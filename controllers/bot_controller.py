import io
import logging
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from models.model import process_uploaded_document, process_drivers_license, fetch_sanitized_name_from_firestore
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

        # Download the file as bytes for further processing
        file_bytes = await file.download_as_bytearray()
        file_like_object = io.BytesIO(file_bytes)

        # Determine which document type is being uploaded
        document_type = context.user_data.get('document_type', 'identity_card')

        # Save the file to disk
        image_folder = os.path.join(os.getcwd(), 'image_folder')
        os.makedirs(image_folder, exist_ok=True)
        filename = f"{document_type}_{os.urandom(8).hex()}.jpg"
        image_path = os.path.join(image_folder, filename)

        # Write the bytes to disk as an image
        with open(image_path, "wb") as f:
            f.write(file_bytes)

        logger.info(f"Image saved to {image_path}")

        # Process the uploaded document using the model.py function
        extracted_data = process_uploaded_document(image_path, document_type=document_type)

        if extracted_data:
            logger.info(f"Extracted data: {extracted_data}")
            await update.message.reply_text(f"Extracted Data: {extracted_data}")

            # Handle identity card upload
            if document_type == 'identity_card':
                sanitized_name = extracted_data.get('sanitized_name', None)
                
                # Log the extracted sanitized name
                logger.info(f"Extracted sanitized_name from identity card: {sanitized_name}")
                
                if sanitized_name:
                    # Store sanitized_name in context for future use
                    context.user_data['sanitized_name'] = sanitized_name
                    logger.debug(f"Sanitized Name: {sanitized_name} stored in context.")

                    # Prompt to upload Driver's License next
                    reply_markup = create_upload_button("Upload Policy holder's Driver's License")
                    await update.message.reply_text(
                        "Identity Card uploaded successfully. Now please upload the Driver's License.",
                        reply_markup=reply_markup
                    )
                    context.user_data['document_type'] = 'drivers_license'  # Update document type
                else:
                    logger.error("Sanitized name not found in extracted data.")
                    await update.message.reply_text("Failed to extract sanitized name from identity card.")
                    return UPLOADING

            # Handle driver's license upload
            elif document_type == 'drivers_license':
                sanitized_name = context.user_data.get('sanitized_name')

                # Log the sanitized_name retrieval
                logger.info(f"Sanitized name retrieved from context for driver's license: {sanitized_name}")

                # If sanitized_name is not in context, fetch it from Firestore
                if not sanitized_name:
                    user_id = str(update.message.from_user.id)
                    logger.info(f"Fetching sanitized_name from Firestore for user_id: {user_id}")
                    sanitized_name = fetch_sanitized_name_from_firestore(user_id)

                if sanitized_name:
                    logger.debug(f"Processing driver's license with sanitized_name: {sanitized_name}")
                    # Call process_drivers_license with both arguments
                    result = process_drivers_license(image_path, sanitized_name)
                    if result:
                        logger.info(f"Driver's License processed successfully: {result}")
                    else:
                        logger.error("Failed to process driver's license.")
                        return UPLOADING
                else:
                    logger.error("No sanitized_name found in context or Firestore. Cannot process driver's license.")
                    await update.message.reply_text("Failed to process driver's license due to missing identity card information.")
                    return UPLOADING

                # Prompt to upload Log Card next
                reply_markup = create_upload_button("Upload Policy holder's Log Card")
                await update.message.reply_text(
                    "Driver's License uploaded successfully. Now please upload the Log Card.",
                    reply_markup=reply_markup
                )
                context.user_data['document_type'] = 'log_card'

            # Handle log card upload
            elif document_type == 'log_card':
                await update.message.reply_text("All documents uploaded successfully. Thank you!")
        else:
            await update.message.reply_text("Failed to extract information from the uploaded document.")
            logger.error("Extraction failed.")
            return UPLOADING

        return UPLOADING

    except Exception as e:
        logger.error(f"Error in handle_image: {e}")
        await update.message.reply_text("An error occurred while processing the image.")
        return ConversationHandler.END
