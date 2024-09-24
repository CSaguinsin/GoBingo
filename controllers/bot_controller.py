from views.telegram_view import create_upload_button
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler, CommandHandler, MessageHandler, filters
from models.model import process_uploaded_document  # Use generalized function to handle different doc types
import os
import logging
import datetime

logger = logging.getLogger(__name__)

# Defining states for ConversationHandler
CHOOSING, UPLOADING_IDENTITY, UPLOADING_LICENSE, UPLOADING_LOG = range(4)

# Function to handle the initial greeting and ask the user to upload their ID card
async def ask_name(update: Update, context: CallbackContext) -> int:
    welcome_message = "Hello! Welcome to GoBingo Life. Please upload your Identity Card as an image (JPEG or PNG format)."
    reply_markup = create_upload_button()
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    # Returning UPLOADING_IDENTITY to indicate that the bot is now waiting for the Identity Card upload
    return UPLOADING_IDENTITY

# Function to handle document uploads
async def handle_image_upload(update: Update, context: CallbackContext) -> int:
    try:
        # Determine the current document type the bot is waiting for
        current_state = context.user_data.get('next_upload', 'identity_card')

        # Check if the image was uploaded as a document or a photo
        if update.message.document:
            file = await update.message.document.get_file()
            file_name_ext = update.message.document.file_name.split('.')[-1]
        elif update.message.photo:
            file = await update.message.photo[-1].get_file()
            file_name_ext = 'jpg'  # Telegram does not provide an extension for photos
        else:
            await update.message.reply_text("Please upload an image file (JPEG or PNG).")
            logger.error("No valid image file uploaded. Please provide JPEG or PNG format.")
            return current_state  # Stay in the current state

        # Ensure the image folder exists
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        image_folder = os.path.join(base_dir, 'image_folder')
        os.makedirs(image_folder, exist_ok=True)

        # Generate a unique filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = os.path.join(image_folder, f'{current_state}_{timestamp}.{file_name_ext}')
        await file.download_to_drive(file_name)
        logger.info(f"Saved uploaded image to {file_name}")

        # Confirm the file exists
        if not os.path.exists(file_name):
            logger.error(f"File not found: {file_name}")
            await update.message.reply_text("Failed to save the uploaded image.")
            return ConversationHandler.END

        # Process the image (Identity Card, Driver's License, or Log Card)
        logger.info(f"Attempting to extract text from the {current_state}...")
        with open(file_name, 'rb') as uploaded_file:
            extracted_text = process_uploaded_document(uploaded_file, current_state)

        if extracted_text:
            # Log the extracted text
            logger.info(f"Extracted text: {extracted_text}")
            await update.message.reply_text(f"Extracted Text: {extracted_text}")

            # Based on the current document, prompt the user for the next upload
            if current_state == 'identity_card':
                await update.message.reply_text("Please upload the Driver's License.")
                context.user_data['next_upload'] = 'drivers_license'
                return UPLOADING_LICENSE
            elif current_state == 'drivers_license':
                await update.message.reply_text("Please upload the Log Card.")
                context.user_data['next_upload'] = 'log_card'
                return UPLOADING_LOG
            elif current_state == 'log_card':
                await update.message.reply_text("All documents uploaded successfully. Thank you!")
                return ConversationHandler.END
        else:
            await update.message.reply_text(f"Failed to extract information from the {current_state}.")
            logger.error(f"Extraction failed for {current_state}.")
            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_image_upload: {e}")
        await update.message.reply_text("An error occurred while processing the image.")
        return ConversationHandler.END
