import io
from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import MessageHandler, CommandHandler, filters, Application
import logging
from models.model import process_uploaded_document
from database.firebase_init import initialize_firestore
from firebase_admin import firestore

logger = logging.getLogger(__name__)

# Define function to create buttons dynamically
def create_upload_button(button_text):
    keyboard = [[KeyboardButton(button_text)]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

# Start command handler
def handle_start(update, context):
    welcome_message = "Hello! Welcome to GoBingo Life. Please upload Policy holder's Identity Card as an image (JPEG or PNG format)."
    reply_markup = create_upload_button("Upload Policy holder's Identity Card")
    update.message.reply_text(welcome_message, reply_markup=reply_markup)

def handle_upload_button_press(update, context):
    message_text = update.message.text
    if message_text == "Upload Policy holder's Identity Card":
        update.message.reply_text("Please upload the image of the Identity Card as a document or photo.")
        context.user_data['document_type'] = 'identity_card'  # Store the document type
        logger.info("Upload button pressed for Identity Card.")
    elif message_text == "Upload Policy holder's Driver's License":
        update.message.reply_text("Please upload the image of the Driver's License.")
        context.user_data['document_type'] = 'drivers_license'  # Store the document type
        logger.info("Upload button for Driver's License pressed.")
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

    # Download the file as bytes
    file_bytes = file.download_as_bytearray()

    # Wrap the bytearray in a file-like object
    file_like_object = io.BytesIO(file_bytes)

    # Determine which document type is being uploaded
    document_type = context.user_data.get('document_type', 'identity_card')  # Default to identity card

    # Process the uploaded document (identity card or driver's license)
    extracted_data = process_uploaded_document(file_like_object, document_type=document_type)

    if extracted_data:
        # Send the extracted text back to the user
        update.message.reply_text(f"Extracted Data: {extracted_data}")
        logger.info(f"Extracted data: {extracted_data}")

        # Initialize Firestore
        db = initialize_firestore()

        # Save the extracted text to Firestore
        try:
            collection_name = 'identity_cards' if document_type == 'identity_card' else 'drivers_licenses'
            doc_ref = db.collection(collection_name).document()  # Auto-generate a document ID
            doc_ref.set({
                'extracted_data': extracted_data,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'user_id': update.message.from_user.id
            })
            logger.info(f"Data successfully saved to Firestore in {collection_name}.")

            # Show the next step: If identity card is uploaded, prompt for Driver's License
            if document_type == 'identity_card':
                reply_markup = create_upload_button("Upload Policy holder's Driver's License")
                update.message.reply_text("Identity Card uploaded successfully. Now please upload the Driver's License.", reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Failed to save to Firestore: {e}")
            update.message.reply_text("Failed to save the extracted data to the database.")
    else:
        update.message.reply_text("Failed to extract information from the uploaded image.")
        logger.error("Extraction failed.")
