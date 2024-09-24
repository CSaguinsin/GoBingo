import os
import logging
import re  # For regex pattern matching
from dotenv import load_dotenv
import requests
from fpdf import FPDF
from PIL import Image, ImageEnhance, ImageFilter  # For image preprocessing
import pytesseract
import cv2
import numpy as np
from flask import Flask, request
from firebase_admin import firestore  # Add this import for Firestore
from database.firebase_init import initialize_firestore  # Assuming firebase_init is your module for initializing Firestore
import easyocr  # Add the EasyOCR library
import json  # Ensure JSON library is imported

app = Flask(__name__)  # Define the Flask app

# Set the path to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize the EasyOCR reader (global reader instance)
reader = easyocr.Reader(['en'])

# Create a folder to store PDFs if it doesn't exist
PDF_FOLDER = os.path.join(os.getcwd(), 'pdf_folder')
os.makedirs(PDF_FOLDER, exist_ok=True)

# Path to the DejaVuSansCondensed.ttf file
FONT_PATH = os.getenv('FONT_PATH')

# Class for handling Unicode characters in PDFs using DejaVuSansCondensed.ttf
class UTF8FPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Add the DejaVuSansCondensed font
        self.add_font('DejaVu', '', FONT_PATH, uni=True)

def create_selectable_pdf_from_image(image_path, pdf_path):
    try:
        # Create a new PDF with UTF-8 support
        pdf = UTF8FPDF()
        pdf.add_page()

        # Add the image to the PDF
        pdf.image(image_path, x=10, y=10, w=190)

        # Save the PDF
        pdf.output(pdf_path)
        logger.info(f"Created selectable PDF at {pdf_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating selectable PDF: {e}")
        return False

# Parse extracted text for identity card
def parse_identity_card_text(extracted_text):
    parsed_data = {}

    # Example regex patterns for each field (adjust according to actual text structure)
    name_match = re.search(r'Name:\s*(.*)', extracted_text)
    id_no_match = re.search(r'Identity Card No:\s*(.*)', extracted_text)
    race_match = re.search(r'Race:\s*(.*)', extracted_text)
    dob_match = re.search(r'Date of Birth:\s*(.*)', extracted_text)
    sex_match = re.search(r'Sex:\s*(.*)', extracted_text)
    pob_match = re.search(r'Place of Birth:\s*(.*)', extracted_text)

    # Store extracted data in dictionary
    if name_match:
        parsed_data['Name'] = name_match.group(1).strip()
    if id_no_match:
        parsed_data['Identity_Card_No'] = id_no_match.group(1).strip()
    if race_match:
        parsed_data['Race'] = race_match.group(1).strip()
    if dob_match:
        parsed_data['Date_of_birth'] = dob_match.group(1).strip()
    if sex_match:
        parsed_data['Sex'] = sex_match.group(1).strip()
    if pob_match:
        parsed_data['Place_of_birth'] = pob_match.group(1).strip()

    return parsed_data

# Parse extracted text for driver's license
def parse_drivers_license_text(extracted_text):
    parsed_data = {}

    # Example regex patterns for each field (adjust according to actual text structure)
    name_match = re.search(r'Name:\s*(.*)', extracted_text)
    license_no_match = re.search(r'License No:\s*(.*)', extracted_text)
    issue_date_match = re.search(r'Date of Issue:\s*(.*)', extracted_text)
    expiry_date_match = re.search(r'Expiry Date:\s*(.*)', extracted_text)

    # Store extracted data in dictionary
    if name_match:
        parsed_data['Name'] = name_match.group(1).strip()
    if license_no_match:
        parsed_data['License_No'] = license_no_match.group(1).strip()
    if issue_date_match:
        parsed_data['Date_of_issue'] = issue_date_match.group(1).strip()
    if expiry_date_match:
        parsed_data['Expiry_date'] = expiry_date_match.group(1).strip()

    return parsed_data

def parse_log_card_text(extracted_text):
    # Parse log card text (you can adjust based on the structure of the log card)
    parsed_data = {}

    id_no_match = re.search(r'Card ID:\s*(.*)', extracted_text)
    name_match = re.search(r'Name:\s*(.*)', extracted_text)
    race_match = re.search(r'Race:\s*(.*)', extracted_text)
    dob_match = re.search(r'Date of Birth:\s*(.*)', extracted_text)
    sex_match = re.search(r'Sex:\s*(.*)', extracted_text)
    pob_match = re.search(r'Place of Birth:\s*(.*)', extracted_text)

    # Extract the data if matched
    if id_no_match:
        parsed_data['Identity_Card_No'] = id_no_match.group(1).strip()
    if name_match:
        parsed_data['Name'] = name_match.group(1).strip()
    if race_match:
        parsed_data['Race'] = race_match.group(1).strip()
    if dob_match:
        parsed_data['Date_of_birth'] = dob_match.group(1).strip()
    if sex_match:
        parsed_data['Sex'] = sex_match.group(1).strip()
    if pob_match:
        parsed_data['Place_of_birth'] = pob_match.group(1).strip()

    return parsed_data


# Function to enhance image quality using OpenCV
def enhance_image_quality(image_path):
    try:
        if not os.path.exists(image_path):
            raise ValueError(f"Image file at {image_path} does not exist.")
        
        # Read and process the image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Image at {image_path} could not be loaded.")
        
        # Resize and enhance the image
        scale_percent = 200  # Increase image size by 200%
        width = int(image.shape[1] * scale_percent / 100)
        height = int(image.shape[0] * scale_percent / 100)
        resized_image = cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)
        denoised_image = cv2.fastNlMeansDenoisingColored(resized_image, None, h=10, templateWindowSize=7, searchWindowSize=21)
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])  # Sharpening kernel
        sharpened_image = cv2.filter2D(denoised_image, -1, kernel)

        logger.info(f"Image at {image_path} enhanced successfully.")
        return sharpened_image

    except Exception as e:
        logger.error(f"Error enhancing image quality: {e}")
        return None

# Function to extract text using Tesseract OCR
def extract_text_from_image(image_path):
    try:
        enhanced_image = enhance_image_quality(image_path)

        if enhanced_image is None:
            logger.error("Image enhancement failed.")
            return None
        
        pil_image = Image.fromarray(cv2.cvtColor(enhanced_image, cv2.COLOR_BGR2RGB))
        text = pytesseract.image_to_string(pil_image)
        
        if text.strip():
            logger.info("Text extracted from image using Tesseract OCR.")
            return text.strip()
        else:
            logger.error("No text extracted from the image.")
            return None

    except Exception as e:
        logger.error(f"Failed to extract text from image: {e}")
        return None

# Convert OCR results to JSON format
def convert_to_json(result):
    data = []
    for (bbox, text, confidence) in result:
        entry = {
            "coordinates": np.array(bbox).tolist(),  # Convert numpy array to list
            "text": text,
            "confidence": float(confidence)  # Ensure confidence is a float
        }
        data.append(entry)
    return json.dumps(data, indent=4)

# OCR processing for driver's license using EasyOCR
def ocr_drivers_license(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Error: Unable to load image at {image_path}")
    
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    result = reader.readtext(img_gray)
    return convert_to_json(result)

# OCR processing for identity card using Tesseract
def ocr_identity_card(image_path):
    return extract_text_from_image(image_path)

# Process uploaded document and perform OCR based on doc type
def process_uploaded_document(uploaded_file, doc_type):
    try:
        image_folder = os.path.join(os.getcwd(), 'image_folder')
        os.makedirs(image_folder, exist_ok=True)

        # Generate unique filename
        filename = f"{doc_type}_{os.urandom(8).hex()}.jpg"
        file_path = os.path.join(image_folder, filename)

        # Save uploaded file
        with open(file_path, "wb") as f:
            f.write(uploaded_file.read())

        # Perform OCR based on document type
        if doc_type == 'drivers_license':
            return ocr_drivers_license(file_path)
        elif doc_type == 'identity_card':
            return ocr_identity_card(file_path)
        else:
            raise ValueError(f"Unsupported document type: {doc_type}")

    except Exception as e:
        logger.error(f"Error processing {doc_type}: {e}")
        return None

# Firestore saving function
def save_to_firestore(parsed_data, doc_type, file_path):
    # Extract 'Name' to use as the collection name
    name = parsed_data.get('Name')
    
    # Ensure that 'Name' is present, otherwise log an error
    if not name:
        logger.error("Failed to find a valid Name in the parsed data.")
        return None

    # Sanitize the 'Name' (convert to lowercase, replace spaces with underscores)
    sanitized_name = name.replace(" ", "_").lower()

    # Initialize Firestore
    db = initialize_firestore()

    # Prepare the data to be saved
    doc_data = {
        'Identity_Card_No': parsed_data.get('Identity_Card_No'),
        'Name': parsed_data.get('Name'),
        'Race': parsed_data.get('Race'),
        'Date_of_birth': parsed_data.get('Date_of_birth'),
        'Sex': parsed_data.get('Sex'),
        'Place_of_birth': parsed_data.get('Place_of_birth'),
        'document_type': doc_type,
        'image_path': file_path,
        'timestamp': firestore.SERVER_TIMESTAMP
    }

    try:
        # Save the document to Firestore under the user's collection (e.g., john_doe)
        doc_ref = db.collection(sanitized_name).document(doc_type)
        doc_ref.set(doc_data)
        logger.info(f"Parsed data saved to Firestore as /{sanitized_name}/{doc_type}.")
        return parsed_data
    except Exception as e:
        logger.error(f"Failed to save data to Firestore: {e}")
        return None


# Flask route for identity card upload
@app.route('/upload_identity_card', methods=['POST'])
def upload_identity_card():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        # Step 1: Extract text from the identity card image
        extracted_text = process_uploaded_document(file, 'identity_card')
        if extracted_text:
            # Step 2: Parse the extracted text into a dictionary (parsed_data)
            parsed_data = parse_identity_card_text(extracted_text)
            
            # Check if we successfully parsed the name
            if parsed_data.get('Name'):
                # Step 3: Save to Firestore
                saved_data = save_to_firestore(parsed_data, 'identity_card', file.filename)
                if saved_data:
                    return saved_data, 200
                else:
                    return 'Failed to save data to Firestore', 500
            else:
                return 'Failed to extract required fields from the identity card', 500
        else:
            return 'Failed to process image', 500

# Flask route for driver's license upload
@app.route('/upload_drivers_license', methods=['POST'])
def upload_drivers_license():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        # Step 1: Extract text from the driver's license image
        extracted_text = process_uploaded_document(file, 'drivers_license')
        if extracted_text:
            # Step 2: Parse the extracted text into a dictionary (parsed_data)
            parsed_data = parse_drivers_license_text(extracted_text)

            # Check if we successfully parsed the name
            if parsed_data.get('Name'):
                # Step 3: Save to Firestore
                saved_data = save_to_firestore(parsed_data, 'drivers_license', file.filename)
                if saved_data:
                    return saved_data, 200
                else:
                    return 'Failed to save data to Firestore', 500
            else:
                return 'Failed to extract required fields from the drivers license', 500
        else:
            return 'Failed to process image', 500

@app.route('/upload_log_card', methods=['POST'])
def upload_log_card():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        # Step 1: Extract text from the log card image
        extracted_text = process_uploaded_document(file, 'log_card')
        if extracted_text:
            # Step 2: Parse the extracted text
            parsed_data = parse_log_card_text(extracted_text)
            
            # Check if we successfully parsed the name
            if parsed_data.get('Name'):
                # Step 3: Save to Firestore
                saved_data = save_to_firestore(parsed_data, 'log_card', file.filename)
                if saved_data:
                    return saved_data, 200
                else:
                    return 'Failed to save data to Firestore', 500
            else:
                return 'Failed to extract required fields from the log card', 500
        else:
            return 'Failed to process image', 500

