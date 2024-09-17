from views.telegram_view import create_upload_button  # Removed create_welcome_message import as it's no longer needed
from telegram import Update
from telegram.ext import CallbackContext

CHOOSING = range(1)  # Define CHOOSING as a constant for the conversation state

async def ask_name(update: Update, context: CallbackContext) -> int:
    # Static welcome message
    welcome_message = "Hello There! Welcome to GoBingo Life. Please upload your Identity Card as an image (JPEG or PNG format)."

    # Update user_data for uploads (if needed for other features)
    context.user_data['uploads'] = {'driver_license': False, 'identity_card': False, 'log_card': False}
    
    # Show the upload button
    reply_markup = create_upload_button()

    # Send the static welcome message with the button
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    return CHOOSING
