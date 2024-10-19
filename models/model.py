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
from google.cloud.exceptions import GoogleCloudError



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

# ss
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



identitycard_name = {}

def process_identity_card(image_path, user_id):
    # Extract text from the saved image
    extracted_text = extract_text_from_image(image_path)

    if extracted_text:
        logger.info("Text successfully extracted from the uploaded identity card.")

        # Parse the extracted text to structured data
        parsed_data = parse_extracted_text(extracted_text)

        if not parsed_data:
            logger.error("Parsed data is empty. Unable to process identity card.")
            return None

        # Get the Name from the parsed data
        name = parsed_data.get('Name', 'Unknown')  # Default to 'Unknown' if missing

        # Sanitize the name by removing unwanted characters (newlines, parentheses, etc.)
        sanitized_name = re.sub(r'[^\w\s]', '', name)  # Remove special characters (except spaces)
        sanitized_name = sanitized_name.replace("\n", " ").replace("\r", " ").strip()  # Replace newlines with spaces and trim
        sanitized_name = sanitized_name.replace(" ", "_").lower()  # Convert to lowercase and replace spaces with underscores

        logger.info(f"Sanitized name generated: {sanitized_name}")

        # Store the sanitized name in the global dictionary using user_id as key
        identitycard_name[user_id] = sanitized_name

        # Prepare Firestore document data
        doc_data = {
            'Identity_Card_No': parsed_data.get('Identity_Card_No', 'Unknown'),
            'Race': parsed_data.get('Race', "Unknown"),
            'Date_of_birth': parsed_data.get('Date_of_birth', "Unknown"),
            'Sex': parsed_data.get('Sex', "Unknown"),
            'Place_of_birth': parsed_data.get('Place_of_birth', "Unknown"),
            'sanitized_name': sanitized_name,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'image_path': image_path
        }
        filtered_doc_data = {k: v for k, v in doc_data.items() if v is not None}

        try:
            # Save the identity card data to Firestore
            db = initialize_firestore()
            doc_ref = db.collection('policy_holders').document(sanitized_name)
            doc_ref.set(filtered_doc_data)

            logger.info(f"Identity Card data successfully saved to Firestore under policy_holders/{sanitized_name}.")
        
        except Exception as e:
            logger.error(f"Failed to save identity card data to Firestore: {e}")
            return None

        # Now update the `data_into_monday` for this user
        if sanitized_name not in data_into_monday:
            data_into_monday[sanitized_name] = {}

        data_into_monday[sanitized_name].update({
            'sanitized_name': sanitized_name,
            'Identity_Card_No': parsed_data.get('Identity_Card_No', 'Unknown'),
            'Race': parsed_data.get('Race', 'Unknown'),
            'Date_of_birth': parsed_data.get('Date_of_birth', 'Unknown'),
            'Sex': parsed_data.get('Sex', 'Unknown'),
            'Place_of_birth': parsed_data.get('Place_of_birth', 'Unknown')
        })

        logger.info(f"Identity card data for {sanitized_name} added to data_into_monday.")

        # Check if all required documents are processed and send data to Monday
        check_and_send_to_monday(sanitized_name)

        # Return the document data as a dictionary
        return filtered_doc_data
    else:
        logger.error("Failed to extract text from the image.")
        return None

def process_drivers_license(image_path, sanitized_name):
    try:
        logger.info(f"Processing driver's license for sanitized_name: {sanitized_name}")

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
        json_result = convert_to_json(result)
        logger.info(f"OCR Result for Driver's License: {json_result}")

        # Extract relevant fields from the OCR result (as much as possible)
        license_data = extract_drivers_license_data(result)

        # Prepare Firestore document data for the driver's license
        doc_data = {
            'License_Number': license_data.get('License_Number', 'Unknown'),
            'Birth_Date': license_data.get('Birth_Date'),
            'Issue_Date': license_data.get('Issue_Date'),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'image_path': image_path
        }
        filtered_doc_data = {k: v for k, v in doc_data.items() if v is not None}
        try:
            # Save the driver's license data to Firestore
            db = initialize_firestore()
            doc_ref = db.collection('policy_holders').document(sanitized_name)

            # Save the driver's license data in the `drivers_license` subcollection
            subcollection_ref = doc_ref.collection('drivers_license').document()
            subcollection_ref.set(filtered_doc_data)

            logger.info(f"Driver's License data successfully saved to Firestore under policy_holders/{sanitized_name}/drivers_license.")

        except Exception as e:
            logger.error(f"Failed to save driver's license data to Firestore: {e}")
            return None

        # Update the `data_into_monday` for this user
        if sanitized_name not in data_into_monday:
            data_into_monday[sanitized_name] = {}

        data_into_monday[sanitized_name].update({
            'License_Number': license_data.get('License_Number', 'Unknown'),
            'Birth_Date': license_data.get('Birth_Date', 'Unknown'),
            'Issue_Date': license_data.get('Issue_Date', 'Unknown')
        })

        logger.info(f"Driver's license data for {sanitized_name} added to data_into_monday.")

        # Check if all required documents are processed and send data to Monday
        check_and_send_to_monday(sanitized_name)

        return license_data

    except Exception as e:
        logger.error(f"Failed to process driver's license: {e}")
        return None



 # Function to fetch the sanitized_name from Firestore based on user_id or other identifier
def fetch_sanitized_name_from_firestore(user_id):
    try:
        # Initialize Firestore database
        db = initialize_firestore()
        # Assuming you store the sanitized_name under the user's document or another collection
        doc_ref = db.collection('users').document(user_id)  # Replace 'users' with your collection

        # Fetch the document
        doc = doc_ref.get()

        if doc.exists:
            # Assuming the sanitized_name is stored in the document fields
            return doc.to_dict().get('sanitized_name')
        else:
            logger.error(f"No document found for user_id: {user_id}")
            return None

    except Exception as e:
        logger.error(f"Failed to fetch sanitized_name from Firestore: {e}")
        return None


def extract_drivers_license_data(ocr_result):
    license_data = {
        'License_Number': None,
        'Name': None,
        'Birth_Date': None,
        'Issue_Date': None
    }

    # Iterate through the OCR results to find relevant fields
    for entry in ocr_result:
        # Access the detected text from the tuple (entry[1] is the text)
        text = entry[1].strip()  # entry[1] contains the text in the OCR result
        
        # Match the License Number (e.g., "S7120710 B")
        if re.match(r'[A-Z0-9]{7,}', text):  # Adjust regex to allow 7+ alphanumeric characters
            license_data['License_Number'] = text
        
        # Match the Name (e.g., "CHAN LEONG FEI") - adjust if more specific patterns are needed
        if re.match(r'[A-Z\s\(\)]+', text) and not license_data['Name']:  # Match uppercase names
            license_data['Name'] = text
        
        # Match the Birth Date (e.g., "Birth Date: 22 Jun 1971" or variations)
        if 'Birth Date' in text or 'Birthdate' in text or 'Date of Birth' in text:
            license_data['Birth_Date'] = re.sub(r'(Birth Date:|Birthdate:|Date of Birth:)', '', text).strip()
        
        # Match the Issue Date (e.g., "Issue Date: 27 Nov 2003")
        if 'Issue Date' in text:
            license_data['Issue_Date'] = text.replace('Issue Date: ', '').strip()

    return license_data


def process_uploaded_document(uploaded_file, document_type, user_id=None, sanitized_name=None):
    """
    This function processes an uploaded document, stores the data in Firestore, 
    and adds the sanitized data to the global dictionary for Monday.com.
    """
    try:
        # Validate document type
        if document_type not in ['identity_card', 'drivers_license', 'log_card']:
            logger.error(f"Unsupported document type: {document_type}")
            return None

        # Create 'image_folder' if it doesn't exist
        image_folder = os.path.join(os.getcwd(), 'image_folder')
        os.makedirs(image_folder, exist_ok=True)

        # Generate a unique filename for the uploaded image
        filename = f"{document_type}_{os.urandom(8).hex()}.jpg"
        file_path = os.path.join(image_folder, filename)

        # File handling: Save file or use existing path
        if hasattr(uploaded_file, 'read'):  # It's a file-like object
            with open(file_path, "wb") as f:
                f.write(uploaded_file.read())
            logger.info(f"Saved file to {file_path}")
        else:
            if not os.path.exists(uploaded_file):
                logger.error(f"File path does not exist: {uploaded_file}")
                return None
            file_path = uploaded_file  # Use the provided file path directly
            logger.info(f"Using existing file at {file_path}")

        # Initialize variables to store extracted data
        identity_data = None
        drivers_license_data = None
        log_card_data = None

        # Process the identity card
        if document_type == 'identity_card':
            identity_data = process_identity_card(file_path, user_id)  # Process the identity card
            if identity_data and 'sanitized_name' in identity_data:
                sanitized_name = identity_data['sanitized_name']  # Store sanitized name in memory
                identitycard_name[user_id] = sanitized_name  # Store for future use
            else:
                logger.error("Failed to extract sanitized name from identity card.")
                return None

        # Process the driver's license
        elif document_type == 'drivers_license':
            if not sanitized_name:
                logger.error("Cannot process driver's license without sanitized name.")
                return None

            # Process the driver's license using the sanitized name
            drivers_license_data = process_drivers_license(file_path, sanitized_name)

        # Process the log card
        elif document_type == 'log_card':
            if not sanitized_name:
                logger.error("Cannot process log card without sanitized name.")
                return None

            # Process the log card using the sanitized name
            log_card_data = process_log_card(file_path, sanitized_name)

        # Check if the result is valid
        if isinstance(identity_data, dict) or isinstance(drivers_license_data, dict) or isinstance(log_card_data, dict):
            # Combine and sanitize data from all documents and store in the global dictionary
            sanitized_data = sanitize_and_store_data(
                user_data=user_id,
                identity_data=identity_data,
                drivers_license_data=drivers_license_data,
                log_card_data=log_card_data
            )

            logger.info(f"Sanitized data stored for user {user_id}.")

            # Keep the original Firestore logic intact, saving the document data to Firestore
            # This logic should not be altered to ensure data is still saved in Firestore as intended.
            if document_type == 'identity_card' and identity_data:
                try:
                    db = initialize_firestore()
                    doc_ref = db.collection('policy_holders').document(sanitized_name)
                    doc_ref.set(identity_data)  # Save identity card data to Firestore
                    logger.info(f"Identity Card data successfully saved to Firestore under policy_holders/{sanitized_name}.")
                except Exception as e:
                    logger.error(f"Failed to save identity card data to Firestore: {e}")

            elif document_type == 'drivers_license' and drivers_license_data:
                try:
                    db = initialize_firestore()
                    doc_ref = db.collection('policy_holders').document(sanitized_name)
                    subcollection_ref = doc_ref.collection('drivers_license').document()
                    subcollection_ref.set(drivers_license_data)  # Save driver's license data to Firestore
                    logger.info(f"Driver's License data successfully saved to Firestore under policy_holders/{sanitized_name}/drivers_license.")
                except Exception as e:
                    logger.error(f"Failed to save driver's license data to Firestore: {e}")

            elif document_type == 'log_card' and log_card_data:
                try:
                    db = initialize_firestore()
                    doc_ref = db.collection('policy_holders').document(sanitized_name)
                    subcollection_ref = doc_ref.collection('log_card').document()
                    subcollection_ref.set(log_card_data)  # Save log card data to Firestore
                    logger.info(f"Log Card data successfully saved to Firestore under policy_holders/{sanitized_name}/log_card.")
                except Exception as e:
                    logger.error(f"Failed to save log card data to Firestore: {e}")

            return sanitized_data  # Return the sanitized data after processing

        else:
            logger.error(f"Unexpected result format from {document_type} processing.")
            return None

    except Exception as e:
        logger.error(f"Error processing uploaded {document_type}: {e}")
        return None


# Function to parse the extracted text from identity card
def parse_extracted_text(extracted_text):
    parsed_data = {}

    try:
        # Extract Identity Card No (assume it's a combination of letters and digits)
        id_card_no_match = re.search(r'IDENTITY CARD No\.\s*([A-Z0-9]+)', extracted_text, re.IGNORECASE)
        if id_card_no_match:
            parsed_data['Identity_Card_No'] = id_card_no_match.group(1)
        else:
            logger.warning("Identity Card No. not found in the extracted text.")

        # Extract Name (assume it's the line following "Name")
        name_match = re.search(r'Name\s*([A-Z\s\(\)]+)', extracted_text, re.IGNORECASE)
        if name_match:
            # Extract the name and sanitize
            name = name_match.group(1).strip()

            # Remove any text in parentheses (e.g., "(Chen Lianghui)")
            name = re.sub(r'\(.*?\)', '', name).strip()

            # Remove any extra exclamation marks or unwanted symbols
            name = name.replace('!', '').strip()

            # Ensure only the name is captured, not extra text
            parsed_data['Name'] = name
        else:
            logger.warning("Name not found in the extracted text.")

        # Extract Race (assume it's the line following "Race")
        race_match = re.search(r'Race\s*([A-Z]+)', extracted_text, re.IGNORECASE)
        if race_match:
            parsed_data['Race'] = race_match.group(1).strip()
        else:
            logger.warning("Race not found in the extracted text.")

        # Extract Date of Birth (assume it's in the format DD-MM-YYYY)
        dob_match = re.search(r'Date of birth\s*([\d-]+)', extracted_text, re.IGNORECASE)
        if dob_match:
            parsed_data['Date_of_birth'] = dob_match.group(1).strip()
        else:
            logger.warning("Date of birth not found in the extracted text.")

        # Extract Sex (assume it's either M or F)
        sex_match = re.search(r'Sex\s*([MF])', extracted_text, re.IGNORECASE)
        if sex_match:
            parsed_data['Sex'] = sex_match.group(1).strip()
        else:
            logger.warning("Sex not found in the extracted text.")

        # Extract Country/Place of Birth (assume it's the line following "Country/Place of birth")
        place_of_birth_match = re.search(r'Country/Place of birth\s*([A-Z\s]+)', extracted_text, re.IGNORECASE)
        if place_of_birth_match:
            parsed_data['Place_of_birth'] = place_of_birth_match.group(1).strip()
        else:
            logger.warning("Place of birth not found in the extracted text.")

    except Exception as e:
        logger.error(f"Error parsing extracted text: {e}")
    
    return parsed_data


def process_log_card(image_path, sanitized_name):
    # Extract text from the saved image using OCR
    extracted_text = extract_text_from_image(image_path)
    
    if extracted_text:
        logger.debug(f"Extracted text from log card: {extracted_text}")  # Log the raw extracted text only in debug

        # Parse the extracted text to structured data
        parsed_data = parse_log_card_text(extracted_text)
        
        logger.info(f"Parsed log card data: {parsed_data}")  # Log the parsed data
        
        # Prepare Firestore document data
        log_card_data = {
            'Vehicle_No': parsed_data.get('Vehicle_No', 'Unknown'),
            'Vehicle_Type': parsed_data.get('Vehicle_Type', 'Unknown'),
            'Make_Model': parsed_data.get('Make_Model', 'Unknown'),
            'Year_of_Manufacture': parsed_data.get('Year_of_Manufacture', None),
            'Chassis_No': parsed_data.get('Chassis_No', None),
            'Engine_No': parsed_data.get('Engine_No', None),
            'Engine_Capacity': parsed_data.get('Engine_Capacity', None),
            'Road_Tax_Expiry_Date': parsed_data.get('Road_Tax_Expiry_Date', None),
            'COE_Expiry_Date': parsed_data.get('COE_Expiry_Date', None),
            'Original_Registration_Date': parsed_data.get('Original_Registration_Date', None),
            'Lifespan_Expiry_Date': parsed_data.get('Lifespan_Expiry_Date', None),
            'Inspection_Due_Date': parsed_data.get('Inspection_Due_Date', None),
            'PQP_Paid': parsed_data.get('PQP_Paid', None),
            'Intended_Transfer_Date': parsed_data.get('Intended_Transfer_Date', None),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'image_path': image_path  # Store the image path if needed
        }
        filtered_log_card_data = {k: v for k, v in log_card_data.items() if v is not None}

        try:
            # Initialize Firestore and reference the user's log_card subcollection
            db = initialize_firestore()
            doc_ref = db.collection('policy_holders').document(sanitized_name)

            # Save the log card data in the `log_card` subcollection
            subcollection_ref = doc_ref.collection('log_card').document()  # Auto-generate a document ID
            subcollection_ref.set(filtered_log_card_data)

            logger.info(f"Log card data successfully saved to Firestore under policy_holders/{sanitized_name}/log_card.")

        except Exception as e:
            logger.error(f"Failed to save log card data to Firestore: {e}")
            return None

        # Update the `data_into_monday` for this user
        if sanitized_name not in data_into_monday:
            data_into_monday[sanitized_name] = {}

        data_into_monday[sanitized_name].update({
            'Vehicle_No': parsed_data.get('Vehicle_No', 'Unknown'),
            'Vehicle_Type': parsed_data.get('Vehicle_Type', 'Unknown'),
            'Make_Model': parsed_data.get('Make_Model', 'Unknown'),
            'Year_of_Manufacture': parsed_data.get('Year_of_Manufacture', 'Unknown')
        })

        logger.info(f"Log card data for {sanitized_name} added to data_into_monday.")

        # Check if all required documents are processed and send data to Monday
        check_and_send_to_monday(sanitized_name)

        return parsed_data

    else:
        logger.error("Failed to extract text from the uploaded log card.")
        return None




def parse_log_card_text(extracted_text):
    """
    Parse the extracted text from the log card and return structured data.
    """
    # Initialize a dictionary to hold the parsed data
    log_card_data = {
        'Vehicle_No': None,
        'Vehicle_Type': None,
        'Make_Model': None,
        'Year_of_Manufacture': None,
        'Chassis_No': None,
        'Engine_No': None,
        'Engine_Capacity': None,
        'Road_Tax_Expiry_Date': None,
        'COE_Expiry_Date': None,
        'Original_Registration_Date': None,
        'Lifespan_Expiry_Date': None,
        'PQP_Paid': None,
        'Inspection_Due_Date': None,
        'Intended_Transfer_Date': None
    }

    # Regular expressions to capture log card fields
    vehicle_no_pattern = re.compile(r'Vehicle No\.\s*([A-Z0-9]+)')
    vehicle_type_pattern = re.compile(r'Vehicle Type:\s*([\w\s\/\-]+)')
    make_model_pattern = re.compile(r'Make\s*\/\s*Model\s*([\w\s\/\.]+)')
    year_of_manufacture_pattern = re.compile(r'Year Of Manufacture:\s*(\d{4})')
    chassis_no_pattern = re.compile(r'Chassis No\.\s*([A-Z0-9]+)')
    engine_no_pattern = re.compile(r'Engine No\.\s*([A-Z0-9]+)')
    engine_capacity_pattern = re.compile(r'Engine Capacity\s*:\s*(\d+\s*cc)')
    road_tax_expiry_pattern = re.compile(r'Road Tax Expiry Date:\s*([\d\s\w]+)')
    coe_expiry_pattern = re.compile(r'COE Expiry Date:\s*([\d\s\w]+)')
    original_reg_date_pattern = re.compile(r'Original Registration Date:\s*([\d\s\w]+)')
    lifespan_expiry_pattern = re.compile(r'Lifespan Expiry Date:\s*([\d\s\w]*)')
    pqp_paid_pattern = re.compile(r'PQP Paid:\s*\$(\S+)')
    inspection_due_date_pattern = re.compile(r'Inspection Due Date:\s*([\d\s\w]+)')
    intended_transfer_date_pattern = re.compile(r'Intended Transfer Date:\s*([\d\s\w]+)')

    # Extract data using regex
    vehicle_no_match = vehicle_no_pattern.search(extracted_text)
    vehicle_type_match = vehicle_type_pattern.search(extracted_text)
    make_model_match = make_model_pattern.search(extracted_text)
    year_of_manufacture_match = year_of_manufacture_pattern.search(extracted_text)
    chassis_no_match = chassis_no_pattern.search(extracted_text)
    engine_no_match = engine_no_pattern.search(extracted_text)
    engine_capacity_match = engine_capacity_pattern.search(extracted_text)
    road_tax_expiry_match = road_tax_expiry_pattern.search(extracted_text)
    coe_expiry_match = coe_expiry_pattern.search(extracted_text)
    original_reg_date_match = original_reg_date_pattern.search(extracted_text)
    lifespan_expiry_match = lifespan_expiry_pattern.search(extracted_text)
    pqp_paid_match = pqp_paid_pattern.search(extracted_text)
    inspection_due_date_match = inspection_due_date_pattern.search(extracted_text)
    intended_transfer_date_match = intended_transfer_date_pattern.search(extracted_text)

    # Store extracted data in the dictionary
    if vehicle_no_match:
        log_card_data['Vehicle_No'] = vehicle_no_match.group(1)
    if vehicle_type_match:
        log_card_data['Vehicle_Type'] = vehicle_type_match.group(1).strip()
    if make_model_match:
        log_card_data['Make_Model'] = make_model_match.group(1).strip()
    if year_of_manufacture_match:
        log_card_data['Year_of_Manufacture'] = year_of_manufacture_match.group(1)
    if chassis_no_match:
        log_card_data['Chassis_No'] = chassis_no_match.group(1)
    if engine_no_match:
        log_card_data['Engine_No'] = engine_no_match.group(1)
    if engine_capacity_match:
        log_card_data['Engine_Capacity'] = engine_capacity_match.group(1)
    if road_tax_expiry_match:
        log_card_data['Road_Tax_Expiry_Date'] = road_tax_expiry_match.group(1).strip()
    if coe_expiry_match:
        log_card_data['COE_Expiry_Date'] = coe_expiry_match.group(1).strip()
    if original_reg_date_match:
        log_card_data['Original_Registration_Date'] = original_reg_date_match.group(1).strip()
    if lifespan_expiry_match and lifespan_expiry_match.group(1):
        log_card_data['Lifespan_Expiry_Date'] = lifespan_expiry_match.group(1).strip()
    if pqp_paid_match:
        log_card_data['PQP_Paid'] = pqp_paid_match.group(1)
    if inspection_due_date_match:
        log_card_data['Inspection_Due_Date'] = inspection_due_date_match.group(1).strip()
    if intended_transfer_date_match:
        log_card_data['Intended_Transfer_Date'] = intended_transfer_date_match.group(1).strip()

    return log_card_data


def get_user_id_from_firestore(name):
    """
    Function to retrieve the user_id from Firestore using the user's name.
    """
    # Initialize Firestore database
    db = initialize_firestore()

    # Search for the user in Firestore based on their name
    try:
        policy_holders_ref = db.collection('policy_holders')
        query = policy_holders_ref.where('Name', '==', name).get()

        # Assuming the query will return only one result; adjust if multiple results are possible
        for doc in query:
            user_data = doc.to_dict()
            print(f"Found user data: {user_data}")  # Debugging output
            return doc.id  # Return the Firestore document ID (this is the user_id)

        logger.error(f"User with name {name} not found in Firestore.")
        return None  # Return None if no user is found

    except Exception as e:
        logger.error(f"Error retrieving user_id from Firestore: {e}")
        return None
    



# Monday board columns ID's
FULL_NAME = "text9"
AGENT_CONTACT_NUMBER = "phone0"
DEALERSHIP_COLUMN_ID = "text3"
CONTACT_INFO_COLUMN_ID = "phone"

OWNER_ID = "text78"
OWNER_ID_TYPE = "text"
CONTACT_NUMBER = "phone"
ORIGINAL_REGISTRATION_DATA = "date8"
VEHICLE_MODEL = "text6"
VEHICLE_MAKE = "text2"
ENGINE_NUMBER = "engine_number"
VEHICLE_NO = "text1"
CHASSIS_NO = "text775"

# Global dictionary to store sanitized data for Monday.com
data_into_monday = {}


MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
POLICY_BOARD_ID = os.getenv('POLICY_BOARD_ID')


def send_data_to_monday(sanitized_data):
    """
    Send the sanitized data to a Monday.com board using the provided column IDs.
    Consolidates data from identity cards, driver's licenses, and log cards into one request.
    """
    if not POLICY_BOARD_ID:
        logger.error("POLICY_BOARD_ID not set. Cannot send data to Monday.com.")
        return False

    if not MONDAY_API_TOKEN:
        logger.error("MONDAY_API_TOKEN not set. Cannot authenticate to Monday.com.")
        return False

    # Define the Monday.com API endpoint
    monday_api_url = "https://api.monday.com/v2"

    # Prepare the headers for the request
    headers = {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json"
    }

    # Extract the sanitized name for the item name (if available)
    item_name = sanitized_data.get('sanitized_name', 'Unnamed Policy Holder')

    # Construct the column values in the format required by Monday.com
    # Ensure proper escaping and handling of None values
    column_values = {
        FULL_NAME: sanitized_data.get("sanitized_name", "Unknown"),  # Full Name
        AGENT_CONTACT_NUMBER: sanitized_data.get("Agent_Contact_Number", ""),  # Agent Contact Number
        DEALERSHIP_COLUMN_ID: sanitized_data.get("Dealership", ""),  # Dealership
        CONTACT_INFO_COLUMN_ID: sanitized_data.get("Contact_Info", ""),  # Contact Info
        OWNER_ID: sanitized_data.get("Identity_Card_No", "Unknown"),  # Owner ID
        OWNER_ID_TYPE: sanitized_data.get("Identity_Card_Type", "Unknown"),  # Owner ID Type (e.g., Identity card, driver's license)
        CONTACT_NUMBER: sanitized_data.get("Contact_Number", ""),  # Contact Number
        ORIGINAL_REGISTRATION_DATA: sanitized_data.get("Original_Registration_Date", ""),  # Original Registration Date (for vehicle documents)
        VEHICLE_MODEL: sanitized_data.get("Make_Model", "Unknown"),  # Vehicle Model
        VEHICLE_MAKE: sanitized_data.get("Vehicle_Type", "Unknown"),  # Vehicle Make
        ENGINE_NUMBER: sanitized_data.get("Engine_No", "Unknown"),  # Engine Number
        VEHICLE_NO: sanitized_data.get("Vehicle_No", "Unknown"),  # Vehicle No
        CHASSIS_NO: sanitized_data.get("Chassis_No", "Unknown")  # Chassis No
    }

    # Filter out empty or None values from column_values
    filtered_column_values = {k: v for k, v in column_values.items() if v}

    # Serialize column_values to JSON string
    column_values_json = json.dumps(filtered_column_values).replace('"', '\\"')  # Escape double quotes

    # Construct the GraphQL mutation
    query = f"""
    mutation {{
        create_item(board_id: {POLICY_BOARD_ID}, item_name: "{item_name}", column_values: "{column_values_json}") {{
            id
        }}
    }}
    """

    # Send the request to Monday.com API
    try:
        response = requests.post(monday_api_url, json={'query': query}, headers=headers)

        # Check the response status
        if response.status_code == 200:
            logger.info(f"Data successfully sent to Monday.com for {item_name}.")
            return True
        else:
            logger.error(f"Failed to send data to Monday.com: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error sending data to Monday.com: {e}")
        return False





def sanitize_and_store_data(user_data, identity_data=None, drivers_license_data=None, log_card_data=None):
    """
    Sanitize and store data from different document types (identity card, driver's license, log card).
    """
    sanitized_data = {}

    if identity_data:
        sanitized_data.update({
            "sanitized_name": identity_data.get('sanitized_name', 'Unknown'),
            "Identity_Card_No": identity_data.get('Identity_Card_No', 'Unknown'),
            "Race": identity_data.get('Race', 'Unknown'),
            "Date_of_birth": identity_data.get('Date_of_birth', 'Unknown'),
            # Add more fields as needed
        })

    if drivers_license_data:
        sanitized_data.update({
            "License_Number": drivers_license_data.get('License_Number', 'Unknown'),
            "Birth_Date": drivers_license_data.get('Birth_Date', 'Unknown'),
            "Issue_Date": drivers_license_data.get('Issue_Date', 'Unknown'),
            # Add more fields as needed
        })

    if log_card_data:
        sanitized_data.update({
            "Vehicle_No": log_card_data.get('Vehicle_No', 'Unknown'),
            "Vehicle_Type": log_card_data.get('Vehicle_Type', 'Unknown'),
            "Make_Model": log_card_data.get('Make_Model', 'Unknown'),
            # Add more fields as needed
        })

    # Store sanitized data in the global dictionary
    data_into_monday[user_data] = sanitized_data
    logger.info(f"Sanitized data for user {user_data} stored in the global dictionary.")

    # Step 4: Send the sanitized data to Monday.com board
    result = send_data_to_monday(sanitized_data)

    if result:
        logger.info(f"Sanitized data for {user_data} successfully sent to Monday.com.")
    else:
        logger.error(f"Failed to send sanitized data for {user_data} to Monday.com.")

    return sanitized_data


def check_and_send_to_monday(sanitized_name):
    """
    Check if all documents (identity card, driver's license, log card) have been processed for the user.
    If so, send the consolidated data to Monday.com.
    """
    user_data = data_into_monday.get(sanitized_name, {})

    # Check if all required fields from all documents are available
    if all(key in user_data for key in ['Identity_Card_No', 'License_Number', 'Vehicle_No']):
        logger.info(f"All data ready for {sanitized_name}. Sending to Monday.com.")
        
        # Call the function to sanitize and send data to Monday
        sanitize_and_store_data(sanitized_name, identity_data=user_data)

        # Optionally clear the data for this user after sending
        del data_into_monday[sanitized_name]
    else:
        logger.info(f"Waiting for more data for {sanitized_name}. Not all documents have been processed yet.")




# Modify the /upload_document route to handle log card processing
@app.route('/upload_document', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return 'No file part', 400

    file = request.files['file']
    document_type = request.form.get('document_type', 'identity_card')  # Default to identity card if not specified
    sanitized_name = request.form.get('sanitized_name')  # Retrieve sanitized_name from the form

    if file.filename == '':
        return 'No selected file', 400

    if file:
        extracted_data = process_uploaded_document(file, document_type, sanitized_name)
        
        if extracted_data:
            if document_type == 'identity_card':
                # Store sanitized_name for subsequent uploads (driver's license, log card)
                sanitized_name = extracted_data.get('sanitized_name')

                # Ask for driver's license next
                return {
                    'message': 'Identity card processed. Please upload the driver\'s license.',
                    'sanitized_name': sanitized_name  # Pass sanitized_name back to the client
                }, 200

            elif document_type == 'drivers_license':
                return {
                    'message': 'Driver\'s license processed. Please upload the log card.',
                    'sanitized_name': sanitized_name  # Pass sanitized_name back to the client
                }, 200

            elif document_type == 'log_card':
                return {
                    'message': 'Log card processed successfully!',
                    'extracted_data': extracted_data
                }, 200
        else:
            return 'Failed to process image', 500


if __name__ == '__main__':
    app.run(debug=True)
    
    
    

