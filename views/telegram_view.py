from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, CommandHandler, filters, Application
import logging
from models.model import process_uploaded_document  # Import generalized function
from database.firebase_init import initialize_firestore
from firebase_admin import firestore  # Import Firestore module

logger = logging.getLogger(__name__)

# Function to create upload button
def create_upload_button():
    keyboard = [[KeyboardButton("Upload Policy holder's Identity Card")]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

# Start command handler
def handle_start(update, context):
    welcome_message = (
        "Hello! Welcome to GoBingo Life. "
        "Please upload the Policy holder's Identity Card as an image (JPEG or PNG format)."
    )
    reply_markup = create_upload_button()
    update.message.reply_text(welcome_message, reply_markup=reply_markup)

# Sequential upload process after Identity Card
def handle_upload_button_press(update, context):
    message_text = update.message.text
    if message_text == "Upload Policy holder's Identity Card":
        update.message.reply_text("Please upload the image of the Identity Card as a document or photo.")
        context.user_data['next_upload'] = "identity_card"  # Track what to upload next
        logger.info("Upload button pressed for Identity Card.")
    else:
        update.message.reply_text("Unexpected input.")
        logger.warning(f"Unexpected input received: {message_text}")

# Generalized image upload handler for Identity Card, Driver's License, and Log Card
def handle_image_upload(update, context):
    file = None
    doc_type = context.user_data.get('next_upload', 'identity_card')  # Default to identity_card

    # Check if the image was uploaded as a photo or document
    if update.message.document:
        file = update.message.document.get_file()
    elif update.message.photo:
        file = update.message.photo[-1].get_file()
    else:
        update.message.reply_text("Please upload an image file (JPEG or PNG).")
        logger.error("No valid image file uploaded. Please provide JPEG or PNG format.")
        return

    # Download the file to memory for processing
    try:
        file_bytes = file.download_as_bytearray()
    except Exception as e:
        logger.error(f"Failed to download the file: {e}")
        update.message.reply_text("Failed to download the image. Please try again.")
        return

    # Process the uploaded image based on document type
    extracted_text = process_uploaded_document(file_bytes, doc_type)

    if extracted_text:
        update.message.reply_text(f"Extracted Text from {doc_type.replace('_', ' ').title()}: {extracted_text}")
        logger.info(f"Extracted text from {doc_type}: {extracted_text}")

        # Initialize Firestore and save the data
        db = initialize_firestore()

        try:
            doc_ref = db.collection(doc_type).document()  # Auto-generate a document ID based on doc_type
            doc_ref.set({
                'extracted_text': extracted_text,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'user_id': update.message.from_user.id
            })
            logger.info(f"Text successfully saved to Firestore under {doc_type}.")

            # Prompt the user for the next document based on the current document type
            if doc_type == "identity_card":
                update.message.reply_text("Please upload the Driver's License.")
                context.user_data['next_upload'] = "drivers_license"
            elif doc_type == "drivers_license":
                update.message.reply_text("Please upload the Log Card.")
                context.user_data['next_upload'] = "log_card"
            elif doc_type == "log_card":
                update.message.reply_text("All documents uploaded successfully.")
                context.user_data['next_upload'] = None  # Reset once the process is complete
        except Exception as e:
            logger.error(f"Failed to save {doc_type} to Firestore: {e}")
            update.message.reply_text(f"Failed to save the extracted text from {doc_type} to the database.")
    else:
        update.message.reply_text(f"Failed to extract information from the {doc_type.replace('_', ' ').title()}.")
        logger.error(f"Extraction failed for {doc_type}.")
