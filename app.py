from flask import Flask
import os
from flask import send_from_directory, redirect, request, render_template, Flask, flash, url_for, session
from flask_cors import CORS
from flask_session import Session
from tempfile import gettempdir
import pyrebase
import pprint
import uuid
import jwt
import requests
from firebase_admin import credentials
from firebase_admin import auth
import datetime
from werkzeug.utils import secure_filename
# To preprocess uploaded essay files
from tensorflow.keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from datetime import datetime
# For Google Cloud Firestore
from google.cloud import firestore
import requests
import numpy as np
import pickle
import json
from spellchecker import SpellChecker
import pprint
import string
from pymongo import MongoClient
from flask import Flask,request,jsonify



# Web app's Firebase configuration
firebaseConfig = {
    "apiKey": "AIzaSyCyItr7fcP1SF2ee0yzYl28fjJoOMVeLVw",
    "authDomain": "gen-lang-client-.firebaseapp.com",
    "databaseURL": "https://gen-lang-client-0478230925-default-rtdb.firebaseio.com",
    "projectId": "gen-lang-client-0478230925",
    "storageBucket": "gen-lang-client-0478230925.firebasestorage.app",
    "messagingSenderId": "672302890022",
    "appId": "1:672302890022:android:8355c5348b2478f2e7bae7",
    "measurementId": "G-1ST0B6HD4Y"
}
# Firebase Auth
firebase = pyrebase.initialize_app(firebaseConfig)

client=MongoClient("mongodb://localhost:27017")
db=client["question_bank"]
questions_collecion=db["questions"]

db=client['answer']
answers_collection=db["answers"]

# The minimum and maximum scored attained for each prompt
# Used in the normalisation of the score.
# First element in the list (-1) is used for padding
MIN_SCORES = [-1, 2, 1, 0, 0, 0, 0, 0, 0, 0]
MAX_SCORES = [-1, 12, 6, 3, 3, 4, 4, 30, 60]

import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("C:\\Users\\ravis\\Downloads\\gen-lang-client-0478230925-firebase-adminsdk-vmjvx-a317ee507c.json")
firebase_admin.initialize_app(cred)

db = firestore.client()


#import os
#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\\Users\\ravis\\Downloads\\gold-summer-359216-c982c605fb5b.json"
#from google.cloud import firestore


# Cloud Firestore
#db = firestore.Client('essayscore')

app = Flask(__name__, static_url_path='/static')
# session = {}
app.secret_key = "random strings"
# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# configure session to use filesystem (instead of signed cookies)
#app.config["SESSION_FILE_DIR"] = gettempdir()
#print(app.config["SESSION_FILE_DIR"])
#app.config["SESSION_PERMANENT"] = False
#app.config["SESSION_TYPE"] = "filesystem"
#aSession(app)

@app.route('/')
def index():
    return render_template('index.html')

"""
@app.route('/login', methods=["GET", "POST"])
def login():
    if (request.method == "GET"):
        return render_template('index.html')
    else:
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            # Get a reference to the auth service
            auth = firebase.auth()
            user = auth.sign_in_with_email_and_password(email, password)
            
            pprint.pprint(user)

            session_id=str(uuid.uuid4())

            session_data = {
                'user_id': user['localId'],  # Firebase user ID to associate session with user
                'id_token': user['idToken'],
                'refresh_token': user['refreshToken'],
                'email': user['email'],
                'created_at': datetime.now().timestamp(),
                'show_upload_page': True

            }
            db.collection('sessions').document(session_id).set(session_data)

            print(f"Set session for user {user['localId']} with session_id {session_id}")
            print(f"Set id_token in Firestore session {session_id}: {user['idToken']}")
            print(f"Set refresh_token in Firestore session {session_id}: {user['refreshToken']}")

            db.collection('user_activity').add({
                'user_id': user['localId'],
                'action': 'login',
                'timestamp': datetime.now().timestamp()
            })

            response = redirect(url_for("upload_page",session_id=session_id))
            response.set_cookie('session_id', session_id, httponly=True, secure=False,max_age=3600)  # secure=True in production
            return response


            # Set user session
           # session['id_token'] = user['idToken']
            #session['refresh_token']=user['refreshToken']
           # session['email'] = user['email']
            #session['show_login_message']=True
            #print(f"Set id_token in session after login: {session['id_token']}")
            #print(f"Set refresh_token in session after login: {session['refresh_token']}")
            #return redirect(url_for("dashboard"))
        except requests.exceptions.HTTPError as e:
            response = e.args[0].response
            error = response.json()['error']
            print(error)
            if error['message'] == "INVALID_PASSWORD":
                flash("Wrong Password or Username.", "danger")
            elif error['message'] == "EMAIL_NOT_FOUND":
                flash("Not a registered email.", "danger")
            else:
                flash(error['message'], "danger")
            print("Log in failed!")
            return render_template('index.html')
"""

@app.route('/login', methods=["GET", "POST"])
def login():
    if (request.method == "GET"):
        return render_template('index.html')
    else:
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            # Get a reference to the auth service
            auth = firebase.auth()
            user = auth.sign_in_with_email_and_password(email, password)
            pprint.pprint(user)
            # Set user session
            session['id_token'] = user['idToken']
            session['email'] = user['email']
            return redirect(url_for("dashboard"))
        except requests.exceptions.HTTPError as e:
            response = e.args[0].response
            error = response.json()['error']
            print(error)
            if error['message'] == "INVALID_PASSWORD":
                flash("Wrong Password or Username.", "danger")
            elif error['message'] == "EMAIL_NOT_FOUND":
                flash("Not a registered email.", "danger")
            else:
                flash(error['message'], "danger")
            print("Log in failed!")
            return render_template('index.html')
        

@app.route('/register', methods=["GET", "POST"])
def register():
    successful = "Registered Successfully! Please log in."
    if (request.method == "GET"):
        return redirect('index.html')
    else:
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            auth = firebase.auth()
            user = auth.create_user_with_email_and_password(email, password)
            session['id_token'] = user["idToken"]
            session['email'] = user['email']
            flash(successful, "info")
            return redirect('/')
        except requests.exceptions.HTTPError as e:
            response = e.args[0].response
            error = response.json()['error']
            if error["message"] == "EMAIL_EXISTS":
                flash("Email already exists.", "danger")
            else:
                flash(error['message'], "danger")
            print("Register failed!")
            return render_template('index.html')

    
@app.route('/dashboard', methods=["GET", "POST"])
def dashboard():

    id_token=request.args.get('idToken',None)
    refresh_token=request.args.get('refreshToken',None)

    if id_token:
        id_token = id_token.strip()
        print(f"Received idToken in dashboard: {id_token}")
    else:
        print("id token is missing in query parameter")
    if refresh_token:
        refresh_token=refresh_token.strip()
        print(f"received refreshtoken in dashboard:{refresh_token}")
    else:
        print("refresh token is missing in query parameter")

    if id_token:
        try:
            
            import jwt
            decoded_token=jwt.decode(id_token,options={"verify_signature":False})
            exp_timestamp=decoded_token['exp']
            current_timestamp = int(datetime.now().timestamp())
            if exp_timestamp>current_timestamp:
                
                session['id_token']=id_token
                session['email']=decoded_token['email']
            else:

                if refresh_token:
                    print("idtoken expired ,attempting to refresh")
                    auth=firebase.auth()
                    user=auth.refresh(refresh_token)
                    new_id_token = user['idToken']
                    session['id_token'] = new_id_token
                    session['refresh_token']=user['refreshToken']
                    decoded_new_token = jwt.decode(new_id_token, options={"verify_signature": False})
                    session['email'] = decoded_new_token['email']
                else:
                    print("idToken expired and no refreshToken provided")
                    flash("Session expired. Please log in again.", "danger")
                    return redirect(url_for("login"))

        except Exception as e:

            print(f"Error processing idToken: {str(e)}")

            if refresh_token:
                try:
                    print("attempting to refresh token.")
                    auth = firebase.auth()
                    user = auth.refresh(refresh_token)
                    new_id_token = user['idToken']
                    session['id_token'] = new_id_token
                    session['refresh_token'] = user['refreshToken']
                    # Decode the new idToken to get the email
                    decoded_new_token = jwt.decode(new_id_token, options={"verify_signature": False})
                    session['email'] = decoded_new_token['email']
                except Exception as e:
                    print(f"Error refreshing token: {str(e)}")
                    flash("Session expired or invalid token. Please log in again.", "danger")
                    return redirect(url_for("login"))
            else:
                print("idToken invalid and no refreshToken provided")
                flash("Session expired or invalid token. Please log in again.", "danger")
                return redirect(url_for("login"))

           # flash("Session expired or invalid token. Please log in again!")
            #return redirect(url_for("login"))
        
       # else:
        
        #    print("idToken is empty after trimming")
    #else:
     #   print("idToken is missing in query parameter")
        
    if "id_token" not in session:
        print("id_token not in session, redirecting to login")
        return redirect(url_for("login"))
    """
    if session.get('show_login_message', False):
        id_token = session['id_token']
        refresh_token = session['refresh_token']
        upload_url = f"http://localhost:5000/?idToken={id_token}&refreshToken={refresh_token}"
        return redirect(upload_url)
    """
    
    print(f"Session id_token in dashboard: {session.get('id_token', 'Not found')}")
    all_questions=list(questions_collecion.find({},{"_id":0}))

   # current_qid=request.args.get("question")
    #current_data=None

    #if current_qid:
     #   clean_id=current_qid.lstrip("Q")
      #  normalized_id=f"Q{clean_id}"
       # current_data=questions_collecion.find_one(
        #    {"question_id":normalized_id},
         #   {"_id":0}
        #)
    if session.pop('show_login_message',False):
        flash("Login Successfully! Welcome " + session['email'] + "!", "success")
    return render_template("dashboard.html", email=session['email'],questions=all_questions)

""""
@app.route('/dashboard', methods=["GET", "POST"])
def dashboard():
    session_id = request.cookies.get('session_id') or request.args.get('session_id')
    if not session_id:
        print("No session_id provided, redirecting to login")
        flash("Please log in to access the dashboard.", "danger")
        return redirect(url_for("login"))

    # Retrieve session data from Firestore
    #session_doc = db.collection('sessions').document(session_id).get()
    session_ref=db.collection('sessions')
    if not session_doc.exists:
        print(f"Session {session_id} not found in Firestore, redirecting to login")
        flash("Session expired or invalid. Please log in again.", "danger")
        return redirect(url_for("login"))

    session_data = session_doc.to_dict()
    user_id = session_data.get('user_id')
    id_token = session_data.get('id_token')
    email = session_data.get('email')

    if not user_id or not id_token or not email:
        print(f"Session {session_id} missing critical data, redirecting to login")
        flash("Session invalid. Please log in again.", "danger")
        return redirect(url_for("login"))

    # Optionally re-verify id_token to get current user_id
    try:
        decoded_token = jwt.decode(id_token, options={"verify_signature": False})
        current_user_id = decoded_token['user_id']
        if current_user_id != user_id:
            print(f"Session {session_id} does not belong to user {current_user_id}")
            flash("Unauthorized access. Please log in again.", "danger")
            return redirect(url_for("login"))
    except Exception as e:
        print(f"Error verifying id_token: {str(e)}")
        flash("Session invalid. Please log in again.", "danger")
        return redirect(url_for("login"))

    # Process new tokens if provided (e.g., after upload)
    new_id_token = request.args.get('idToken', None)
    new_refresh_token = request.args.get('refreshToken', None)
    if new_id_token and new_refresh_token:
        try:
            decoded_token = jwt.decode(new_id_token, options={"verify_signature": False})
            db.collection('sessions').document(session_id).update({
                'id_token': new_id_token,
                'refresh_token': new_refresh_token,
                'email': decoded_token['email']
            })
            id_token = new_id_token
            email = decoded_token['email']
            print(f"Updated session {session_id} with new tokens for user {user_id}")
        except Exception as e:
            print(f"Error updating tokens: {str(e)}")
            flash("Error updating session. Please log in again.", "danger")
            return redirect(url_for("login"))

    show_login_message = session_data.get('show_login_message', False)
    if show_login_message:
        upload_url = f"http://localhost:5000/?session_id={session_id}"
        print(f"Redirecting to upload page for session {session_id}")
        return redirect(upload_url)

    print(f"Rendering dashboard for user {user_id}, session {session_id}")
    # Fetch user-specific questions (e.g., based on user_id)
    all_questions = list(questions_collection.find({'user_id': user_id}, {"_id": 0}))
    if show_login_message:
        db.collection('sessions').document(session_id).update({'show_login_message': False})
        flash(f"Login Successfully! Welcome {email}!", "success")
    return render_template("dashboard.html", email=email, questions=all_questions)
"""
"""
#ocr page
@app.route('/upload.html')
def upload_page():
    session_id=request.args.get('session_id') or request.cookies.get('session_id')
    if not session_id:
        return redirect(url_for("login"))

    #session_data=db.collection('sessions').document(session_id).get().to_dict()
    session_ref=db.collection('sessions').document(session_id)
    session_data=session_ref.get().to_dict()
    if not session_data:
        return redirect(url_for("login"))
    
   # if "id_token" not in session:
    #    return redirect(url_for("login"))
    return render_template('upload.html',email=session_data['email'],session_id=session_id)
"""

@app.route('/api/answers/<question_id>')
def get_answer(question_id):
    try:

        clean_id=question_id.lstrip("Q")
        normalized_id=f"Q{clean_id}"
        # Normalize question ID (handle both Q1 and QQ1 formats)
        #normalized_id = question_id.upper().replace('Q', 'QQ') if not question_id.startswith('QQ') else question_id

        #normalized_id=f"Q{question_id.lstrip("Q")}" if not question_id.startswith("Q") else question_id

        print(f"fetching answer for questionid:{normalized_id}")
        answer = answers_collection.find_one({'questionId': normalized_id})
        
        if not answer:
            return jsonify({
                'error': 'Answer not found',
                'questionId': normalized_id
            }), 404
        
        print(f"found answer:{answer}")
    
    

        return jsonify({
            'questionId': answer['questionId'],
            'question_text': answer['question_text'],
            'answer_text': answer['answer_text'],
            'updatedAt': answer['updated_at'].isoformat()
        })
        
    except Exception as e:
        print(f"error in get_answer:{str(e)}")
        return jsonify({
            'error': 'Server error',
            'message': str(e)
        }), 500



@app.route('/question/<question_id>',methods=["GET"])
def question(question_id):
    if "id_token" not in session:
        return redirect(url_for("login"))
    
    #if question_id.lstrip("Q"):
     #   question_id=f"Q{question_id}"
    
    clean_id=question_id.lstrip("Q")
    normalized_id=f"Q{clean_id}"

    print(f"Original ID: {question_id} → Normalized: {normalized_id}")



    



    print(f"looking for question:{question_id}")


    

    
    question=questions_collecion.find_one({"question_id":normalized_id})
    if not question:
        print(f"question {normalized_id} not found in database")
        return render_template("404.html"),404
    
    
    all_questions=list(questions_collecion.find({}))
    return render_template("dashboard.html",email=session["email"],question=question,questions=all_questions,current_question_id=normalized_id)

#fetching the questions from database mongodb
@app.route('/get_question/<question_id>')
def get_question(question_id):
    try:
        if "id_token" not in session:
            return jsonify({"error": "Unauthorized"}), 401
        
        # Normalize question ID (handle Q3, QQ3, 3, etc.)
        clean_id = question_id.lstrip('Q')
        normalized_id = f"Q{clean_id}"
        
        print(f"Fetching question: {normalized_id}")  # Debug log
        
        question = questions_collecion.find_one(
            {"question_id": normalized_id},
            {"_id": 0}  # Exclude MongoDB _id field
        )
        
        if not question:
            print(f"Question not found: {normalized_id}")
            return jsonify({"error": "Question not found"}), 404
        
        print(f"Found question: {question}")  # Debug log
        return jsonify(question)
        
    except Exception as e:
        print(f"Error in get_question: {str(e)}")
        return jsonify({"error": "Server error"}), 500

    
#normalization of questions starting with 'Q'
@app.before_request
def normalize_question_ids():
    if request.path.startswith('/question/'):
        parts = request.path.split('/')
        if len(parts) > 2:
            raw_id = parts[2]
            clean_id = raw_id.lstrip('Q')
            normalized_path =f"/question/Q{clean_id}"
            if request.path !=normalized_path:
                return redirect(normalized_path)


            

@app.route('/logout', methods=["GET"])
def logout():
    # Get a reference to the auth service
    auth = firebase.auth()
    auth.current_user = None
    session.clear()
    flash("Successfully logged out!", "success")
    return redirect('/')

#@app.route("/essay/question_id>",methods=["GET"])
#def essay_page(question_id):
   # if "id_token" not in session:
    #    return redirect(url_for("login"))
    
    #question_doc=questions_collecion.find_one({"question_id":question_id})
    #if not question_doc:
     #   return render_template("404.html"),404
    
    #return render_template("essay_dynamic.html",question_id=question_id,question_text=question_doc["question"])




#@app.route("/questions")
#def questions_page():
 #   if "id_token" not in session:
  #      return redirect(url_for("login"))
   # return render_template("questions.html")

#@app.route("/get_questions",method=["GET"])
#def get_questions():
 #   if "id_token" not in session:
  #      return jsonify({"error":"Unauthorized"}),401
    
   # questions_cursor=questions_collecion.find({},{"_id":0})
    #questions=list(questions_cursor)
    #return jsonify(questions)
    

@app.route('/grading', methods=["GET"])
def grading():
    if "id_token" not in session:
        return redirect(url_for("login"))
    # retrieve the prompt
    prompt = request.args.get('prompt', None)
    if not prompt.startswith("Q"):
        prompt=f"Q{prompt}"

    session['prompt'] = prompt
    print(prompt)
    return render_template("grading.html", topic=prompt, email=session['email'])

@app.route('/upload_essay', methods=["POST"])
def upload_essay():
    if (request.method == "POST"):
        fh = request.files['file']
        if fh:
            filename = secure_filename(fh.filename)
            essay_text = [line.strip(b"\r\n") for line in fh]
            return render_template("grading.html", topic=session['prompt'], email=session['email'], essay_text=essay_text)






@app.route('/backend_grade', methods=["POST"])
def grade():
    essay_text = request.form.get("essay")
    print(essay_text)
    print("Entering backend grading")

    prompt_str=session["prompt"]
    if prompt_str.startswith('Q'):
        prompt_str=prompt_str[1:]
    try:
        essay_prompt=int(prompt_str)
    except ValueError:
        flash("Invalid question selected","error")
        return redirect(url_for("dashboard"))
    
    print(essay_prompt)
    print(MAX_SCORES[essay_prompt])

    # Testing: Make GET requests to confirm the status of the backend
    response = requests.get("http://localhost:8501/v1/models/aes_regressor")
    print(response.json())
    # Preprocess the text to fit into the model
    # Read in the tokenizer used to convert text to sequence
    with open("C:\\Users\\ravis\\Downloads\\tokenizer.pickle", 'rb') as handle:
        nltk_tokenizer = pickle.load(handle)
        sequence_vectors = nltk_tokenizer.texts_to_sequences([essay_text])
        print(sequence_vectors)
        # Pad the vectors so that all of them is 500 words long
        data = pad_sequences(sequence_vectors, maxlen=500)
        print(data.shape)
    # Perform spell check using pyspellchecker
    spell_check_dict = check_spellings(essay_text)
    pprint.pprint(spell_check_dict)
    # Define payload for POST request
    payload = {
        "instances": data.tolist()
    }
    # Perform POST RESTful API request to TF Serving Endpoint
  
    try:
        response = requests.post("http://localhost:8501/v1/models/aes_regressor:predict", json=payload)
        print(response.json())
    except requests.exceptions.ConnectTimeout:
        print("Failed to connect to TensorFlow Serving.")

    print(response.status_code)
    print(response.text)
    if (response.status_code == 200):
        try:
            pred_score=response.json()["predictions"][0][0]
            true_score=denormalise_scores(pred_score,essay_prompt)

        #print(int(session["prompt"]))
        #print(MAX_SCORES[int(session["prompt"])])
        #pred_score = response.json()["predictions"][0][0]
        # Denormalise the returned score
        #true_score = denormalise_scores(pred_score, int(session["prompt"]))
        # Store the record in FireStore
        #doc_ref = db.collection(u'submissions').document()
            results_dict = {
                'email': session['email'],
                'timestamp': datetime.datetime.now(),
                'text': essay_text,
                'topic': session['prompt'],
                'max_score': MAX_SCORES[essay_prompt],
                'score_obtained': true_score
            }
            doc_ref=db.collection(u'submissions').document()

            doc_ref.set(results_dict)

            if request.headers.get('X-Requested-With')=='XMLHttpRequest':
                return render_template('results_partial.html',result=results_dict)
            else:
                return render_template("results.html", result=results_dict, email=session["email"])
            
        except Exception as e:
            print(f"Error:{e}")
            if request.headers.get('X-Requested-With')=="XMLHttpRequest":
                return jsonify({"error":str(e)}),500
            else:
                flash("Error processing grading results","error")
                return redirect(url_for("dashboard"))
            
        except Exception as e:
            print(f"Result processing failed:{e}")
            flash("Error processing grading results","error")
            return render_template("results.html")
    else:
        flash("Problem retrieving score from the server. Please check the console for details.", "error")
        print(response.text)
        return render_template("results.html")

def denormalise_scores(pred_score, essay_prompt):
    """ Denormalise the score returned by the model into their real score.
        Parameters:
            pred_score:     predicted score return by the model.
            essay_prompt:   the topic of the essay.
        Returns:
            Essay score scaled back to their respective topics.
    """
    true_score = pred_score * (MAX_SCORES[essay_prompt] - MIN_SCORES[essay_prompt]) + MIN_SCORES[essay_prompt]
    return true_score

@app.route('/view_submissions', methods=["GET"])
def view_submissions():
    if request.method == "GET":
        email = session['email']
        docs = db.collection('submissions').where("email", "==", email).stream()
        submissions = []
        for doc in docs:
            print('{} => {}'.format(doc.id, doc.to_dict()))
            submissions.append(doc.to_dict())
        print(submissions)
        return render_template("view_submissions.html", email=session['email'], submissions=submissions)

def check_spellings(essay):
    spell = SpellChecker(distance=1)
    contractions_str = "'tis,'twas,ain't,aren't,can't,could've,couldn't,didn't,doesn't,don't,hasn't,he'd,he'll,he's,how'd,how'll,how's,i'd,i'll,i'm,i've,isn't,it's,might've,mightn't,must've,mustn't,shan't,she'd,she'll,she's,should've,shouldn't,that'll,that's,there's,they'd,they'll,they're,they've,wasn't,we'd,we'll,we're,weren't,what'd,what's,when,when'd,when'll,when's,where'd,where'll,where's,who'd,who'll,who's,why'd,why'll,why's,won't,would've,wouldn't,you'd,you'll,you're,you've"
    spell.word_frequency.load_words(contractions_str.split(','))   
    punc_list = string.punctuation.replace('@', '')
    punc_list = punc_list.replace('\'', '')
    essay = essay.translate(str.maketrans('', '', punc_list))
    essay_words = essay.lower().split() # get each words in the text
    print(essay_words)
    spell_check_dict = {}
    for word in essay_words:
        # Skip anonymized tokens
        if word.startswith('@'):
            continue
        if word not in spell:
            spell_check_dict[word] = spell.candidates(word)
    return spell_check_dict
    
if __name__ == "__main__":
    # Set debugging to true to enable hot reload
    app.secret_key = 'any random stdring'
    app.run(debug=True, port=5001)
    