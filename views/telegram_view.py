from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def create_welcome_message(full_name, company_name):
    return (
        f"Hello {full_name}!\n"
        f"I'm your {company_name} Assistant.\n"
        "By chatting with us, you agree to share sensitive information. How can we help you today?\n\n"
        "Please select an option to upload the required documents:"
    )

def create_keyboard():
    keyboard = [
        [InlineKeyboardButton("Upload Driver's License", callback_data='upload_license')],
        [InlineKeyboardButton("Upload Identity Card", callback_data='upload_identity_card')],
        [InlineKeyboardButton("Upload Log Card", callback_data='upload_log_card')]
    ]
    return InlineKeyboardMarkup(keyboard)