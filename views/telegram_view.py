import logging
from telegram import ReplyKeyboardMarkup, KeyboardButton
from models.model import process_uploaded_document, fetch_sanitized_name_from_firestore
from firebase_admin import firestore
from database.firebase_init import initialize_firestore
import io

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

# Handle the button press to trigger file uploads
def handle_upload_button_press(update, context):
    message_text = update.message.text

    if message_text == "Upload Policy holder's Identity Card":
        update.message.reply_text("Please upload the image of the Identity Card as a document or photo.")
        context.user_data['document_type'] = 'identity_card'  # Store document type
    elif message_text == "Upload Policy holder's Driver's License":
        update.message.reply_text("Please upload the image of the Driver's License.")
        context.user_data['document_type'] = 'drivers_license'
    elif message_text == "Upload Policy holder's Log Card":
        update.message.reply_text("Please upload the image of the Log Card.")
        context.user_data['document_type'] = 'log_card'
    else:
        update.message.reply_text("Unexpected input.")

# Handle the image upload and save the extracted data in Firestore
def handle_image_upload(update, context):
    try:
        # Check if the image is a photo or a document
        if update.message.document:
            file = update.message.document.get_file()
        elif update.message.photo:
            file = update.message.photo[-1].get_file()
        else:
            update.message.reply_text("Please upload a valid image file.")
            return

        # Download the file as bytes and process it
        file_bytes = file.download_as_bytearray()
        file_like_object = io.BytesIO(file_bytes)

        # Determine which document type is being uploaded
        document_type = context.user_data.get('document_type', 'identity_card')
        
        # Retrieve the sanitized_name if already stored in user data (after identity card processing)
        sanitized_name = context.user_data.get('sanitized_name', None)

        # If sanitized_name is missing for non-identity card uploads, fetch it from Firestore
        if document_type != 'identity_card' and not sanitized_name:
            user_id = str(update.message.from_user.id)
            logger.info(f"Fetching sanitized_name from Firestore for user_id: {user_id}")
            sanitized_name = fetch_sanitized_name_from_firestore(user_id)
            if not sanitized_name:
                update.message.reply_text("Missing identity card data. Please upload the Identity Card first.")
                return

        # Process the uploaded document with the sanitized_name if available
        extracted_data = process_uploaded_document(file_like_object, document_type=document_type, sanitized_name=sanitized_name)

        if extracted_data:
            update.message.reply_text(f"Extracted Data: {extracted_data}")
            logger.info(f"Extracted data: {extracted_data}")

            # Initialize Firestore and save the extracted data
            db = initialize_firestore()
            collection_name = 'identity_cards' if document_type == 'identity_card' else 'drivers_licenses' if document_type == 'drivers_license' else 'log_cards'
            doc_ref = db.collection(collection_name).document()  # Auto-generate document ID
            doc_ref.set({
                'extracted_data': extracted_data,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'user_id': update.message.from_user.id
            })

            # Store the sanitized_name in user_data after processing the identity card
            if document_type == 'identity_card':
                context.user_data['sanitized_name'] = extracted_data.get('sanitized_name')
                reply_markup = create_upload_button("Upload Policy holder's Driver's License")
                update.message.reply_text("Identity Card uploaded successfully. Now please upload the Driver's License.", reply_markup=reply_markup)

            elif document_type == 'drivers_license':
                reply_markup = create_upload_button("Upload Policy holder's Log Card")
                update.message.reply_text("Driver's License uploaded successfully. Now please upload the Log Card.", reply_markup=reply_markup)

            else:
                update.message.reply_text("All documents uploaded successfully. Thank you!")
        else:
            update.message.reply_text("Failed to extract information from the uploaded image.")
            logger.error("Extraction failed.")

    except Exception as e:
        logger.error(f"Error in handle_image_upload: {e}")
        update.message.reply_text("An error occurred during image processing.")
