from dotenv import load_dotenv
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from controllers.bot_controller import ask_name, handle_image_upload  # Use handle_image_upload
import os

# Load environment variables from .env 
load_dotenv()

# Configure logging to capture any errors or information
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch the Telegram bot token from the environment
TOKEN = os.getenv('TELEGRAM_BOT_API')

# Main function to run the bot
if __name__ == '__main__':
    if not TOKEN:
        logger.error("No Telegram bot token provided. Check your .env file.")
    else:
        # Build the application using the bot token
        app = Application.builder().token(TOKEN).build()

        # Conversation handler for the sequential document upload flow
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', ask_name)],
            states={
                # States for uploading different documents
                1: [MessageHandler(filters.PHOTO | filters.Document.ALL, handle_image_upload)],
                2: [MessageHandler(filters.PHOTO | filters.Document.ALL, handle_image_upload)],
                3: [MessageHandler(filters.PHOTO | filters.Document.ALL, handle_image_upload)],
            },
            fallbacks=[],
        )

        # Add the conversation handler to the application
        app.add_handler(conv_handler)

        # Start the bot's polling loop
        logger.info("Bot is starting...")
        app.run_polling()
