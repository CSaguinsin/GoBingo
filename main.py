from dotenv import load_dotenv
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from controllers.bot_controller import ask_name, handle_image  # Import handle_image
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

        # Add the start command handler
        app.add_handler(CommandHandler('start', ask_name))

        # Add a handler for photo or document uploads (handle_image)
        app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_image))

        # Start the bot's polling loop
        logger.info("Bot is starting...")
        app.run_polling()
