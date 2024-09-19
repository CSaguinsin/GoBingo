from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, CommandHandler, filters, Application
import logging
import os
from models.model import extract_text_from_image, process_uploaded_identity_card

logger = logging.getLogger(__name__)

# Define create_upload_button function
def create_upload_button():
    keyboard = [[KeyboardButton("Upload Policy holder's Identity Card")]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

# Start command handler
def handle_start(update, context):
    welcome_message = "Hello! Welcome to GoBingo Life. Please upload Policy holder's Identity Card as an image (JPEG or PNG format)."
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
    file = None

    # Check if the image was uploaded as a photo or document
    if update.message.document:
        file = update.message.document.get_file()
    elif update.message.photo:
        file = update.message.photo[-1].get_file()
    else:
        update.message.reply_text("Please upload an image file (JPEG or PNG).")
        return

    # Create the folder to save the uploaded image
    image_folder = os.path.join(os.getcwd(), 'IMAGE_PATH')
    os.makedirs(image_folder, exist_ok=True)
    
    file_name = os.path.join(image_folder, 'identity_card.jpg')
    file.download(file_name)
    logger.info(f"Saved uploaded image to {file_name}")

    # Now extract the text from the image using Tesseract and OpenCV
    extracted_text = process_uploaded_identity_card(open(file_name, 'rb'))

    if extracted_text:
        update.message.reply_text(f"Extracted Text: {extracted_text}")
        logger.info(f"Extracted text: {extracted_text}")
    else:
        update.message.reply_text("Failed to extract information from the Identity Card.")
        logger.error("Extraction failed.")
