from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters, Application
from telegram import ReplyKeyboardMarkup, KeyboardButton
import os  # Fix for the "os is not defined" error
import logging
from models.model import create_selectable_pdf_from_image, extract_text_from_pdf

logger = logging.getLogger(__name__)

# # Define create_welcome_message function
# def create_welcome_message(full_name, company_name):
#     return f"Hello {full_name}, welcome to {company_name}! Please upload your Identity Card as an image (JPEG or PNG format)."

# Define create_upload_button function
def create_upload_button():
    # Create a keyboard with a button to prompt the user to upload the identity card
    keyboard = [[KeyboardButton("Upload Policy holder's Identity Card")]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

# Start command handler
def handle_start(update, context):
    # Static welcome message
    welcome_message = "Hello There! Welcome to GoBingo Life. Please upload Policy holder's Identity Card as an image (JPEG or PNG format)."
    
    # Show upload button
    reply_markup = create_upload_button()
    update.message.reply_text(welcome_message, reply_markup=reply_markup)




# Handle image upload for Identity Card
def handle_image_upload(update, context):
    file = update.message.document.get_file()

    # Define paths for storing the image and PDF
    image_folder = '/Users/carlsaginsin/Projects/BingoTelegram/image_folder'
    pdf_folder = '/Users/carlsaginsin/Projects/BingoTelegram/pdf_folder'
    
    # Ensure the directories exist
    os.makedirs(image_folder, exist_ok=True)
    os.makedirs(pdf_folder, exist_ok=True)
    
    # Save the uploaded image locally in the image folder
    file_name = os.path.join(image_folder, 'identity_card.jpg')
    file.download(file_name)
    
    # Convert the image to a PDF and save it in the PDF folder
    pdf_name = os.path.join(pdf_folder, 'identity_card.pdf')
    create_selectable_pdf_from_image(file_name, pdf_name)

    # Extract text from the PDF using the AI model
    extracted_data = extract_text_from_pdf(pdf_name)

    # Send a message to the user with the extracted name or an error
    if extracted_data:
        name = extracted_data.get("name", "Name not found")
        update.message.reply_text(f"Extracted Name: {name}")
        logger.info(f"Extracted data: {extracted_data}")
    else:
        update.message.reply_text("Failed to extract information from the Identity Card.")
        logger.error("Extraction failed.")

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    application = Application.builder().token(TOKEN).build()

    # Start command handler
    application.add_handler(CommandHandler("start", handle_start))

    # Handle document upload (expecting an image with JPEG or PNG format)
    application.add_handler(MessageHandler(filters.Document.MIME_TYPE(["image/jpeg", "image/png"]), handle_image_upload))

    # Start the bot
    application.run_polling()
