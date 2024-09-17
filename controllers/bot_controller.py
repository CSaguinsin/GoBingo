from models.model import create_drive_folder, upload_file_to_drive
from views.telegram_view import create_welcome_message, create_keyboard
from telegram import Update
from telegram.ext import CallbackContext

CHOOSING = range(1)  # Define CHOOSING as a constant for the conversation state

async def ask_name(update: Update, context: CallbackContext) -> int:
    full_name = update.message.text
    context.user_data['full_name'] = full_name

    company_name = "Bingo"
    welcome_message = create_welcome_message(full_name, company_name)

    context.user_data['uploads'] = {'driver_license': False, 'identity_card': False, 'log_card': False}
    reply_markup = create_keyboard()

    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    return CHOOSING