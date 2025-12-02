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


# Message Handlers
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    """Handle /start command"""
    user_name = message.from_user.first_name
    welcome_text = f"""
👋 <b>Hello {user_name}!</b>

Welcome to the bot! I'm up and running on Vercel.

Available commands:
/start - Show this message
/help - Get help
    """
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['help'])
def help_command(message: Message):
    """Handle /help command"""
    help_text = """
<b>📚 Help Menu</b>

Available commands:
• /start - Start the bot
• /help - Show this help message

Send me any message and I'll echo it back!
    """
    bot.reply_to(message, help_text)


@bot.message_handler(func=lambda message: True)
def echo_message(message: Message):
    """Echo all other messages"""
    bot.reply_to(message, f"You said: {message.text}")
