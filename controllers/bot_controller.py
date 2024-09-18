from views.telegram_view import create_upload_button
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from models.model import create_selectable_pdf_from_image, extract_text_from_pdf
import os
import logging

logger = logging.getLogger(__name__)

CHOOSING, UPLOADING = range(2)

async def handle_image(update: Update, context: CallbackContext) -> int:
    if update.message.document:
        file = await update.message.document.get_file()
    elif update.message.photo:
        file = await update.message.photo[-1].get_file()
    else:
        await update.message.reply_text("Please upload an image file.")
        return UPLOADING

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_folder = os.path.join(base_dir, 'image_folder')
    pdf_folder = os.path.join(base_dir, 'pdf_folder')
    os.makedirs(image_folder, exist_ok=True)
    os.makedirs(pdf_folder, exist_ok=True)

    file_name = os.path.join(image_folder, 'identity_card.jpg')
    await file.download_to_drive(file_name)
    logger.info(f"Saved uploaded image to {file_name}")

    pdf_name = 'identity_card.pdf'
    pdf_path = os.path.join(pdf_folder, pdf_name)
    
    try:
        create_selectable_pdf_from_image(file_name, pdf_path)
        
        extracted_data = extract_text_from_pdf(pdf_path)

        if extracted_data:
            name = extracted_data.get("name", "Name not found")
            await update.message.reply_text(f"Extracted Name: {name}")
            logger.info(f"Extracted data: {extracted_data}")
        else:
            await update.message.reply_text("Failed to extract information from the Identity Card.")
            logger.error("Extraction failed.")
    except Exception as e:
        await update.message.reply_text("An error occurred while processing the image.")
        logger.error(f"Error processing image: {e}")

    return ConversationHandler.END

async def ask_name(update: Update, context: CallbackContext) -> int:
    welcome_message = "Hello There! Welcome to GoBingo Life. Please upload your Identity Card as an image (JPEG or PNG format)."
    reply_markup = create_upload_button()
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    return UPLOADING
