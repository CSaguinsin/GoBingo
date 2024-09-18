from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, CommandHandler, filters, Application
import logging
import os
from models.model import create_selectable_pdf_from_image, extract_text_from_pdf

logger = logging.getLogger(__name__)

# Define create_upload_button function
def create_upload_button():
    keyboard = [[KeyboardButton("Upload Policy holder's Identity Card")]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

# Start command handler
def handle_start(update, context):
    welcome_message = "Hello There! Welcome to GoBingo Life. Please upload Policy holder's Identity Card as an image (JPEG or PNG format)."
    reply_markup = create_upload_button()
    update.message.reply_text(welcome_message, reply_markup=reply_markup)

def handle_upload_button_press(update, context):
    message_text = update.message.text
    if message_text == "Upload Policy holder's Identity Card":
        update.message.reply_text("Please upload the image of the Identity Card as a document or photo.")
        logger.info("Upload button pressed.")
    else:
        update.message.reply_text("Unexpected input.")

# Handle image upload for Identity Card
def handle_image_upload(update, context):
    file = update.message.document.get_file()
    
    logger.info(f"Uploaded file MIME type: {file.mime_type}")

    image_folder = '/Users/carlsaginsin/Projects/BingoTelegram/image_folder'
    pdf_folder = '/Users/carlsaginsin/Projects/BingoTelegram/pdf_folder'
    
    os.makedirs(image_folder, exist_ok=True)
    os.makedirs(pdf_folder, exist_ok=True)
    
    file_name = os.path.join(image_folder, 'identity_card.jpg')
    file.download(file_name)
    logger.info(f"Saved uploaded image to {file_name}")

    pdf_name = 'identity_card.pdf'
    create_selectable_pdf_from_image(file_name, pdf_name)

    pdf_path = os.path.join(pdf_folder, pdf_name)

    extracted_data = extract_text_from_pdf(pdf_path)

    if extracted_data:
        name = extracted_data.get("name", "Name not found")
        update.message.reply_text(f"Extracted Name: {name}")
        logger.info(f"Extracted data: {extracted_data}")
    else:
        update.message.reply_text("Failed to extract information from the Identity Card.")
        logger.error("Extraction failed.")
