import PyPDF2
import pytesseract
from PIL import Image, ImageEnhance
import re
import os
import json
import base64
from pdf2image import convert_from_path
from PIL import ImageFilter
try:
    import pdf2image
except ImportError:
    pdf2image = None
from google.oauth2 import service_account
import os
from google.cloud import vision
from groq import Groq

# In your extraction.py or app.py
POPPLER_PATH = r"C:\Program Files\poppler-24.08.0\Library\bin"  # Update this path

# Configure Tesseract path
#pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'



GROQ_API_KEY = "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"  # Replace with your Groq API key
groq_client = Groq(api_key=GROQ_API_KEY)

def encode_image(image_path):
    with open(image_path,"rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def count_pdf_pages(pdf_path):
    """Count the number of pages in the PDF."""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            return len(pdf_reader.pages)
    except Exception as e:
        print(f"Error counting pages: {e}")
        return 0

def extract_handwritten_answers(pdf_path):

    filename = os.path.basename(pdf_path).lower()
    roll_no = re.match(r'^(\d{3}[a-z]{2}\d{5})\.pdf$', filename)
    if not roll_no:
        raise ValueError(f"Invalid filename format: {filename}")
    
    roll_no = roll_no.group(1).upper()
    results = {
        'roll_no': roll_no,
        'handwritten_answers': []
    }

    try:
        num_pages = count_pdf_pages(pdf_path)
        if num_pages == 0:
            raise ValueError("No pages found in the PDF or error reading the PDF.")

        if pdf2image:
            try:
                print(f"Converting PDF to images: {pdf_path}")
                pages = pdf2image.convert_from_path(pdf_path, dpi=400, poppler_path=POPPLER_PATH)
                print(f"Successfully converted {len(pages)} pages")

                for page_num, page in enumerate(pages, 1):
                    

                    #save the image temporarily for google vision
                    temp_img_path=f"temp_page_{page_num}.png"
                    page.save(temp_img_path)

                    try:
                        base64_image=encode_image(temp_img_path)
                    except Exception as e:
                        print(f"Error encoding image to base64:{e}")
                        if os.path.exists(temp_img_path):
                            os.remove(temp_img_path)
                        continue

                    #base64_image=encode_image(temp_img_path)

                   # credentials = service_account.Credentials.from_service_account_file(
                    #    r"C:\Users\ravis\OneDrive\Desktop\mythic-lattice-462217-s9-97fab03e8a59.json"  # Updated path
                    #)

                    #use Google vision for ocr
                    #client=vision.ImageAnnotatorClient(credentials=credentials)
                    #with open(temp_img_path,"rb") as image_file:
                     #   content=image_file.read()
                    #image=vision.Image(content=content)
                   # response=client.document_text_detection(image=image)
                    #text=response.text_annotations[0].description if response.text_annotations else ""
                   # print(f"Raw OCR Text on page {page_num}:{text}")

                    #if os.path.exists(temp_img_path):
                     #   os.remove(temp_img_path)


                    #if text:
                    cleaned_text=""
                    try:
                        prompt=(
                            "You are an expert at extracting and structuring handwritten text from images. "
                            "The following image contains handwritten student answers. "
                            "1. Extract the text from the image. "
                            "2. Clean up the text, fix any errors, and structure it into numbered sections (e.g., 1), 2), etc.). "
                            "If the numbering is missing or incorrect, infer the correct numbering based on the context. "
                            "Return only the final cleaned and structured text, without any intermediate steps or explanations."
                            
                            )

                        response = groq_client.chat.completions.create(  # Fixed syntax: '=' instead of ':'
                        model='meta-llama/llama-4-scout-17b-16e-instruct',
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{base64_image}",  # Fixed typo: 'base64'
                                        },
                                    },
                                ],
                            }
                        ],
                        max_tokens=3000,
                        temperature=1,  # Adjusted to 1 for more consistent results
                        top_p=1,
                        stream=False,
                        stop=None,
                    )

                        if response and response.choices and response.choices[0].message:
                            cleaned_text=response.choices[0].message.content.strip()
                            print(f"Extracted and cleaned text on page {page_num}:{cleaned_text}")

                        else:
                            print(f"Groq api returned no valid response for page {page_num}")

                        

                        #cleaned_text=response.choices[0].message.content.strip()
                        #print(f"Cleaned Text from LLaMA on page {page_num}: {cleaned_text}")

                    except Exception as e:
                        print(f"Groq api error on page {page_num}:{str(e)}")
                        #print(f"groq api error:{e}")
                        if hasattr(e,'response'):
                            print(f"groq api error details:{e.response}")

                        #cleaned_text=""
                    finally:

                        if os.path.exists(temp_img_path):
                            os.remove(temp_img_path)






                    # Process text for the current page
                    if cleaned_text:
                        sections = re.split(r'(\d+\)|Q\d+\)|\d+\.\s*)', cleaned_text)
                        answer_sections = []
                        for i in range(1, len(sections), 2):
                            answer_num = sections[i].strip()
                            answer_text = sections[i + 1].strip() if i + 1 < len(sections) else ""
                            if answer_text:
                                answer_sections.append((answer_num, answer_text))
                        print(f"Answer sections on page {page_num}: {answer_sections}")

                        seen_answers = set()
                        for idx, (answer_num, section) in enumerate(answer_sections, 1):
                            ocr_text = re.sub(r'\n+', ' ', section).strip()
                            if ocr_text and ocr_text not in seen_answers:
                                seen_answers.add(ocr_text)
                                answer_context = f"[...answer {answer_num}...]"
                                filled_sentence = ocr_text
                                results['handwritten_answers'].append({
                                    'page': page_num,
                                    'ocr_text': ocr_text,
                                    'context': answer_context,
                                    'filled_sentence': filled_sentence,
                                    'position': f"Page {page_num}, Section {answer_num}"
                                })
            except Exception as e:
                print(f"pdf2image Error: {str(e)}")
                print(f"Exception type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
        else:
            print("pdf2image not installed. Falling back to empty results.")

    except Exception as e:
        print(f"Processing Error: {e}")
    
    return results

if __name__ == "__main__":
    pdf_path = r"C:\\Users\\ravis\\OneDrive\\Desktop\\211FA18115.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found at {pdf_path}")
        exit()

    try:
        print(f"Processing {os.path.basename(pdf_path)}...")
        results = extract_handwritten_answers(pdf_path)

        print("\nExtracted Results:")
        print(f"Roll Number: {results['roll_no']}")
        print(f"Total Pages: {count_pdf_pages(pdf_path)}")
        
        if results['handwritten_answers']:
            print("\nHandwritten Answers Found:\n")
            for i, answer in enumerate(results['handwritten_answers'], 1):
                print(f"Answer {i}:")
                print(f"Context: {answer['context']}")
                print(f"OCR Text: {answer['ocr_text']}")
                print(f"Position: {answer['position']}\n")
        else:
            print("\nNo handwritten answers detected")

        output_file = f"{results['roll_no']}_answers.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {output_file}")

    except Exception as e:
        print(f"\nError: {e}")