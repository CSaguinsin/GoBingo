from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, CommandHandler, filters, Application
import logging
import os
from models.model import extract_text_from_image, process_uploaded_identity_card
from database.firebase_init import initialize_firestore
from firebase_admin import firestore  # Import firestore module from firebase_admin

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

    # You no longer need to save the image here or refer to file_name.
    # Simply pass the file to process_uploaded_identity_card for text extraction.

    # Download the file to memory and pass it for text extraction
    file_bytes = file.download_as_bytearray()

    # Process the uploaded image and extract the text
    extracted_text = process_uploaded_identity_card(file_bytes)

    if extracted_text:
        # Send the extracted text back to the user
        update.message.reply_text(f"Extracted Text: {extracted_text}")
        logger.info(f"Extracted text: {extracted_text}")

        # Initialize Firestore
        db = initialize_firestore()

        # Save the extracted text to Firestore
        try:
            doc_ref = db.collection('identity_cards').document()  # Auto-generate a document ID
            doc_ref.set({
                'extracted_text': extracted_text,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'user_id': update.message.from_user.id
            })
            logger.info("Text successfully saved to Firestore.")
        except Exception as e:
            logger.error(f"Failed to save to Firestore: {e}")
            update.message.reply_text("Failed to save the extracted text to the database.")
    else:
        update.message.reply_text("Failed to extract information from the Identity Card.")
        logger.error("Extraction failed.")
