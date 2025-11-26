import time, re
from django.conf import settings
from telebot import TeleBot
from telebot.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ChatJoinRequest,
)

bot = TeleBot(settings.BOT_TOKEN, parse_mode="HTML", threaded=False)
