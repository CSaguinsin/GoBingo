import io
from views.telegram_view import create_upload_button
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from models.model import process_uploaded_document
import os
import logging
import datetime

logger = logging.getLogger(__name__)

CHOOSING, UPLOADING = range(2)

# Function to handle the initial greeting and ask the user to upload their ID card
async def ask_name(update: Update, context: CallbackContext) -> int:
    welcome_message = "Hello! Welcome to GoBingo Life. Please upload your Identity Card as an image (JPEG or PNG format)."
    reply_markup = create_upload_button("Upload Policy holder's Identity Card")
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    context.user_data['document_type'] = 'identity_card'  # Initial document type
    return UPLOADING

# Function to handle image uploads (photo or document)
async def handle_image(update: Update, context: CallbackContext) -> int:
    try:
        # Determine if the image was uploaded as a document or a photo
        if update.message.document:
            file = await update.message.document.get_file()
            file_name_ext = update.message.document.file_name.split('.')[-1]
        elif update.message.photo:
            file = await update.message.photo[-1].get_file()
            file_name_ext = 'jpg'  # Telegram does not provide an extension for photos
        else:
            await update.message.reply_text("Please upload an image file (JPEG or PNG).")
            return UPLOADING

        # Download the file as bytes for further processing
        file_bytes = await file.download_as_bytearray()

        # Wrap the bytearray in a file-like object
        file_like_object = io.BytesIO(file_bytes)

        # Determine which document type is being uploaded
        document_type = context.user_data.get('document_type', 'identity_card')  # Default to identity_card

        # Process the uploaded document using the model.py function
        extracted_data = process_uploaded_document(file_like_object, document_type=document_type)

        if extracted_data:
            logger.info(f"Extracted data: {extracted_data}")
            await update.message.reply_text(f"Extracted Data: {extracted_data}")
            
            # Show the next button to upload Driver's License if Identity Card was uploaded
            if document_type == 'identity_card':
                reply_markup = create_upload_button("Upload Policy holder's Driver's License")
                await update.message.reply_text("Identity Card uploaded successfully. Now please upload the Driver's License.", reply_markup=reply_markup)
                context.user_data['document_type'] = 'drivers_license'  # Switch to drivers_license
        else:
            await update.message.reply_text("Failed to extract information from the uploaded document.")
            logger.error("Extraction failed.")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_image: {e}")
        await update.message.reply_text("An error occurred while processing the image.")
        return ConversationHandler.END
