from dotenv import load_dotenv
import logging
from telegram.ext import Application, CommandHandler
from controllers.bot_controller import ask_name
import os

load_dotenv()

logger = logging.getLogger(__name__)
TOKEN = os.getenv('TELEGRAM_BOT_API')

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', ask_name))
    app.run_polling()