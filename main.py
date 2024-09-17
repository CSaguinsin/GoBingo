from dotenv import load_dotenv
import logging
import threading
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, CallbackContext, ConversationHandler
import os


load_dotenv()  


TOKEN = os.getenv('TELEGRAM_BOT_API')
MONDAY_API_TOKEN = os.getenv('MONDAY_API_TOKEN')
POLICY_BOARD_ID = os.getenv('POLICY_BOARD_ID')
REFERRER_BOARD_ID = os.getenv('REFERRER_BOARD_ID')
INSURANCE_BOARD_ID = os.getenv('INSURANCE_BOARD_ID')
AI_MODEL_ENDPOINT = os.getenv('AI_MODEL_ENDPOINT')
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT')