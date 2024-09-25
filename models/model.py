import os
import logging
import re  # For regex pattern matching
import json  # <-- Added this import
from dotenv import load_dotenv
import requests
from fpdf import FPDF
from PIL import Image, ImageEnhance, ImageFilter  # For image preprocessing
import pytesseract
import cv2
import numpy as np
import easyocr  # Import EasyOCR for driver's license processing
from flask import Flask, request
from firebase_admin import firestore  # Add this import for Firestore
from database.firebase_init import initialize_firestore  # Assuming firebase_init is your module for initializing Firestore


app = Flask(__name__)  # Define the Flask app

# Set the path to the Tesseract executable
pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
load_dotenv()

logger = logging.getLogger(__name__)

# Get the AI model endpoint from environment variables
AI_MODEL_ENDPOINT = os.getenv('AI_MODEL_ENDPOINT')

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

# Function to enhance image quality using OpenCV
def enhance_image_quality(image_path):
    try:
        # Check if the file exists at the given path
        if not os.path.exists(image_path):
            raise ValueError(f"Image file at {image_path} does not exist.")
        
        # Read the image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Image at {image_path} could not be loaded. Check file path or integrity.")
        
        # Step 1: Resize the image to a higher resolution (optional, based on use case)
        scale_percent = 200  # Increase the image size by 200%
        width = int(image.shape[1] * scale_percent / 100)
        height = int(image.shape[0] * scale_percent / 100)
        resized_image = cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)

        # Step 2: Apply denoising to reduce noise
        denoised_image = cv2.fastNlMeansDenoisingColored(resized_image, None, h=10, templateWindowSize=7, searchWindowSize=21)

        # Step 3: Sharpen the image for better clarity
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])  # Sharpening kernel
        sharpened_image = cv2.filter2D(denoised_image, -1, kernel)

        logger.info(f"Image at {image_path} enhanced successfully.")
        return sharpened_image

    except Exception as e:
        logger.error(f"Error enhancing image quality: {e}")
        return None

# Function to extract text from an image using pytesseract and display it on the terminal
def extract_text_from_image(image_path):
    try:
        # Enhance the image quality first
        enhanced_image = enhance_image_quality(image_path)
        
        if enhanced_image is None:
            logger.error("Image enhancement failed. Cannot proceed with OCR.")
            return None
        
        # Convert OpenCV image to PIL Image for pytesseract
        enhanced_image = cv2.cvtColor(enhanced_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(enhanced_image)

        # Perform OCR to extract text from the enhanced image
        text = pytesseract.image_to_string(pil_image)
        
        if text.strip():
            # Display extracted text on the terminal
            print("\n--- Extracted Text from Image ---\n")
            print(text)
            print("\n--- End of Extracted Text ---\n")
        else:
            print("No text was extracted from the image.")

        return text

    except Exception as e:
        logger.error(f"Failed to extract text from image: {e}")
        return None


# Function to convert EasyOCR result to JSON (for debugging or logging)
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

# Function to process the driver's license using EasyOCR
def process_drivers_license(image_path):
    try:
        # Initialize the EasyOCR reader
        reader = easyocr.Reader(['en'])

        # Read the image
        img = cv2.imread(image_path)

        if img is None:
            logger.error(f"Error: Unable to load image at {image_path}")
            return None

        # Convert the image to grayscale for better OCR accuracy
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Use EasyOCR to extract text from the grayscale image
        result = reader.readtext(img_gray)

        # Convert result to JSON (for debugging or logging purposes)
        json_result = convert_to_json(result)
        logger.info(f"OCR Result for Driver's License: {json_result}")

        # Extract the key fields from the OCR result
        license_data = extract_drivers_license_data(result)

        # Log a message if no relevant data was extracted
        if not any(license_data.values()):
            logger.error("No relevant driver's license data found.")
            return None

        # Save the extracted data to Firestore (even if partial data is available)
        try:
            # Initialize Firestore database
            db = initialize_firestore()

            # Prepare Firestore document data
            doc_data = {
                'License_Number': license_data.get('License_Number'),
                'Name': license_data.get('Name', 'Unknown'),  # Default to 'Unknown' if missing
                'Birth_Date': license_data.get('Birth_Date'),
                'Issue_Date': license_data.get('Issue_Date'),
                'timestamp': firestore.SERVER_TIMESTAMP,
                'image_path': image_path  # Optional: Storing the image path if needed
            }

            # Remove None values from Firestore document data before saving
            filtered_doc_data = {k: v for k, v in doc_data.items() if v is not None}

            # Save to Firestore, using an auto-generated document ID in the 'drivers_licenses' collection
            doc_ref = db.collection('drivers_licenses').document()
            doc_ref.set(filtered_doc_data)
            logger.info(f"Driver's License data successfully saved to Firestore.")
        
        except Exception as e:
            logger.error(f"Failed to save driver's license data to Firestore: {e}")
            return None

        return license_data

    except Exception as e:
        logger.error(f"Failed to process driver's license: {e}")
        return None



# Function to extract specific fields from the OCR result for the driver's license
def extract_drivers_license_data(ocr_result):
    license_data = {
        'License_Number': None,
        'Name': None,
        'Birth_Date': None,
        'Issue_Date': None
    }

    for (bbox, text, confidence) in ocr_result:
        text = text.strip().lower()

        # Use basic keyword matching to extract data (improve this based on your OCR results)
        if 'license' in text and 'number' in text:
            license_data['License_Number'] = text.split(':')[-1].strip()
        elif 'name' in text:
            license_data['Name'] = text.split(':')[-1].strip()
        elif 'birth date' in text or 'dob' in text:
            license_data['Birth_Date'] = text.split(':')[-1].strip()
        elif 'issue date' in text:
            license_data['Issue_Date'] = text.split(':')[-1].strip()

    # Log warnings for any missing fields
    if not license_data['License_Number']:
        logger.warning("License Number is missing in the extracted data.")
    if not license_data['Name']:
        logger.warning("Name is missing in the extracted data.")
    if not license_data['Birth_Date']:
        logger.warning("Birth Date is missing in the extracted data.")
    if not license_data['Issue_Date']:
        logger.warning("Issue Date is missing in the extracted data.")

    return license_data  # Return the extracted (partial or full) license data



# Function to process the uploaded identity card or driver's license and save to Firestore
def process_uploaded_document(uploaded_file, document_type):
    try:
        # Ensure document_type is correctly handled
        if document_type not in ['identity_card', 'drivers_license']:
            logger.error(f"Unsupported document type: {document_type}")
            return None

        # Create image_folder if it doesn't exist
        image_folder = os.path.join(os.getcwd(), 'image_folder')
        os.makedirs(image_folder, exist_ok=True)

        # Generate a unique filename for the uploaded image
        filename = f"{document_type}_{os.urandom(8).hex()}.jpg"
        file_path = os.path.join(image_folder, filename)

        # Save the uploaded file to disk
        with open(file_path, "wb") as f:
            f.write(uploaded_file.read())

        if document_type == 'identity_card':
            # Process identity card
            return process_identity_card(file_path)
        elif document_type == 'drivers_license':
            # Process driver's license using EasyOCR
            return process_drivers_license(file_path)

    except Exception as e:
        logger.error(f"Error processing uploaded {document_type}: {e}")
        return None





# Function to parse the extracted text from the identity card
def parse_extracted_text(extracted_text):
    # Initialize a dictionary to hold the parsed data
    parsed_data = {
        'Identity_Card_No': None,
        'Name': None,
        'Race': None,
        'Date_of_birth': None,
        'Sex': None,
        'Place_of_birth': None
    }
    
    # Regular expressions to capture the different fields
    id_card_no_pattern = re.compile(r'IDENTITY CARD No\.?\s*([A-Z0-9]+)')
    name_pattern = re.compile(r'Name\s*([\w\s\(\)]+)')
    race_pattern = re.compile(r'Race\s*(\w+)')
    dob_pattern = re.compile(r'Date of birth\s*(\d{2}-\d{2}-\d{4})')
    sex_pattern = re.compile(r'Sex\s*([MF])')
    pob_pattern = re.compile(r'Country/Place of birth\s*(\w+)')

    # Extract data using regex
    id_card_match = id_card_no_pattern.search(extracted_text)
    name_match = name_pattern.search(extracted_text)
    race_match = race_pattern.search(extracted_text)
    dob_match = dob_pattern.search(extracted_text)
    sex_match = sex_pattern.search(extracted_text)
    pob_match = pob_pattern.search(extracted_text)
    
    if id_card_match:
        parsed_data['Identity_Card_No'] = id_card_match.group(1)
    if name_match:
        parsed_data['Name'] = name_match.group(1).strip()
    if race_match:
        parsed_data['Race'] = race_match.group(1).strip()
    if dob_match:
        parsed_data['Date_of_birth'] = dob_match.group(1)
    if sex_match:
        parsed_data['Sex'] = sex_match.group(1)
    if pob_match:
        parsed_data['Place_of_birth'] = pob_match.group(1)

    return parsed_data

# Function to process the identity card and save to Firestore
def process_identity_card(image_path):
    # Extract text from the saved image
    extracted_text = extract_text_from_image(image_path)

    if extracted_text:
        logger.info("Text successfully extracted from the uploaded identity card.")
        
        # Parse the extracted text to structured data
        parsed_data = parse_extracted_text(extracted_text)
        
        # Get the Name from the parsed data
        name = parsed_data.get('Name')
        if not name:
            logger.error("Failed to find a valid Name in the parsed data.")
            return None

        # Sanitize the name to use it as Firestore document ID (optional: remove special characters)
        sanitized_name = name.replace(" ", "_").lower()  # Example: "John Doe" -> "john_doe"

        # Initialize Firestore database
        db = initialize_firestore()
        
        # Prepare Firestore document data
        doc_data = {
            'Identity_Card_No': parsed_data['Identity_Card_No'],
            'Name': parsed_data['Name'],
            'Race': parsed_data['Race'],
            'Date_of_birth': parsed_data['Date_of_birth'],
            'Sex': parsed_data['Sex'],
            'Place_of_birth': parsed_data['Place_of_birth'],
            'timestamp': firestore.SERVER_TIMESTAMP,
            'image_path': image_path  # Optional: Storing the image path if needed
        }

        # Save to Firestore {sanitized_name}/identity_card collection
        try:
            # Create a document using the sanitized name in a root collection with a sub-collection `identity_card`
            doc_ref = db.collection(sanitized_name).document('identity_card')
            doc_ref.set(doc_data)
            logger.info(f"Parsed data successfully saved to Firestore as /{sanitized_name}/identity_card.")
        except Exception as e:
            logger.error(f"Failed to save parsed data to Firestore: {e}")
            return None  # Return None if saving fails

        return parsed_data  # Return the parsed data after saving to Firestore
    else:
        logger.error("Failed to extract text from the uploaded identity card.")
        return None

@app.route('/upload_document', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    document_type = request.form.get('document_type', 'identity_card')  # Default to identity card if not specified
    if file.filename == '':
        return 'No selected file', 400
    if file:
        extracted_data = process_uploaded_document(file, document_type)
        if extracted_data:
            return extracted_data, 200
        else:
            return 'Failed to process image', 500

if __name__ == '__main__':
    app.run(debug=True)
