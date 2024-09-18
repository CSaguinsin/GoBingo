import os
import logging
from dotenv import load_dotenv
import requests
from fpdf import FPDF
from PIL import Image
import pytesseract

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
FONT_PATH = '/Users/carlsaginsin/Projects/BingoTelegram/fonts/DejaVuSansCondensed.ttf'

# Class for handling Unicode characters in PDFs using DejaVuSansCondensed.ttf
class UTF8FPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Add the DejaVuSansCondensed font
        self.add_font('DejaVu', '', FONT_PATH, uni=True)

# Function to create a selectable PDF from an image with OCR text extraction
def create_selectable_pdf_from_image(image_path, pdf_name):
    try:
        # Ensure the PDF will be saved in the pdf_folder
        pdf_path = os.path.join(PDF_FOLDER, pdf_name)

        # Open the image file
        image = Image.open(image_path)
        logger.info(f"Opened image: {image_path}, size: {image.size}")

        # Perform OCR to extract text from the image
        text = pytesseract.image_to_string(image)
        logger.info(f"Extracted text from image: {text}")

        # Create a PDF using the Unicode-compatible class
        pdf = UTF8FPDF()
        pdf.add_page()

        # Set the font to DejaVuSansCondensed for full Unicode support
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("DejaVu", size=12)

        # Add the extracted text to the PDF
        pdf.multi_cell(0, 10, text)

        # Save the PDF
        pdf.output(pdf_path)
        logger.info(f"Created a legitimate PDF at {pdf_path}")
    except Exception as e:
        logger.error(f"Failed to create a legitimate PDF from image: {e}")

# Function to extract text from a PDF using the AI model
def extract_text_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as pdf_file:
            files = {'file': (os.path.basename(pdf_path), pdf_file, 'application/pdf')}
            logger.info(f"Sending PDF {pdf_path} to AI model at {AI_MODEL_ENDPOINT}")
            response = requests.post(AI_MODEL_ENDPOINT, files=files)

        if response.status_code == 200:
            extracted_data = response.json()
            logger.info(f"Raw AI Model Response: {extracted_data}")
            return extracted_data
        else:
            logger.error(f"Failed to extract text from {pdf_path}: {response.status_code} {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error during PDF text extraction for {pdf_path}: {e}")
        return None
