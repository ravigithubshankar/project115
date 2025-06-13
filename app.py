from flask import Flask, request, jsonify, send_file,render_template
from werkzeug.utils import secure_filename
import os
import uuid
import threading
import queue
import re
from functools import wraps
from flask_caching import Cache
from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from extraction import extract_handwritten_answers, count_pdf_pages  # Import your existing functions
from pdf2image import convert_from_path
from api import store_in_db
from flask_cors import CORS
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('PDF_Extraction_API')
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
logger.addHandler(handler)




POPPLER_PATH = r'C:\Program Files\poppler-24.06.0\Library\bin'


# Initialize Flask app
app = Flask(__name__)


CORS(app)

# Add request logging
@app.before_request
def log_request_info():
    logger.info(f"Request: {request.method} {request.url} from {request.remote_addr}")

    
# Configure cache
app.config['CACHE_TYPE'] = 'simple'  # Use Redis in production
cache = Cache(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB limit

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Task queue for load balancing
task_queue = queue.Queue()
workers = []

@app.route('/')
def home():
    id_token=request.args.get('idToken','').strip()
    refresh_token=request.args.get('refreshToken','').strip()
    
    print(f"Received idToken in app.py: {id_token}")
    print(f"received refreshtoken in app.py:{refresh_token}")
    return render_template('upload.html',id_token=id_token,refresh_token=refresh_token)

# Worker function for processing tasks
def worker():
    while True:
        task = task_queue.get()
        if task is None:
            break  # Poison pill to shutdown worker
        try:
            task['function'](*task['args'], **task['kwargs'])
        except Exception as e:
            logger.error(f"Error processing task: {e}")
        task_queue.task_done()

# Start worker threads (adjust based on server capacity)
for i in range(20):  # 4 worker threads
    t = threading.Thread(target=worker)
    t.start()
    workers.append(t)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Update the process_pdf_task function in your app.py
def process_pdf_task(filepath, task_id):
    try:
        original_filename = os.path.basename(filepath).split('_', 1)[1]
        original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
        os.rename(filepath, original_filepath)

        try:
            logger.info(f"Starting processing for task {task_id}, file: {original_filename}")
            pages = count_pdf_pages(original_filepath)  # Assuming this function exists
            logger.info(f"Total pages in PDF: {pages}")
            results = extract_handwritten_answers(original_filepath)
            logger.info(f"Handwritten answers extracted: {results.get('handwritten_answers', [])}")
            results.update({
                'status': 'completed',
                'task_id': task_id,
                'pages_processed': len(results['handwritten_answers'])
            })

                        # Prepare data for MongoDB
            answers_for_db = results['handwritten_answers']
            roll_no = results.get("roll_no")
            if roll_no is None or roll_no == "":
                roll_no = "unknown"  # Ensure roll_no is never null

            # Parse the position field to extract the question number
            parsed_answers = []
            for answer in answers_for_db:
                position = answer["position"]
                # Try to extract question number from formats like "Page 1, Section 1)"
                match = re.search(r'Section (\d+)', position)
                if match:
                    question_no = int(match.group(1))
                else:
                    # Fallback: If no match, use a default or log an error
                    logger.warning(f"Could not parse question number from position: {position}")
                    question_no = 0  # Default to 0 or handle differently as needed
                parsed_answers.append({
                    "question_no": question_no,
                    "answer_text": answer["ocr_text"]
                })

            student_data = {
                "roll_no": roll_no,
                "answers": parsed_answers,
                "total_questions": len(answers_for_db),
                "created_at": datetime.now().isoformat()+"Z",  # Updated to 05:34 PM IST
                "updated_at": datetime.now().isoformat()+"Z"   # Updated to 05:34 PM IST
            }

            # Store in MongoDB
            db_result = store_in_db(student_data)
            logger.info(f"Data stored in MongoDB for task {task_id}: {db_result}")
        finally:
            os.rename(original_filepath, filepath)

        result_file = os.path.join(app.config['PROCESSED_FOLDER'], f"{task_id}_results.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)

    except Exception as e:
        logger.error(f"Processing failed for task {task_id}: {str(e)}", exc_info=True)
        error_result = {
            'status': 'error',
            'error': str(e),
            'task_id': task_id,
            'solution': 'Check Poppler installation' if 'poppler' in str(e).lower() else ''
        }
        result_file = os.path.join(app.config["PROCESSED_FOLDER"], f"{task_id}_results.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(error_result, f, indent=2)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload and initiate processing"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Generate unique task ID
            task_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)

            original_filepath=os.path.join(app.config['UPLOAD_FOLDER'],filename)
            file.save(original_filepath)

            tracked_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
            
            os.rename(original_filepath,tracked_filepath)

            
            # Add task to queue
            task_queue.put({
                'function': process_pdf_task,
                'args': (tracked_filepath, task_id),
                'kwargs': {}
            })
            
            return jsonify({
                'status': 'queued',
                'task_id': task_id,
                'filename': filename
            }), 202
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/status/<task_id>', methods=['GET'])
@cache.cached(timeout=10)  # Cache status for 10 seconds
def get_status(task_id):
    """Check processing status"""
    result_file = os.path.join(app.config['PROCESSED_FOLDER'], f"{task_id}_results.json")
    
    if os.path.exists(result_file):
        try:
            with open(result_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
            return jsonify(results)
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    else:
        return jsonify({'status': 'processing', 'message': 'File is still being processed'}), 200

@app.route('/api/results/<task_id>', methods=['GET'])
def get_results(task_id):
    """Get final results"""
    result_file = os.path.join(app.config['PROCESSED_FOLDER'], f"{task_id}_results.json")
    
    if not os.path.exists(result_file):
        return jsonify({'error': 'Results not found'}), 404
        
    try:
        with open(result_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        if results.get('status') != 'completed':
            return jsonify(results), 202  # Still processing or error
            
        # Optionally clean up files
        # os.remove(result_file)
        # os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_*.pdf"))
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<task_id>', methods=['GET'])
def download_results(task_id):
    """Download results as JSON file"""
    result_file = os.path.join(app.config['PROCESSED_FOLDER'], f"{task_id}_results.json")
    
    if not os.path.exists(result_file):
        return jsonify({'error': 'Results not found'}), 404
        
    try:
        return send_file(
            result_file,
            mimetype='application/json',
            as_attachment=True,
            download_name=f"{task_id}_results.json"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def shutdown_workers():
    """Clean shutdown of worker threads"""
    for _ in workers:
        task_queue.put(None)
    for t in workers:
        t.join()

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, threaded=True)
    finally:
        shutdown_workers()
        from api import close_connection  # Import here to avoid circular import
        close_connection()  # Close MongoDB connection