import os
import logging
from dotenv import load_dotenv  # For environment variables
import requests  # For AI model API requests
from fpdf import FPDF  # For PDF creation
from PIL import Image  # For image manipulation and legit PDF generation

load_dotenv()  # Load environment variables from .env file

logger = logging.getLogger(__name__)

# Get the AI model endpoint from environment variables
AI_MODEL_ENDPOINT = os.getenv('AI_MODEL_ENDPOINT')

# Create a folder to store PDFs if it doesn't exist
PDF_FOLDER = os.path.join(os.getcwd(), 'pdf_folder')
os.makedirs(PDF_FOLDER, exist_ok=True)

# Function to extract text from a PDF using the AI model
def extract_text_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as pdf_file:
            files = {'file': (os.path.basename(pdf_path), pdf_file, 'application/pdf')}
            response = requests.post(AI_MODEL_ENDPOINT, files=files)

        if response.status_code == 200:
            extracted_data = response.json()
            logger.info(f"Raw AI Model Response: {extracted_data}")

            # Return the extracted data
            return extracted_data
        else:
            logger.error(f"Failed to extract text from {pdf_path}: {response.status_code} {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error during PDF text extraction for {pdf_path}: {e}")
        return None

# Function to create a selectable, legit PDF from an image
def create_selectable_pdf_from_image(image_path, pdf_name):
    try:
        # Ensure the PDF will be saved in the pdf_folder
        pdf_path = os.path.join(PDF_FOLDER, pdf_name)

        # Open the image file
        image = Image.open(image_path)
        pdf = FPDF()
        pdf.add_page()

        # Set up A4 page size in mm (210 x 297)
        pdf_w, pdf_h = 210, 297
        image_w, image_h = image.size
        aspect_ratio = image_h / image_w

        # Set width within A4 page margins
        new_width = 190
        new_height = new_width * aspect_ratio

        # Ensure the image is in RGB mode
        image = image.convert('RGB')
        
        # Add the image to the PDF
        pdf.image(image_path, x=10, y=10, w=new_width, h=new_height)
        
        # Output the PDF
        pdf.output(pdf_path)
        logger.info(f"Created a legitimate PDF at {pdf_path}")
    except Exception as e:
        logger.error(f"Failed to create a legitimate PDF from image: {e}")
