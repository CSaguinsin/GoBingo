from dotenv import load_dotenv
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters
from controllers.bot_controller import ask_name, handle_image, handle_upload_button_press  # Import functions from bot_controller
import os

# Load environment variables from .env
load_dotenv()

# Configure logging to capture any errors or information
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch the Telegram bot token from the environment
TOKEN = os.getenv('TELEGRAM_BOT_API')

# Define conversation states
CHOOSING, UPLOADING = range(2)

# Main function to run the bot
if __name__ == '__main__':
    if not TOKEN:
        logger.error("No Telegram bot token provided. Check your .env file.")
    else:
        # Build the application using the bot token
        app = Application.builder().token(TOKEN).build()

        # Define conversation handler to manage user flow
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', ask_name)],
            states={
                CHOOSING: [MessageHandler(filters.TEXT, handle_upload_button_press)],
                UPLOADING: [MessageHandler(filters.PHOTO | filters.Document.ALL, handle_image)]
            },
            fallbacks=[]  # You can add fallbacks to handle errors or /cancel
        )

        # Add the conversation handler
        app.add_handler(conv_handler)

        # Start the bot's polling loop
        logger.info("Bot is starting...")
        app.run_polling()
