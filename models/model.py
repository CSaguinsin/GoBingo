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

def process_uploaded_identity_card(uploaded_file):
    try:
        # Create image_folder if it doesn't exist
        image_folder = os.path.join(os.getcwd(), 'image_folder')
        os.makedirs(image_folder, exist_ok=True)

        # Generate a unique filename
        filename = f"identity_card_{os.urandom(8).hex()}.jpg"
        file_path = os.path.join(image_folder, filename)

        # Save the uploaded file
        with open(file_path, "wb") as f:
            f.write(uploaded_file.read())

        # Extract text from the saved image
        extracted_text = extract_text_from_image(file_path)

        if extracted_text:
            logger.info("Text successfully extracted from uploaded identity card.")
            return extracted_text
        else:
            logger.error("Failed to extract text from uploaded identity card.")
            return None

    except Exception as e:
        logger.error(f"Error processing uploaded identity card: {e}")
        return None

@app.route('/upload_identity_card', methods=['POST'])
def upload_identity_card():
    if 'file' not in request.files:
        return 'No file part', 400
    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400
    if file:
        extracted_text = process_uploaded_identity_card(file)
        if extracted_text:
            return extracted_text, 200
        else:
            return 'Failed to process image', 500

if __name__ == '__main__':
    app.run(debug=True)