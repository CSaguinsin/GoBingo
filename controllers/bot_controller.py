from views.telegram_view import create_upload_button
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from models.model import process_uploaded_identity_card
import os
import logging
import datetime

logger = logging.getLogger(__name__)

CHOOSING, UPLOADING = range(2)

# Function to handle the initial greeting and ask the user to upload their ID card
async def ask_name(update: Update, context: CallbackContext) -> int:
    welcome_message = "Hello! Welcome to GoBingo Life. Please upload your Identity Card as an image (JPEG or PNG format)."
    reply_markup = create_upload_button()
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    # Returning UPLOADING to indicate that the bot is now waiting for the image upload
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

        # Ensure the image_folder exists
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        image_folder = os.path.join(base_dir, 'image_folder')
        os.makedirs(image_folder, exist_ok=True)

        # Generate a unique filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = os.path.join(image_folder, f'identity_card_{timestamp}.{file_name_ext}')
        await file.download_to_drive(file_name)
        logger.info(f"Saved uploaded image to {file_name}")

        # Confirm the file exists
        if not os.path.exists(file_name):
            logger.error(f"File not found: {file_name}")
            await update.message.reply_text("Failed to save the uploaded image.")
            return ConversationHandler.END

        # Extract text from the image
        logger.info("Attempting to extract text from the image...")
        with open(file_name, 'rb') as uploaded_file:
            extracted_text = process_uploaded_identity_card(uploaded_file)

        if extracted_text:
            # Log and print the extracted text in the terminal (plain text)
            logger.info(f"Extracted text: {extracted_text}")
            print("\n--- Extracted Text from Image ---\n")
            print(extracted_text)
            print("\n--- End of Extracted Text ---\n")

        else:
            await update.message.reply_text("Failed to extract information from the Identity Card.")
            logger.error("Extraction failed.")

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error in handle_image: {e}")
        await update.message.reply_text("An error occurred while processing the image.")
        return ConversationHandler.END