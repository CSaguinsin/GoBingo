from dotenv import load_dotenv
import logging
from telegram.ext import Application, CommandHandler
from controllers.bot_controller import ask_name
import os

# Load environment variables from .env
load_dotenv()

# Configure logging to capture any errors or information
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch the Telegram bot token from the environment
TOKEN = os.getenv('TELEGRAM_BOT_API')  # Consistent with your .env file

# Main function to run the bot
from dotenv import load_dotenv
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from controllers.bot_controller import ask_name, handle_image, CHOOSING, UPLOADING
import os

# ... existing code ...

if __name__ == '__main__':
    if not TOKEN:
        logger.error("No Telegram bot token provided. Check your .env file.")
    else:
        logger.info(f"Loaded bot token: {TOKEN}")

        app = Application.builder().token(TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', ask_name)],
            states={
                UPLOADING: [MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image)],
            },
            fallbacks=[],
        )

        app.add_handler(conv_handler)

        logger.info("Bot is starting...")
        app.run_polling()
