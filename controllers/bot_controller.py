import io
import logging
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from models.model import process_uploaded_document, process_identity_card, fetch_sanitized_name_from_firestore, send_data_to_monday
from views.telegram_view import create_upload_button
import os

logger = logging.getLogger(__name__)

CHOOSING, UPLOADING = range(2)

# Function to handle the initial greeting and ask the user to upload their ID card
async def ask_name(update: Update, context: CallbackContext) -> int:
    welcome_message = "Hello! Welcome to GoBingo Life. Please upload your Identity Card as an image (JPEG or PNG format)."
    reply_markup = create_upload_button("Upload Policy holder's Identity Card")
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    context.user_data['document_type'] = 'identity_card'  # Initial document type
    return UPLOADING

async def handle_upload_button_press(update: Update, context: CallbackContext) -> int:
    message_text = update.message.text

    if message_text == "Upload Policy holder's Identity Card":
        await update.message.reply_text("Please upload the image of the Identity Card as a document or photo.")
        context.user_data['document_type'] = 'identity_card'
    elif message_text == "Upload Policy holder's Driver's License":
        await update.message.reply_text("Please upload the image of the Driver's License.")
        context.user_data['document_type'] = 'drivers_license'
    elif message_text == "Upload Policy holder's Log Card":
        await update.message.reply_text("Please upload the image of the Log Card.")
        context.user_data['document_type'] = 'log_card'
    else:
        await update.message.reply_text("Unexpected input.")
    
    return UPLOADING

async def handle_image(update: Update, context: CallbackContext) -> int:
    try:
        # Check if the image was uploaded as a document or a photo
        if update.message.document:
            file = await update.message.document.get_file()
            file_name_ext = update.message.document.file_name.split('.')[-1].lower()
            if file_name_ext not in ['jpg', 'jpeg', 'png']:
                await update.message.reply_text("Please upload a valid image file (JPEG or PNG).")
                return UPLOADING
        elif update.message.photo:
            file = await update.message.photo[-1].get_file()
            file_name_ext = 'jpg'  # Default to jpg if uploaded as a photo
        else:
            await update.message.reply_text("Please upload an image file (JPEG or PNG).")
            return UPLOADING

        # Notify the user that the system is processing the uploaded image
        await update.message.reply_text("Our system is currently processing your data, please wait and thank you!")

        # Download the file as bytes for further processing
        file_bytes = await file.download_as_bytearray()
        file_like_object = io.BytesIO(file_bytes)

        # Determine which document type is being uploaded
        document_type = context.user_data.get('document_type', 'identity_card')

        # Save the file to disk (could be used for logging or future analysis)
        image_folder = os.path.join(os.getcwd(), 'image_folder')
        os.makedirs(image_folder, exist_ok=True)
        filename = f"{document_type}_{os.urandom(8).hex()}.jpg"
        image_path = os.path.join(image_folder, filename)

        with open(image_path, "wb") as f:
            f.write(file_bytes)

        logger.info(f"Image saved to {image_path}")

        # Process the uploaded document based on document type
        if document_type == 'identity_card':
            extracted_data = process_identity_card(image_path, user_id=str(update.message.from_user.id))

            if extracted_data:
                sanitized_name = extracted_data.get('sanitized_name')
                context.user_data['sanitized_name'] = sanitized_name
                context.user_data['identity_card_data'] = extracted_data  # Save data temporarily

                # Prompt for driver's license upload
                reply_markup = create_upload_button("Upload Policy holder's Driver's License")
                await update.message.reply_text("Identity Card uploaded successfully. Now please upload the Driver's License.", reply_markup=reply_markup)
                context.user_data['document_type'] = 'drivers_license'
            else:
                logger.error("Failed to process identity card.")
                await update.message.reply_text("Failed to extract information from the Identity Card.")
                return UPLOADING

        else:
            sanitized_name = context.user_data.get('sanitized_name')
            if not sanitized_name:
                user_id = str(update.message.from_user.id)
                sanitized_name = fetch_sanitized_name_from_firestore(user_id)
                if not sanitized_name:
                    await update.message.reply_text("Missing identity card data. Please upload the Identity Card first.")
                    return UPLOADING

            extracted_data = process_uploaded_document(image_path, document_type=document_type, sanitized_name=sanitized_name)

            if extracted_data:
                # Save data for each document temporarily
                if document_type == 'drivers_license':
                    context.user_data['drivers_license_data'] = extracted_data

                    # Prompt for log card upload
                    reply_markup = create_upload_button("Upload Policy holder's Log Card")
                    await update.message.reply_text("Driver's License uploaded successfully. Now please upload the Log Card.", reply_markup=reply_markup)
                    context.user_data['document_type'] = 'log_card'

                elif document_type == 'log_card':
                    context.user_data['log_card_data'] = extracted_data

                    # Now, check if all three documents are uploaded
                    if ('identity_card_data' in context.user_data and
                            'drivers_license_data' in context.user_data and
                            'log_card_data' in context.user_data):

                        # Combine all data to send to Monday.com
                        complete_data = {
                            'identity_card': context.user_data['identity_card_data'],
                            'drivers_license': context.user_data['drivers_license_data'],
                            'log_card': context.user_data['log_card_data']
                        }

                        send_to_monday_result = send_data_to_monday(complete_data)
                        if send_to_monday_result:
                            await update.message.reply_text("All documents uploaded successfully and stored at BingoLife Co. Thank you!")
                        else:
                            await update.message.reply_text("Error occurred while sending data to Monday.com.")
                    else:
                        await update.message.reply_text("Failed to upload all documents.")
                        logger.error("All documents not uploaded.")
            else:
                await update.message.reply_text("Failed to extract information from the uploaded document.")
                logger.error("Extraction failed.")
                return UPLOADING

        return UPLOADING

    except Exception as e:
        logger.error(f"Error in handle_image: {e}")
        await update.message.reply_text("An error occurred while processing the image.")
        return ConversationHandler.END
