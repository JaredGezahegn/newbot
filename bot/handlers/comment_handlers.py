"""
Comment handlers for the confession bot.
Handles viewing, adding, and reacting to comments.
"""
import logging
from datetime import datetime
from telebot.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from bot.models import Comment, Confession, User
from bot.services.comment_service import get_comments
from django.db import DatabaseError

logger = logging.getLogger(__name__)

PAGE_SIZE = 5


def format_timestamp(dt):
    """Format datetime to 'Dec 03, 2024 • 02:30 PM'"""
    try:
        return dt.strftime("%b %d, %Y • %I:%M %p")
    except Exception:
        return "Unknown time"


def build_comment_text(comment):
    """
    Build comment text following guideline format:
    Anonymous
    Great perspective on this situation...
    🕒 Dec 3, 2024 • 02:30 PM
    """
    # Author
    comment_text = "<b>Anonymous</b>\n"
    
    # Comment text (truncated to 400 chars)
    comment_snippet = comment.text[:400]
    comment_text += f"{comment_snippet}\n"
    
    # Timestamp
    timestamp = format_timestamp(comment.created_at)
    comment_text += f"🕒 {timestamp}"
    
    return comment_text


def build_comment_keyboard(comment):
    """
    Build inline keyboard for comment:
    Row 1: [👍 N] [⚠️ N] [👎 N]
    Row 2: [↩️ Reply]
    """
    keyboard = InlineKeyboardMarkup()
    
    # Row 1: Reactions
    keyboard.row(
        InlineKeyboardButton(
            f"👍 {comment.like_count}",
            callback_data=f"like_comment_{comment.id}"
        ),
        InlineKeyboardButton(
            f"⚠️ {comment.report_count}",
            callback_data=f"report_comment_{comment.id}"
        ),
        InlineKeyboardButton(
            f"👎 {comment.dislike_count}",
            callback_data=f"dislike_comment_{comment.id}"
        )
    )
    
    # Row 2: Reply
    keyboard.row(
        InlineKeyboardButton(
            "↩️ Reply",
            callback_data=f"reply_comment_{comment.id}"
        )
    )
    
    return keyboard


def send_comment_message(bot, chat_id, comment):
    """Send a single comment as a separate message"""
    comment_text = build_comment_text(comment)
    comment_keyboard = build_comment_keyboard(comment)
    
    bot.send_message(
        chat_id,
        comment_text,
        parse_mode='HTML',
        reply_markup=comment_keyboard
    )


def send_page_header(bot, chat_id, confession_id, page, total_pages, has_prev, has_next):
    """
    Send page header:
    💬 Comments for Confession #42 • Page 1
    [⬅️ Prev] [Next ➡️]
    """
    header_text = f"💬 Comments for Confession #{confession_id} • Page {page}"
    
    # Build navigation buttons
    buttons = []
    if has_prev:
        buttons.append(
            InlineKeyboardButton(
                "⬅️ Prev",
                callback_data=f"comments_page_{confession_id}_{page - 1}"
            )
        )
    if has_next:
        buttons.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"comments_page_{confession_id}_{page + 1}"
            )
        )
    
    keyboard = InlineKeyboardMarkup([buttons]) if buttons else None
    
    bot.send_message(
        chat_id,
        header_text,
        reply_markup=keyboard
    )


def show_comments_for_confession(bot, chat_id, confession_id, page=1):
    """
    Show comments for a confession (used by deep links and direct calls).
    Sends:
    1. Page header with navigation
    2. Each comment as separate message
    
    Args:
        bot: TeleBot instance
        chat_id: Chat ID to send messages to
        confession_id: ID of the confession
        page: Page number (default 1)
    """
    try:
        # Get confession
        try:
            confession = Confession.objects.get(id=confession_id)
        except Confession.DoesNotExist:
            bot.send_message(chat_id, "❌ Confession not found.")
            return
        
        # Get comments for requested page
        comments_data = get_comments(confession, page=page, page_size=PAGE_SIZE)
        
        # Send page header (separate message)
        send_page_header(
            bot,
            chat_id,
            confession_id,
            page,
            comments_data['total_pages'],
            comments_data['has_previous'],
            comments_data['has_next']
        )
        
        # Send each comment as separate message
        if not comments_data['comments']:
            bot.send_message(chat_id, "No comments yet. Be the first to comment!")
        else:
            for comment in comments_data['comments']:
                send_comment_message(bot, chat_id, comment)
        
    except Exception as e:
        logger.error(f"Error in show_comments_for_confession: {e}")
        bot.send_message(chat_id, "❌ An error occurred while loading comments.")


def handle_view_comments(bot, call: CallbackQuery):
    """
    Handle 'View Comments' button callback.
    Wrapper that extracts data from callback and calls show_comments_for_confession.
    """
    try:
        # Extract confession ID
        confession_id = int(call.data.split('_')[2])
        
        # Use the main function
        show_comments_for_confession(bot, call.message.chat.id, confession_id, page=1)
        
        bot.answer_callback_query(call.id, "✅ Comments loaded")
        
    except Exception as e:
        logger.error(f"Error in handle_view_comments: {e}")
        bot.answer_callback_query(call.id, "❌ An error occurred.")


def handle_comments_pagination(bot, call: CallbackQuery):
    """
    Handle pagination (Next/Prev buttons).
    Deletes old pagination message and sends new page.
    """
    try:
        # Extract confession ID and page
        parts = call.data.split('_')
        confession_id = int(parts[2])
        page = int(parts[3])
        
        # Get confession
        try:
            confession = Confession.objects.get(id=confession_id)
        except Confession.DoesNotExist:
            bot.answer_callback_query(call.id, "❌ Confession not found.")
            return
        
        # Get comments for requested page
        comments_data = get_comments(confession, page=page, page_size=PAGE_SIZE)
        
        # Delete the pagination message
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        # Send new page header
        send_page_header(
            bot,
            call.message.chat.id,
            confession_id,
            page,
            comments_data['total_pages'],
            comments_data['has_previous'],
            comments_data['has_next']
        )
        
        # Send comments
        if not comments_data['comments']:
            bot.send_message(call.message.chat.id, "No more comments.")
        else:
            for comment in comments_data['comments']:
                send_comment_message(bot, call.message.chat.id, comment)
        
        bot.answer_callback_query(call.id, f"✅ Loaded page {page}")
        
    except Exception as e:
        logger.error(f"Error in handle_comments_pagination: {e}")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
