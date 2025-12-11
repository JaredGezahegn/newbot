import time, re
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
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
from bot.services.user_service import register_user, toggle_anonymity, get_user_stats
from bot.services.confession_service import create_confession
from bot.services.notification_service import notify_admins_new_confession, notify_user_confession_status
from bot.models import User, Confession, Comment
from bot.handlers import handle_view_comments, handle_comments_pagination, show_comments_for_confession, update_comment_message

# Configure logging
logger = logging.getLogger(__name__)

bot = TeleBot(settings.BOT_TOKEN, parse_mode="HTML", threaded=False)

# Dictionary to store user conversation states
# Format: {user_id: {'state': 'waiting_confession_text', 'data': {...}, 'timestamp': datetime}}
user_states = {}

# Timeout for user states (in seconds) - 10 minutes (increased for confession writing)
USER_STATE_TIMEOUT = 600


def clean_expired_user_states():
    """Remove user states that have expired due to inactivity"""
    current_time = datetime.now()
    expired_users = []
    
    for user_id, state_data in user_states.items():
        if 'timestamp' in state_data:
            time_diff = current_time - state_data['timestamp']
            if time_diff.total_seconds() > USER_STATE_TIMEOUT:
                expired_users.append(user_id)
    
    for user_id in expired_users:
        logger.info(f"Cleaning expired state for user {user_id}")
        del user_states[user_id]


def set_user_state(user_id, state, data=None):
    """Set user state with timestamp"""
    user_states[user_id] = {
        'state': state,
        'data': data or {},
        'timestamp': datetime.now()
    }


def update_user_state_timestamp(user_id):
    """Update timestamp for existing user state"""
    if user_id in user_states:
        user_states[user_id]['timestamp'] = datetime.now()


def check_user_state_timeout(user_id):
    """Check if user state has timed out and clean if necessary"""
    if user_id in user_states:
        current_time = datetime.now()
        state_time = user_states[user_id].get('timestamp', current_time)
        time_diff = current_time - state_time
        
        if time_diff.total_seconds() > USER_STATE_TIMEOUT:
            state = user_states[user_id].get('state', 'unknown')
            del user_states[user_id]
            return True, state
    
    return False, None


# Helper functions for error handling and validation

def validate_confession_id(confession_id_str):
    """
    Validate and parse confession ID from string.
    
    Args:
        confession_id_str: String representation of confession ID
    
    Returns:
        tuple: (is_valid, confession_id or error_message)
    """
    try:
        confession_id = int(confession_id_str)
        if confession_id <= 0:
            return False, "Confession ID must be a positive number."
        return True, confession_id
    except (ValueError, TypeError):
        return False, "Invalid confession ID. Please provide a numeric ID."


def get_confession_or_error(confession_id):
    """
    Get confession by ID or return error message.
    
    Args:
        confession_id: Integer confession ID
    
    Returns:
        tuple: (confession or None, error_message or None)
    """
    try:
        confession = Confession.objects.get(id=confession_id)
        return confession, None
    except Confession.DoesNotExist:
        return None, f"❌ Confession with ID #{confession_id} not found. The confession ID is invalid."
    except DatabaseError as e:
        logger.error(f"Database error fetching confession {confession_id}: {e}")
        return None, "❌ A temporary database issue occurred. Please try again in a moment."


def get_user_or_error(telegram_id):
    """
    Get user by telegram ID or return error message.
    
    Args:
        telegram_id: Telegram user ID
    
    Returns:
        tuple: (user or None, error_message or None)
    """
    try:
        user = User.objects.get(telegram_id=telegram_id)
        return user, None
    except User.DoesNotExist:
        return None, "❌ You need to /register first before using this command."
    except DatabaseError as e:
        logger.error(f"Database error fetching user {telegram_id}: {e}")
        return None, "❌ A temporary database issue occurred. Please try again in a moment."


def handle_database_error(e, context="operation"):
    """
    Log database error and return user-friendly message.
    
    Args:
        e: Exception object
        context: String describing the operation context
    
    Returns:
        str: User-friendly error message
    """
    logger.error(f"Database error during {context}: {e}", exc_info=True)
    return f"❌ A temporary database issue occurred during {context}. Please try again in a moment."


def handle_generic_error(e, context="operation"):
    """
    Log generic error and return user-friendly message.
    
    Args:
        e: Exception object
        context: String describing the operation context
    
    Returns:
        str: User-friendly error message
    """
    logger.error(f"Error during {context}: {e}", exc_info=True)
    return "❌ An unexpected error occurred. Please try again later."


def get_comment_or_error(comment_id):
    """
    Get comment by ID or return error message.
    
    Args:
        comment_id: Integer comment ID
    
    Returns:
        tuple: (comment or None, error_message or None)
    """
    try:
        comment = Comment.objects.get(id=comment_id)
        return comment, None
    except Comment.DoesNotExist:
        return None, f"❌ Comment with ID #{comment_id} not found."
    except DatabaseError as e:
        logger.error(f"Database error fetching comment {comment_id}: {e}")
        return None, "❌ A temporary database issue occurred. Please try again in a moment."


def rebuild_comment_view(comment, chat_id, message_id):
    """
    Rebuild and update the comment view message with current data.
    Shows one comment at a time with its reaction buttons.
    
    Args:
        comment: Comment instance to display
        chat_id: Telegram chat ID
        message_id: Message ID to edit
    """
    from bot.services.comment_service import get_comments
    
    # Refresh comment data
    comment.refresh_from_db()
    confession = comment.confession
    
    # Find which page this comment is on
    all_comments = Comment.objects.filter(
        confession=confession,
        parent_comment=None
    ).order_by('-created_at')
    
    comment_index = list(all_comments.values_list('id', flat=True)).index(comment.id)
    current_page = comment_index + 1
    total_comments = all_comments.count()
    
    # Build response text
    confession_preview = confession.text[:150] + "..." if len(confession.text) > 150 else confession.text
    
    response_text = f"<b>💬 Comments on Confession {confession.id}</b>\n\n"
    response_text += f"<i>{confession_preview}</i>\n\n"
    response_text += f"<b>Comment {current_page} of {total_comments}</b>\n\n"
    
    # Comments are anonymous - don't show commenter identity
    response_text += f"<b>Comment:</b>\n{comment.text}\n\n"
    response_text += f"👍 {comment.like_count}  |  👎 {comment.dislike_count}  |  🚩 {comment.report_count}\n"
    
    # Create inline keyboard
    keyboard = InlineKeyboardMarkup()
    
    # Reaction buttons
    keyboard.row(
        InlineKeyboardButton(f"👍 {comment.like_count}", callback_data=f"like_comment_{comment.id}"),
        InlineKeyboardButton(f"⚠️ Report", callback_data=f"report_comment_{comment.id}"),
        InlineKeyboardButton(f"👎 {comment.dislike_count}", callback_data=f"dislike_comment_{comment.id}"),
        InlineKeyboardButton(f"💬 Reply", callback_data=f"reply_comment_{comment.id}")
    )
    
    # Navigation buttons
    nav_buttons = []
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"comments_page_{confession.id}_{current_page - 1}"))
    if current_page < total_comments:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"comments_page_{confession.id}_{current_page + 1}"))
    if nav_buttons:
        keyboard.row(*nav_buttons)
    
    # Add comment button
    keyboard.row(
        InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession.id}")
    )
    
    # Update message
    bot.edit_message_text(
        response_text,
        chat_id,
        message_id,
        parse_mode='HTML',
        reply_markup=keyboard
    )


# Message Handlers
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    """Handle /start command"""
    telegram_id = message.from_user.id
    user_name = message.from_user.first_name
    
    # Auto-register user if not already registered
    try:
        user, error = get_user_or_error(telegram_id)
        if error:
            # User doesn't exist, register them
            username = message.from_user.username
            from bot.utils import retry_db_operation
            
            @retry_db_operation(max_retries=3)
            def register_with_retry():
                return register_user(telegram_id, user_name, username)
            
            user = register_with_retry()
    except Exception as e:
        logger.error(f"Error in start command: {e}", exc_info=True)
    
    # Check if this is a deep link (e.g., from channel button)
    command_parts = message.text.split()
    if len(command_parts) > 1 and command_parts[1].startswith('comments_'):
        # Extract confession ID from deep link
        try:
            confession_id = int(command_parts[1].split('_')[1])
            logger.info(f"Deep link to comments for confession {confession_id}")
            
            # Get the confession
            confession, error = get_confession_or_error(confession_id)
            if error:
                bot.reply_to(message, error)
                return
            
            # Use the new handler to show comments (separate messages per comment)
            show_comments_for_confession(bot, message.chat.id, confession_id, page=1)
            
            # Send the main keyboard
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            keyboard.add(
                KeyboardButton("✍️ Confess"),
                KeyboardButton("👤 Profile"),
                KeyboardButton("ℹ️ Help")
            )
            bot.send_message(
                message.chat.id,
                "Use the buttons below to navigate:",
                reply_markup=keyboard
            )
            
            return
            
        except Exception as e:
            logger.error(f"Error handling deep link: {e}", exc_info=True)
            # Fall through to normal start message
    
    welcome_text = f"""
👋 <b>Hello {user_name}!</b>

Welcome to the Anonymous Confession Bot!

Use the buttons below to interact with the bot, or type /help for more information.
    """
    
    # Create keyboard with main buttons
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("✍️ Confess"),
        KeyboardButton("👤 Profile"),
        KeyboardButton("ℹ️ Help")
    )
    
    bot.reply_to(message, welcome_text, reply_markup=keyboard)


@bot.message_handler(commands=['help'])
def help_command(message: Message):
    """Handle /help command"""
    help_text = """
<b>📚 Help Menu</b>

<b>Main Buttons:</b>
• ✍️ Confess - Submit a new confession
• 👤 Profile - View your profile and manage settings
• ℹ️ Help - Show this help message

<b>Profile Menu:</b>
• 📝 My Confessions - View all your confessions
• 💬 My Comments - View all your comments
• 🎭 Toggle Anonymity - Switch between anonymous and named posts

<b>Text Commands:</b>
• /comment [id] - Add a comment to a confession
• /comments [id] - View all comments on a confession

<b>Admin Commands:</b>
• /pending - View all pending confessions
• /stats - View system statistics
• /delete [id] - Delete a confession by ID
• /feedbackhelp - View feedback management commands

<b>About Anonymity:</b>
When anonymous mode is ON ✅, your confessions will be posted without your name.
When anonymous mode is OFF ❌, your confessions will show your name.

<b>Channel Interaction:</b>
When a confession is approved, it's posted to the channel with a "View / Add Comments" button. Click it to see and add comments!
    """
    
    # Create inline keyboard with feedback and back buttons
    inline_keyboard = InlineKeyboardMarkup()
    inline_keyboard.row(
        InlineKeyboardButton("📝 Send Feedback", callback_data="send_feedback")
    )
    inline_keyboard.row(
        InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
    )
    
    bot.reply_to(message, help_text, reply_markup=inline_keyboard)


@bot.message_handler(commands=['register'])
def register_command(message: Message):
    """Handle /register command"""
    try:
        telegram_id = message.from_user.id
        first_name = message.from_user.first_name or "User"
        username = message.from_user.username
        
        # Register the user with retry logic
        from bot.utils import retry_db_operation
        
        @retry_db_operation(max_retries=3)
        def register_with_retry():
            return register_user(telegram_id, first_name, username)
        
        user = register_with_retry()
        
        response_text = f"""
✅ <b>Registration Successful!</b>

Welcome, {first_name}! Your profile has been created.

<b>Your Settings:</b>
• Anonymous Mode: {'ON ✅' if user.is_anonymous_mode else 'OFF ❌'}
• Total Confessions: {user.total_confessions}
• Total Comments: {user.total_comments}
• Impact Points: {user.impact_points}

Use the buttons below to get started!
        """
        
        # Create keyboard with main buttons
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(
            KeyboardButton("✍️ Confess"),
            KeyboardButton("👤 Profile"),
            KeyboardButton("ℹ️ Help")
        )
        
        bot.reply_to(message, response_text, reply_markup=keyboard)
        
    except IntegrityError as e:
        # User already exists
        logger.warning(f"Duplicate registration attempt for telegram_id {message.from_user.id}: {e}")
        error_text = "ℹ️ You are already registered! Use the Profile button to view your profile."
        
        # Show main menu
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(
            KeyboardButton("✍️ Confess"),
            KeyboardButton("👤 Profile"),
            KeyboardButton("ℹ️ Help")
        )
        
        bot.reply_to(message, error_text, reply_markup=keyboard)
    except DatabaseError as e:
        logger.error(f"Database error during registration: {e}", exc_info=True)
        error_text = f"❌ Database connection error. Please try again in a moment.\n\nError details: {str(e)[:100]}"
        bot.reply_to(message, error_text)
    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}", exc_info=True)
        error_text = f"❌ An unexpected error occurred. Please try again.\n\nError: {str(e)[:100]}"
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['anonymous_on'])
def anonymous_on_command(message: Message):
    """Handle /anonymous_on command"""
    try:
        telegram_id = message.from_user.id
        
        # Get the user
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Enable anonymity
        user = toggle_anonymity(user, True)
        
        response_text = """
✅ <b>Anonymous Mode Enabled</b>

Your future confessions will be posted anonymously without your name.
        """
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "updating anonymity setting")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "updating anonymity setting")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['anonymous_off'])
def anonymous_off_command(message: Message):
    """Handle /anonymous_off command"""
    try:
        telegram_id = message.from_user.id
        
        # Get the user
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Disable anonymity
        user = toggle_anonymity(user, False)
        
        response_text = """
✅ <b>Anonymous Mode Disabled</b>

Your future confessions will be posted with your name.
        """
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "updating anonymity setting")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "updating anonymity setting")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['profile'])
def profile_command(message: Message):
    """Handle /profile command"""
    try:
        telegram_id = message.from_user.id
        
        # Get the user
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Get user stats
        stats = get_user_stats(user)
        
        response_text = f"""
👤 <b>Your Profile</b>

<b>Name:</b> {user.first_name}
<b>Username:</b> @{user.username if user.username else 'N/A'}
<b>Anonymous Mode:</b> {'ON' if user.is_anonymous_mode else 'OFF'}

<b>Statistics:</b>
• Approved Confessions: {stats['total_confessions']}
• Total Comments: {stats['total_comments']}
• Impact Points: {stats['impact_points']}
• Community Acceptance Score: {stats['acceptance_score']}%

Use /myconfessions to view your confessions.
Use /mycomments to view your comments.
        """
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "fetching profile")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "fetching profile")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['myconfessions'])
def myconfessions_command(message: Message):
    """Handle /myconfessions command"""
    try:
        telegram_id = message.from_user.id
        
        # Get the user
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Get user's confessions
        confessions = Confession.objects.filter(user=user).order_by('-created_at')[:10]
        
        if not confessions:
            bot.reply_to(message, "📝 You haven't submitted any confessions yet. Use /confess to submit one!")
            return
        
        response_text = "<b>📝 Your Confessions</b>\n\n"
        
        for confession in confessions:
            status_emoji = {
                'pending': '⏳',
                'approved': '✅',
                'rejected': '❌'
            }.get(confession.status, '❓')
            
            text_preview = confession.text[:50] + "..." if len(confession.text) > 50 else confession.text
            
            response_text += f"{status_emoji} <b>ID {confession.id}</b> - {confession.status.upper()}\n"
            response_text += f"   {text_preview}\n"
            response_text += f"   <i>{confession.created_at.strftime('%Y-%m-%d %H:%M')}</i>\n\n"
        
        if len(confessions) == 10:
            response_text += "\n<i>Showing your 10 most recent confessions.</i>"
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "fetching confessions")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "fetching confessions")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['mycomments'])
def mycomments_command(message: Message):
    """Handle /mycomments command"""
    try:
        telegram_id = message.from_user.id
        
        # Get the user
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Get user's comments
        comments = Comment.objects.filter(user=user).select_related('confession').order_by('-created_at')[:10]
        
        if not comments:
            bot.reply_to(message, "💬 You haven't posted any comments yet.")
            return
        
        response_text = "<b>💬 Your Comments</b>\n\n"
        
        for comment in comments:
            text_preview = comment.text[:50] + "..." if len(comment.text) > 50 else comment.text
            confession_preview = comment.confession.text[:30] + "..." if len(comment.confession.text) > 30 else comment.confession.text
            
            response_text += f"<b>Comment ID {comment.id}</b>\n"
            response_text += f"   {text_preview}\n"
            response_text += f"   👍 {comment.like_count} | 👎 {comment.dislike_count}\n"
            response_text += f"   On confession: {confession_preview}\n"
            response_text += f"   <i>{comment.created_at.strftime('%Y-%m-%d %H:%M')}</i>\n\n"
        
        if len(comments) == 10:
            response_text += "\n<i>Showing your 10 most recent comments.</i>"
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "fetching comments")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "fetching comments")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['confess'])
def confess_command(message: Message):
    """Handle /confess command - start confession submission flow"""
    try:
        telegram_id = message.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Set user state to waiting for confession text
        set_user_state(telegram_id, 'waiting_confession_text')
        
        # Inform user about their current anonymity setting
        anonymity_status = "anonymously" if user.is_anonymous_mode else "with your name"
        
        response_text = f"""
📝 <b>Submit a Confession</b>

Your confession will be posted <b>{anonymity_status} on @dduvents</b>.

Please type your confession below.
        """
        
        # Create keyboard with Cancel button
        from telebot.types import ReplyKeyboardMarkup, KeyboardButton
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton("❌ Cancel"))
        
        bot.reply_to(message, response_text, reply_markup=keyboard)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "starting confession")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "starting confession")
        bot.reply_to(message, error_text)


def is_admin(telegram_id):
    """
    Check if a user has admin privileges.
    
    Args:
        telegram_id: Telegram user ID
    
    Returns:
        bool: True if user is admin, False otherwise
    """
    # Check if user is in ADMINS list from settings
    if telegram_id in settings.ADMINS:
        return True
    
    # Check if user has is_admin flag in database
    try:
        user = User.objects.get(telegram_id=telegram_id)
        return user.is_admin
    except User.DoesNotExist:
        return False


@bot.message_handler(commands=['pending'])
def pending_command(message: Message):
    """Handle /pending command - view pending confessions (admin only)"""
    try:
        telegram_id = message.from_user.id
        
        # Check admin permission
        if not is_admin(telegram_id):
            bot.reply_to(message, "❌ You don't have permission to use this command. This command is only available to administrators.")
            return
        
        # Get pending confessions
        from bot.services.confession_service import get_pending_confessions
        pending_confessions = get_pending_confessions()
        
        if not pending_confessions:
            bot.reply_to(message, "✅ No pending confessions at the moment.")
            return
        
        # Send summary first
        summary_text = f"<b>📋 Pending Confessions ({pending_confessions.count()})</b>\n\n"
        if pending_confessions.count() > 10:
            summary_text += f"<i>Showing first 10 confessions. Use Django admin to see all.</i>\n\n"
        
        bot.reply_to(message, summary_text)
        
        # Send each confession as a separate message with full text
        for confession in pending_confessions[:10]:  # Limit to 10 to avoid spam
            author = confession.user.first_name
            if confession.user.username:
                author += f" (@{confession.user.username})"
            
            # Build confession header
            header = f"""<b>📝 Confession ID {confession.id}</b>

<b>From:</b> {author}
<b>Anonymous:</b> {'Yes' if confession.is_anonymous else 'No'}
<b>Submitted:</b> {confession.created_at.strftime('%Y-%m-%d %H:%M')}

<b>Full Text:</b>
"""
            
            # Check if confession text is too long for a single message
            # Telegram limit is 4096 chars, leave room for header and buttons
            max_text_length = 3500
            confession_full_text = confession.text
            
            if len(header) + len(confession_full_text) > max_text_length:
                # Split into multiple messages
                confession_text = header + confession_full_text[:max_text_length - len(header)] + "\n\n<i>... (continued in next message)</i>"
                bot.send_message(message.chat.id, confession_text, parse_mode='HTML')
                
                # Send remaining text
                remaining_text = confession_full_text[max_text_length - len(header):]
                bot.send_message(message.chat.id, f"<i>(Continuation of Confession {confession.id})</i>\n\n{remaining_text}", parse_mode='HTML')
            else:
                confession_text = header + confession_full_text
            
            # Create inline keyboard with approve/reject buttons
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{confession.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{confession.id}")
            )
            
            # Send the confession with buttons (or just buttons if we already sent the text)
            if len(header) + len(confession_full_text) <= max_text_length:
                bot.send_message(message.chat.id, confession_text, parse_mode='HTML', reply_markup=keyboard)
            else:
                # Buttons on a separate message
                bot.send_message(message.chat.id, f"<b>Actions for Confession {confession.id}:</b>", parse_mode='HTML', reply_markup=keyboard)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "fetching pending confessions")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "fetching pending confessions")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['stats'])
def stats_command(message: Message):
    """Handle /stats command - view system statistics (admin only)"""
    try:
        telegram_id = message.from_user.id
        
        # Check admin permission
        if not is_admin(telegram_id):
            bot.reply_to(message, "❌ You don't have permission to use this command. This command is only available to administrators.")
            return
        
        # Get statistics
        total_users = User.objects.count()
        total_confessions = Confession.objects.count()
        pending_confessions = Confession.objects.filter(status='pending').count()
        approved_confessions = Confession.objects.filter(status='approved').count()
        rejected_confessions = Confession.objects.filter(status='rejected').count()
        total_comments = Comment.objects.count()
        
        response_text = f"""
📊 <b>System Statistics</b>

<b>Users:</b>
• Total Registered Users: {total_users}

<b>Confessions:</b>
• Total Confessions: {total_confessions}
• Pending: {pending_confessions}
• Approved: {approved_confessions}
• Rejected: {rejected_confessions}

<b>Engagement:</b>
• Total Comments: {total_comments}

<i>Last updated: {timezone.now().strftime('%Y-%m-%d %H:%M UTC')}</i>
        """
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "fetching statistics")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "fetching statistics")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['delete'])
def delete_command(message: Message):
    """Handle /delete command - delete a confession by ID (admin only)"""
    try:
        telegram_id = message.from_user.id
        
        # Check admin permission
        if not is_admin(telegram_id):
            bot.reply_to(message, "❌ You don't have permission to use this command. This command is only available to administrators.")
            return
        
        # Parse confession ID from command
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.reply_to(message, "❌ Please provide a confession ID. Usage: /delete <confession_id>")
            return
        
        # Validate confession ID
        is_valid, result = validate_confession_id(command_parts[1])
        if not is_valid:
            bot.reply_to(message, f"❌ {result}")
            return
        
        confession_id = result
        
        # Get the confession
        confession, error = get_confession_or_error(confession_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Delete the confession
        from bot.services.confession_service import delete_confession
        
        confession_preview = confession.text[:100] + "..." if len(confession.text) > 100 else confession.text
        delete_confession(confession, bot_instance=bot)
        
        response_text = f"""
✅ <b>Confession Deleted</b>

Confession ID {confession_id} has been deleted from the database.

<b>Preview:</b>
{confession_preview}
        """
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "deleting confession")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "deleting confession")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['viewfeedback'])
def view_feedback_command(message: Message):
    """Handle /viewfeedback command - admin only"""
    telegram_id = message.from_user.id
    if not is_admin(telegram_id):
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    try:
        from bot.models import Feedback
        # Get recent feedback (last 10)
        feedbacks = Feedback.objects.all().order_by('-created_at')[:10]
        
        if not feedbacks:
            bot.reply_to(message, "📭 No feedback received yet.")
            return
        
        # Send header message
        header_text = f"📬 <b>Recent Feedback ({feedbacks.count()} items)</b>\n\nEach feedback is shown below with action buttons:"
        bot.reply_to(message, header_text, parse_mode='HTML')
        
        # Send each feedback as separate message with buttons
        for feedback in feedbacks:
            send_feedback_with_buttons(bot, message.chat.id, feedback)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error retrieving feedback.\n\nError: {str(e)[:200]}")
        logger.error(f"Error in view_feedback: {e}", exc_info=True)


def notify_user_feedback_status(feedback, status_change, admin_name=None):
    """Notify user when their feedback status changes"""
    try:
        user = feedback.user
        
        # Check if this is praise/supportive feedback for special message
        is_praise = False
        if feedback.admin_notes:
            # Check if feedback was categorized as praise (multiple variations)
            admin_notes_lower = feedback.admin_notes.lower()
            is_praise = (
                'praise' in admin_notes_lower or 
                'categorized as \'praise\'' in admin_notes_lower or
                'categorized as "praise"' in admin_notes_lower or
                'category: praise' in admin_notes_lower
            )
            # Debug logging
            logger.info(f"Checking praise for feedback #{feedback.id}: admin_notes='{feedback.admin_notes}', is_praise={is_praise}")
        
        # Base messages (admin stays anonymous)
        if is_praise and status_change == 'resolved':
            # Special appreciation message for praise feedback
            message = f"""
💝 <b>Thank You for Your Kind Words!</b>

We received and appreciated your supportive feedback!

<b>Your message:</b>
{feedback.text[:200]}{'...' if len(feedback.text) > 200 else ''}

<b>Status:</b> Acknowledged with Gratitude ✅

Your encouragement means a lot to our team and motivates us to keep improving the bot. Thank you for taking the time to share your positive experience!

We're grateful to have supportive users like you in our community! 🙏
            """
        else:
            status_messages = {
                'reviewed': f"""
📬 <b>Feedback Update</b>

Your feedback has been reviewed by our admin team.

<b>Your feedback:</b>
{feedback.text[:200]}{'...' if len(feedback.text) > 200 else ''}

<b>Status:</b> Under Review 🔵

We'll keep you updated on any progress!
                """,
                'resolved': f"""
📬 <b>Feedback Resolved</b>

Your feedback has been resolved!

<b>Your feedback:</b>
{feedback.text[:200]}{'...' if len(feedback.text) > 200 else ''}

<b>Status:</b> Resolved ✅

Thank you for helping us improve the bot!
                """,
                'reopened': f"""
📬 <b>Feedback Reopened</b>

Your feedback has been reopened for further review.

<b>Your feedback:</b>
{feedback.text[:200]}{'...' if len(feedback.text) > 200 else ''}

<b>Status:</b> Under Review 🔵

We're taking another look at your feedback.
                """
            }
            message = status_messages.get(status_change)
        
        
        if message:
            bot.send_message(user.telegram_id, message, parse_mode='HTML')
            logger.info(f"Notified user {user.telegram_id} about feedback #{feedback.id} status change: {status_change}")
    
    except Exception as e:
        logger.error(f"Error notifying user about feedback status change: {e}")


def send_feedback_with_buttons(bot, chat_id, feedback):
    """Send a single feedback item with action buttons"""
    status_emoji = {
        'pending': '🟡',
        'reviewed': '🔵', 
        'resolved': '🟢'
    }.get(feedback.status, '⚪')
    
    # Build feedback text
    feedback_text = f"""
{status_emoji} <b>Feedback #{feedback.id}</b> - {feedback.status.title()}

<b>Submitted:</b> {feedback.created_at.strftime('%b %d, %Y • %I:%M %p')}

<b>Feedback:</b>
{feedback.text}
    """
    
    # Add admin notes if they exist
    if feedback.admin_notes:
        feedback_text += f"\n\n<b>Admin Notes:</b>\n{feedback.admin_notes}"
    
    # Add review info if reviewed
    if feedback.reviewed_by:
        feedback_text += f"\n\n<b>Reviewed by:</b> {feedback.reviewed_by.username or feedback.reviewed_by.first_name}"
        feedback_text += f"\n<b>Reviewed at:</b> {feedback.reviewed_at.strftime('%b %d, %Y • %I:%M %p')}"
    
    # Create inline keyboard with action buttons
    keyboard = InlineKeyboardMarkup()
    
    # Row 1: Quick actions based on status
    if feedback.status == 'pending':
        keyboard.row(
            InlineKeyboardButton("✅ Resolve", callback_data=f"resolve_feedback_{feedback.id}"),
            InlineKeyboardButton("👀 Mark Reviewed", callback_data=f"review_feedback_{feedback.id}")
        )
    elif feedback.status == 'reviewed':
        keyboard.row(
            InlineKeyboardButton("✅ Resolve", callback_data=f"resolve_feedback_{feedback.id}"),
            InlineKeyboardButton("⏪ Mark Pending", callback_data=f"pending_feedback_{feedback.id}")
        )
    else:  # resolved
        keyboard.row(
            InlineKeyboardButton("🔄 Reopen", callback_data=f"reopen_feedback_{feedback.id}")
        )
    
    # Row 2: Management actions
    keyboard.row(
        InlineKeyboardButton("📝 Add Note", callback_data=f"add_note_feedback_{feedback.id}"),
        InlineKeyboardButton("🏷️ Categorize", callback_data=f"categorize_feedback_{feedback.id}")
    )
    
    # Row 3: Priority and details
    keyboard.row(
        InlineKeyboardButton("⚡ Set Priority", callback_data=f"priority_feedback_{feedback.id}"),
        InlineKeyboardButton("📊 View Details", callback_data=f"details_feedback_{feedback.id}")
    )
    
    bot.send_message(
        chat_id,
        feedback_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )


@bot.message_handler(commands=['feedback'])
def view_single_feedback_command(message: Message):
    """Handle /feedback <id> command - admin only"""
    telegram_id = message.from_user.id
    if not is_admin(telegram_id):
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    try:
        # Parse feedback ID
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Usage: /feedback <id>")
            return
        
        feedback_id = int(parts[1])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Use the same function to send feedback with buttons
        send_feedback_with_buttons(bot, message.chat.id, feedback)
        
    except ValueError:
        bot.reply_to(message, "❌ Invalid feedback ID. Please provide a number.")
    except Feedback.DoesNotExist:
        bot.reply_to(message, "❌ Feedback not found.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error retrieving feedback.\n\nError: {str(e)[:200]}")
        logger.error(f"Error in view_single_feedback: {e}", exc_info=True)


@bot.message_handler(commands=['resolvefeedback'])
def resolve_feedback_command(message: Message):
    """Handle /resolvefeedback <id> command - admin only"""
    telegram_id = message.from_user.id
    if not is_admin(telegram_id):
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    try:
        # Parse feedback ID
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Usage: /resolvefeedback <id>")
            return
        
        feedback_id = int(parts[1])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Update feedback
        feedback.status = 'resolved'
        feedback.reviewed_by = admin_user
        feedback.reviewed_at = timezone.now()
        feedback.save()
        
        # Notify the user
        notify_user_feedback_status(feedback, 'resolved')
        
        bot.reply_to(
            message, 
            f"✅ Feedback #{feedback_id} marked as resolved. User has been notified.",
            parse_mode='HTML'
        )
    except ValueError:
        bot.reply_to(message, "❌ Invalid feedback ID. Please provide a number.")
    except Feedback.DoesNotExist:
        bot.reply_to(message, "❌ Feedback not found.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error resolving feedback.\n\nError: {str(e)[:200]}")
        logger.error(f"Error in resolve_feedback: {e}", exc_info=True)


@bot.message_handler(commands=['addnote'])
def add_feedback_note_command(message: Message):
    """Handle /addnote <id> <note> command - admin only"""
    telegram_id = message.from_user.id
    if not is_admin(telegram_id):
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    try:
        # Parse feedback ID and note
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(message, "❌ Usage: /addnote <id> <note>\n\nExample: /addnote 5 Fixed the bug mentioned in this feedback")
            return
        
        feedback_id = int(parts[1])
        note_text = parts[2]
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Add note to existing admin notes
        current_notes = feedback.admin_notes or ""
        timestamp = timezone.now().strftime('%b %d, %Y • %I:%M %p')
        admin_name = admin_user.username or admin_user.first_name
        
        new_note = f"[{timestamp}] {admin_name}: {note_text}"
        
        if current_notes:
            feedback.admin_notes = current_notes + "\n\n" + new_note
        else:
            feedback.admin_notes = new_note
        
        # Update review info
        feedback.reviewed_by = admin_user
        feedback.reviewed_at = timezone.now()
        if feedback.status == 'pending':
            feedback.status = 'reviewed'
        
        feedback.save()
        
        bot.reply_to(
            message, 
            f"✅ Note added to feedback #{feedback_id}.\n\n<b>Note:</b> {note_text}",
            parse_mode='HTML'
        )
    except ValueError:
        bot.reply_to(message, "❌ Invalid feedback ID. Please provide a number.")
    except Feedback.DoesNotExist:
        bot.reply_to(message, "❌ Feedback not found.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error adding note.\n\nError: {str(e)[:200]}")
        logger.error(f"Error in add_feedback_note: {e}", exc_info=True)


@bot.message_handler(commands=['categorize'])
def categorize_feedback_command(message: Message):
    """Handle /categorize <id> <category> command - admin only"""
    telegram_id = message.from_user.id
    if not is_admin(telegram_id):
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    try:
        # Parse feedback ID and category
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            categories = "bug, feature, improvement, question, complaint, praise, other"
            bot.reply_to(message, f"❌ Usage: /categorize <id> <category>\n\n<b>Available categories:</b>\n{categories}\n\nExample: /categorize 5 bug")
            return
        
        feedback_id = int(parts[1])
        category = parts[2].lower()
        
        # Validate category
        valid_categories = ['bug', 'feature', 'improvement', 'question', 'complaint', 'praise', 'other']
        if category not in valid_categories:
            bot.reply_to(message, f"❌ Invalid category. Choose from: {', '.join(valid_categories)}")
            return
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Update category (store in admin_notes for now since we don't have a category field)
        timestamp = timezone.now().strftime('%b %d, %Y • %I:%M %p')
        admin_name = admin_user.username or admin_user.first_name
        
        category_note = f"[{timestamp}] {admin_name}: Categorized as '{category.upper()}'"
        
        current_notes = feedback.admin_notes or ""
        if current_notes:
            feedback.admin_notes = current_notes + "\n\n" + category_note
        else:
            feedback.admin_notes = category_note
        
        # Update review info
        feedback.reviewed_by = admin_user
        feedback.reviewed_at = timezone.now()
        if feedback.status == 'pending':
            feedback.status = 'reviewed'
        
        feedback.save()
        
        category_emoji = {
            'bug': '🐛',
            'feature': '✨',
            'improvement': '🔧',
            'question': '❓',
            'complaint': '😠',
            'praise': '👏',
            'other': '📝'
        }.get(category, '📝')
        
        bot.reply_to(
            message, 
            f"✅ Feedback #{feedback_id} categorized as {category_emoji} <b>{category.upper()}</b>",
            parse_mode='HTML'
        )
    except ValueError:
        bot.reply_to(message, "❌ Invalid feedback ID. Please provide a number.")
    except Feedback.DoesNotExist:
        bot.reply_to(message, "❌ Feedback not found.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error categorizing feedback.\n\nError: {str(e)[:200]}")
        logger.error(f"Error in categorize_feedback: {e}", exc_info=True)


@bot.message_handler(commands=['priority'])
def set_feedback_priority_command(message: Message):
    """Handle /priority <id> <level> command - admin only"""
    telegram_id = message.from_user.id
    if not is_admin(telegram_id):
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    try:
        # Parse feedback ID and priority
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ Usage: /priority <id> <level>\n\n<b>Priority levels:</b>\nlow, medium, high, urgent\n\nExample: /priority 5 high")
            return
        
        feedback_id = int(parts[1])
        priority = parts[2].lower()
        
        # Validate priority
        valid_priorities = ['low', 'medium', 'high', 'urgent']
        if priority not in valid_priorities:
            bot.reply_to(message, f"❌ Invalid priority. Choose from: {', '.join(valid_priorities)}")
            return
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Update priority (store in admin_notes)
        timestamp = timezone.now().strftime('%b %d, %Y • %I:%M %p')
        admin_name = admin_user.username or admin_user.first_name
        
        priority_note = f"[{timestamp}] {admin_name}: Priority set to '{priority.upper()}'"
        
        current_notes = feedback.admin_notes or ""
        if current_notes:
            feedback.admin_notes = current_notes + "\n\n" + priority_note
        else:
            feedback.admin_notes = priority_note
        
        # Update review info
        feedback.reviewed_by = admin_user
        feedback.reviewed_at = timezone.now()
        if feedback.status == 'pending':
            feedback.status = 'reviewed'
        
        feedback.save()
        
        priority_emoji = {
            'low': '🟢',
            'medium': '🟡',
            'high': '🟠',
            'urgent': '🔴'
        }.get(priority, '⚪')
        
        bot.reply_to(
            message, 
            f"✅ Feedback #{feedback_id} priority set to {priority_emoji} <b>{priority.upper()}</b>",
            parse_mode='HTML'
        )
    except ValueError:
        bot.reply_to(message, "❌ Invalid feedback ID. Please provide a number.")
    except Feedback.DoesNotExist:
        bot.reply_to(message, "❌ Feedback not found.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error setting priority.\n\nError: {str(e)[:200]}")
        logger.error(f"Error in set_feedback_priority: {e}", exc_info=True)


@bot.message_handler(commands=['feedbackstats'])
def feedback_stats_command(message: Message):
    """Handle /feedbackstats command - admin only"""
    telegram_id = message.from_user.id
    if not is_admin(telegram_id):
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    try:
        from bot.models import Feedback
        
        # Get statistics
        total_feedback = Feedback.objects.count()
        pending_count = Feedback.objects.filter(status='pending').count()
        reviewed_count = Feedback.objects.filter(status='reviewed').count()
        resolved_count = Feedback.objects.filter(status='resolved').count()
        
        # Get recent feedback (last 7 days)
        from datetime import timedelta
        week_ago = timezone.now() - timedelta(days=7)
        recent_count = Feedback.objects.filter(created_at__gte=week_ago).count()
        
        response = f"""
📊 <b>Feedback Statistics</b>

<b>Total Feedback:</b> {total_feedback}

<b>By Status:</b>
🟡 Pending: {pending_count}
🔵 Reviewed: {reviewed_count}
🟢 Resolved: {resolved_count}

<b>Recent Activity:</b>
📅 Last 7 days: {recent_count} new feedback

<b>Response Rate:</b>
{((reviewed_count + resolved_count) / max(total_feedback, 1) * 100):.1f}% of feedback has been addressed

<i>Last updated: {timezone.now().strftime('%b %d, %Y • %I:%M %p')}</i>
        """
        
        bot.reply_to(message, response, parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ Error retrieving feedback statistics.\n\nError: {str(e)[:200]}")
        logger.error(f"Error in feedback_stats: {e}", exc_info=True)


@bot.message_handler(commands=['feedbackhelp'])
def feedback_help_command(message: Message):
    """Handle /feedbackhelp command - admin only"""
    telegram_id = message.from_user.id
    if not is_admin(telegram_id):
        bot.reply_to(message, "❌ This command is only available to administrators.")
        return
    
    help_text = """
📚 <b>Feedback Management Commands</b>

<b>📋 Viewing Feedback:</b>
• <code>/viewfeedback</code> - List recent feedback
• <code>/feedback &lt;id&gt;</code> - View specific feedback details
• <code>/feedbackstats</code> - View feedback statistics

<b>🏷️ Organizing Feedback:</b>
• <code>/categorize &lt;id&gt; &lt;category&gt;</code> - Categorize feedback
  Categories: bug, feature, improvement, question, complaint, praise, other
• <code>/priority &lt;id&gt; &lt;level&gt;</code> - Set priority level
  Levels: low, medium, high, urgent

<b>📝 Managing Feedback:</b>
• <code>/addnote &lt;id&gt; &lt;note&gt;</code> - Add admin note
• <code>/resolvefeedback &lt;id&gt;</code> - Mark as resolved

<b>💡 Examples:</b>
<code>/categorize 5 bug</code>
<code>/priority 5 high</code>
<code>/addnote 5 Fixed in version 2.1</code>
<code>/resolvefeedback 5</code>

<b>🔄 Workflow Suggestion:</b>
1. View new feedback with <code>/viewfeedback</code>
2. Categorize with <code>/categorize</code>
3. Set priority with <code>/priority</code>
4. Add progress notes with <code>/addnote</code>
5. Mark resolved with <code>/resolvefeedback</code>
    """
    
    bot.reply_to(message, help_text, parse_mode='HTML')


@bot.message_handler(commands=['comment'])
def comment_command(message: Message):
    """Handle /comment command - add a comment to a confession"""
    try:
        telegram_id = message.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Parse confession ID from command
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.reply_to(message, "❌ Please provide a confession ID. Usage: /comment <confession_id>")
            return
        
        # Validate confession ID
        is_valid, result = validate_confession_id(command_parts[1])
        if not is_valid:
            bot.reply_to(message, f"❌ {result}")
            return
        
        confession_id = result
        
        # Get the confession
        confession, error = get_confession_or_error(confession_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Check if confession is approved
        if confession.status != 'approved':
            bot.reply_to(message, f"❌ You can only comment on approved confessions. This confession is currently {confession.status}.")
            return
        
        # Set user state to waiting for comment text
        set_user_state(telegram_id, 'waiting_comment_text', {'confession_id': confession_id})
        
        # Show confession preview
        confession_preview = confession.text[:200] + "..." if len(confession.text) > 200 else confession.text
        
        response_text = f"""
💬 <b>Add a Comment</b>

<b>Confession {confession_id}:</b>
{confession_preview}

Please type your comment below. You can write up to 1000 characters.

Type /cancel to cancel.
        """
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "starting comment")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "starting comment")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['comments'])
def comments_command(message: Message):
    """Handle /comments command - view comments for a confession"""
    try:
        telegram_id = message.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Parse confession ID from command
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.reply_to(message, "❌ Please provide a confession ID. Usage: /comments <confession_id>")
            return
        
        # Validate confession ID
        is_valid, result = validate_confession_id(command_parts[1])
        if not is_valid:
            bot.reply_to(message, f"❌ {result}")
            return
        
        confession_id = result
        
        # Get the confession
        confession, error = get_confession_or_error(confession_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Get comments (first page)
        from bot.services.comment_service import get_comments
        comments_data = get_comments(confession, page=1, page_size=10)
        
        if not comments_data['comments']:
            bot.reply_to(message, f"💬 No comments yet on confession {confession_id}. Be the first to comment using /comment {confession_id}")
            return
        
        # Build response text
        confession_preview = confession.text[:100] + "..." if len(confession.text) > 100 else confession.text
        
        response_text = f"<b>💬 Comments on Confession {confession_id}</b>\n\n"
        response_text += f"<i>{confession_preview}</i>\n\n"
        response_text += f"<b>Comments (Page {comments_data['current_page']} of {comments_data['total_pages']}):</b>\n\n"
        
        for comment in comments_data['comments']:
            # Comments are anonymous - don't show commenter identity
            comment_text = comment.text[:150] + "..." if len(comment.text) > 150 else comment.text
            
            response_text += f"<b>Comment #{comment.id}</b>\n"
            response_text += f"{comment_text}\n"
            response_text += f"👍 {comment.like_count} | 👎 {comment.dislike_count} | 🚩 {comment.report_count}\n"
            response_text += f"<i>{comment.created_at.strftime('%Y-%m-%d %H:%M')}</i>\n\n"
        
        # Add pagination info
        if comments_data['has_next'] or comments_data['has_previous']:
            response_text += f"\n<i>Use /comments{confession_id} to view comments. Pagination coming soon!</i>"
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "fetching comments")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "fetching comments")
        bot.reply_to(message, error_text)


@bot.message_handler(commands=['cancel'])
def cancel_command(message: Message):
    """Handle /cancel command - cancel current operation"""
    telegram_id = message.from_user.id
    
    if telegram_id in user_states:
        state = user_states[telegram_id].get('state')
        del user_states[telegram_id]
        
        if state == 'waiting_confession_text':
            bot.reply_to(message, "❌ Confession submission cancelled.")
        elif state == 'waiting_confession_confirmation':
            bot.reply_to(message, "❌ Confession submission cancelled.")
        elif state == 'waiting_comment_text':
            bot.reply_to(message, "❌ Comment submission cancelled.")
        elif state == 'waiting_reply_text':
            bot.reply_to(message, "❌ Reply submission cancelled.")
        elif state == 'waiting_feedback_note':
            bot.reply_to(message, "❌ Note addition cancelled.")
        else:
            bot.reply_to(message, "✅ Operation cancelled.")
    else:
        bot.reply_to(message, "ℹ️ No active operation to cancel.")


# Keyboard button handlers
@bot.message_handler(func=lambda message: message.text == "✍️ Confess")
def button_confess(message: Message):
    """Handle Confess button"""
    confess_command(message)


@bot.message_handler(func=lambda message: message.text == "👤 Profile")
def button_profile(message: Message):
    """Handle Profile button - show profile menu"""
    telegram_id = message.from_user.id
    
    # Check if user is registered
    user, error = get_user_or_error(telegram_id)
    if error:
        bot.reply_to(message, error)
        return
    
    # Get user stats
    try:
        stats = get_user_stats(user)
        
        profile_text = f"""
👤 <b>Your Profile</b>

<b>Name:</b> {user.first_name}
<b>Username:</b> @{user.username if user.username else 'N/A'}
<b>Anonymous Mode:</b> {'ON ✅' if user.is_anonymous_mode else 'OFF ❌'}

<b>Statistics:</b>
• Approved Confessions: {stats['total_confessions']}
• Total Comments: {stats['total_comments']}
• Impact Points: {stats['impact_points']}
• Community Acceptance Score: {stats['acceptance_score']}%

Use the buttons below to manage your profile:
        """
        
        # Create profile submenu keyboard
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(
            KeyboardButton("📝 My Confessions"),
            KeyboardButton("💬 My Comments")
        )
        keyboard.add(
            KeyboardButton("🎭 Toggle Anonymity"),
            KeyboardButton("🔙 Back to Menu")
        )
        
        bot.reply_to(message, profile_text, reply_markup=keyboard)
        
    except Exception as e:
        error_text = handle_generic_error(e, "fetching profile")
        bot.reply_to(message, error_text)


@bot.message_handler(func=lambda message: message.text == "ℹ️ Help")
def button_help(message: Message):
    """Handle Help button"""
    help_command(message)


@bot.message_handler(func=lambda message: message.text == "🔙 Back to Menu")
def button_back_to_menu(message: Message):
    """Handle Back to Menu button"""
    # Show main menu
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("✍️ Confess"),
        KeyboardButton("👤 Profile"),
        KeyboardButton("ℹ️ Help")
    )
    
    bot.reply_to(message, "Main Menu:", reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == "📝 My Confessions")
def button_my_confessions(message: Message):
    """Handle My Confessions button"""
    myconfessions_command(message)


@bot.message_handler(func=lambda message: message.text == "💬 My Comments")
def button_my_comments(message: Message):
    """Handle My Comments button"""
    mycomments_command(message)


@bot.message_handler(func=lambda message: message.text == "🎭 Toggle Anonymity")
def button_toggle_anonymity(message: Message):
    """Handle Toggle Anonymity button"""
    telegram_id = message.from_user.id
    
    try:
        # Get the user
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.reply_to(message, error)
            return
        
        # Toggle anonymity
        new_state = not user.is_anonymous_mode
        user = toggle_anonymity(user, new_state)
        
        status = "ON ✅" if new_state else "OFF ❌"
        response_text = f"""
🎭 <b>Anonymity Mode {status}</b>

Your future confessions will be posted {'anonymously without your name' if new_state else 'with your name'}.
        """
        
        bot.reply_to(message, response_text)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "toggling anonymity")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "toggling anonymity")
        bot.reply_to(message, error_text)


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_confession_'))
def handle_confession_confirmation(call: CallbackQuery):
    """Handle confession confirmation callback"""
    try:
        telegram_id = call.from_user.id
        action = call.data.split('_')[2]  # 'yes' or 'no'
        
        # Check if user has a pending confession
        if telegram_id not in user_states or user_states[telegram_id].get('state') != 'waiting_confession_confirmation':
            bot.answer_callback_query(call.id, "❌ This confirmation has expired. Please use /confess to submit a new confession.")
            return
        
        if action == 'yes':
            # Submit the confession
            confession_text = user_states[telegram_id]['data']['text']
            
            user, error = get_user_or_error(telegram_id)
            if error:
                bot.answer_callback_query(call.id, "❌ User not found. Please /register first.")
                del user_states[telegram_id]
                return
            
            try:
                # Create the confession
                confession = create_confession(user, confession_text)
                
                # Notify admins
                notify_admins_new_confession(confession, bot)
                
                # Clear user state
                del user_states[telegram_id]
                
                # Update the message to show success
                success_text = f"""
✅ <b>Confession Submitted Successfully!</b>

Your confession with ID {confession.id} has been submitted and is now pending admin review.

You will be notified once it's reviewed.

<b>Confession Preview:</b>
{confession_text[:200]}{'...' if len(confession_text) > 200 else ''}
                """
                
                bot.edit_message_text(
                    success_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='HTML'
                )
                
                # Restore main menu keyboard
                from telebot.types import ReplyKeyboardMarkup, KeyboardButton
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                keyboard.add(
                    KeyboardButton("✍️ Confess"),
                    KeyboardButton("👤 Profile"),
                    KeyboardButton("ℹ️ Help")
                )
                
                bot.send_message(
                    call.message.chat.id,
                    "You can now submit another confession or use the menu below.",
                    reply_markup=keyboard
                )
                
                bot.answer_callback_query(call.id, "✅ Confession submitted!")
                
            except ValueError as e:
                # Character limit exceeded
                bot.answer_callback_query(call.id, f"❌ {str(e)}")
                del user_states[telegram_id]
                bot.edit_message_text(
                    f"❌ <b>Error:</b> {str(e)}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='HTML'
                )
            except DatabaseError as e:
                error_text = handle_database_error(e, "submitting confession")
                bot.answer_callback_query(call.id, "❌ Database error occurred.")
                del user_states[telegram_id]
                logger.error(f"Database error submitting confession: {e}")
                bot.edit_message_text(
                    error_text,
                    call.message.chat.id,
                    call.message.message_id
                )
            except Exception as e:
                error_text = handle_generic_error(e, "submitting confession")
                bot.answer_callback_query(call.id, "❌ An error occurred. Please try again.")
                del user_states[telegram_id]
                bot.edit_message_text(
                    error_text,
                    call.message.chat.id,
                    call.message.message_id
                )
        
        elif action == 'no':
            # Cancel the confession
            del user_states[telegram_id]
            bot.edit_message_text(
                "❌ Confession submission cancelled.",
                call.message.chat.id,
                call.message.message_id
            )
            
            # Restore main menu keyboard
            from telebot.types import ReplyKeyboardMarkup, KeyboardButton
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            keyboard.add(
                KeyboardButton("✍️ Confess"),
                KeyboardButton("👤 Profile"),
                KeyboardButton("ℹ️ Help")
            )
            
            bot.send_message(
                call.message.chat.id,
                "You can submit a new confession or use the menu below.",
                reply_markup=keyboard
            )
            
            bot.answer_callback_query(call.id, "Cancelled")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "confession confirmation")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error in confession confirmation: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "confession confirmation")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_confession_confirmation: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def handle_approve_confession(call: CallbackQuery):
    """Handle approve button callback for admin moderation"""
    try:
        telegram_id = call.from_user.id
        logger.info(f"Approve button clicked by user {telegram_id}")
        
        # Check admin permission
        if not is_admin(telegram_id):
            logger.warning(f"Non-admin user {telegram_id} tried to approve confession")
            bot.answer_callback_query(call.id, "❌ You don't have permission to perform this action.")
            return
        
        logger.info(f"Admin {telegram_id} is approving confession")
        
        # Extract and validate confession ID from callback data
        try:
            confession_id = int(call.data.split('_')[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Invalid confession ID in callback.")
            return
        
        # Get the confession
        confession, error = get_confession_or_error(confession_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Confession not found.")
            bot.edit_message_text(
                "❌ <b>Error:</b> Confession not found. It may have been deleted.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            return
        
        # Check if confession is still pending
        if confession.status != 'pending':
            # Update the message to show current status
            author = "Anonymous" if confession.is_anonymous else f"{confession.user.first_name}"
            if not confession.is_anonymous and confession.user.username:
                author += f" (@{confession.user.username})"
            
            preview_text = confession.text
            if len(preview_text) > 200:
                preview_text = preview_text[:200] + "..."
            
            status_emoji = {'approved': '✅', 'rejected': '❌'}.get(confession.status, '❓')
            reviewed_by = confession.reviewed_by.first_name if confession.reviewed_by else "Unknown Admin"
            
            updated_text = f"""
{status_emoji} <b>Confession Already {confession.status.title()}</b>

<b>Confession ID {confession.id}</b>
<b>From:</b> {author}
<b>{confession.status.title()} by:</b> {reviewed_by}
<b>{confession.status.title()} at:</b> {confession.reviewed_at.strftime('%Y-%m-%d %H:%M UTC') if confession.reviewed_at else 'Unknown'}

<b>Preview:</b>
{preview_text}

<i>This confession was already processed by another admin.</i>
            """
            
            bot.edit_message_text(
                updated_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            bot.answer_callback_query(call.id, f"❌ This confession has already been {confession.status} by {reviewed_by}.")
            return
        
        # Get admin user
        admin_user, error = get_user_or_error(telegram_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Admin user not found.")
            return
        
        # Approve the confession
        from bot.services.confession_service import approve_confession
        approve_confession(confession, admin_user, bot_instance=bot)
        
        # Notify the user
        notify_user_confession_status(confession, 'approved', bot)
        
        # Update the admin notification message
        author = "Anonymous" if confession.is_anonymous else f"{confession.user.first_name}"
        if not confession.is_anonymous and confession.user.username:
            author += f" (@{confession.user.username})"
        
        preview_text = confession.text
        if len(preview_text) > 200:
            preview_text = preview_text[:200] + "..."
        
        updated_text = f"""
✅ <b>Confession Approved</b>

<b>Confession ID {confession.id}</b>
<b>From:</b> {author}
<b>Approved by:</b> {call.from_user.first_name}
<b>Approved at:</b> {confession.reviewed_at.strftime('%Y-%m-%d %H:%M UTC')}

<b>Preview:</b>
{preview_text}

<i>This confession has been published to the channel.</i>
        """
        
        bot.edit_message_text(
            updated_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id, "✅ Confession approved and published!")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "approving confession")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error approving confession: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "approving confession")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_approve_confession: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def handle_reject_confession(call: CallbackQuery):
    """Handle reject button callback for admin moderation"""
    try:
        telegram_id = call.from_user.id
        logger.info(f"Reject button clicked by user {telegram_id}")
        
        # Check admin permission
        if not is_admin(telegram_id):
            logger.warning(f"Non-admin user {telegram_id} tried to reject confession")
            bot.answer_callback_query(call.id, "❌ You don't have permission to perform this action.")
            return
        
        logger.info(f"Admin {telegram_id} is rejecting confession")
        
        # Extract and validate confession ID from callback data
        try:
            confession_id = int(call.data.split('_')[1])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Invalid confession ID in callback.")
            return
        
        # Get the confession
        confession, error = get_confession_or_error(confession_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Confession not found.")
            bot.edit_message_text(
                "❌ <b>Error:</b> Confession not found. It may have been deleted.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            return
        
        # Check if confession is still pending
        if confession.status != 'pending':
            # Update the message to show current status
            author = "Anonymous" if confession.is_anonymous else f"{confession.user.first_name}"
            if not confession.is_anonymous and confession.user.username:
                author += f" (@{confession.user.username})"
            
            preview_text = confession.text
            if len(preview_text) > 200:
                preview_text = preview_text[:200] + "..."
            
            status_emoji = {'approved': '✅', 'rejected': '❌'}.get(confession.status, '❓')
            reviewed_by = confession.reviewed_by.first_name if confession.reviewed_by else "Unknown Admin"
            
            updated_text = f"""
{status_emoji} <b>Confession Already {confession.status.title()}</b>

<b>Confession ID {confession.id}</b>
<b>From:</b> {author}
<b>{confession.status.title()} by:</b> {reviewed_by}
<b>{confession.status.title()} at:</b> {confession.reviewed_at.strftime('%Y-%m-%d %H:%M UTC') if confession.reviewed_at else 'Unknown'}

<b>Preview:</b>
{preview_text}

<i>This confession was already processed by another admin.</i>
            """
            
            bot.edit_message_text(
                updated_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML'
            )
            bot.answer_callback_query(call.id, f"❌ This confession has already been {confession.status} by {reviewed_by}.")
            return
        
        # Get admin user
        admin_user, error = get_user_or_error(telegram_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Admin user not found.")
            return
        
        # Reject the confession
        from bot.services.confession_service import reject_confession
        reject_confession(confession, admin_user)
        
        # Notify the user
        notify_user_confession_status(confession, 'rejected', bot)
        
        # Update the admin notification message
        author = "Anonymous" if confession.is_anonymous else f"{confession.user.first_name}"
        if not confession.is_anonymous and confession.user.username:
            author += f" (@{confession.user.username})"
        
        preview_text = confession.text
        if len(preview_text) > 200:
            preview_text = preview_text[:200] + "..."
        
        updated_text = f"""
❌ <b>Confession Rejected</b>

<b>Confession ID {confession.id}</b>
<b>From:</b> {author}
<b>Rejected by:</b> {call.from_user.first_name}
<b>Rejected at:</b> {confession.reviewed_at.strftime('%Y-%m-%d %H:%M UTC')}

<b>Preview:</b>
{preview_text}

<i>The user has been notified of the rejection.</i>
        """
        
        bot.edit_message_text(
            updated_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id, "❌ Confession rejected.")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "rejecting confession")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error rejecting confession: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "rejecting confession")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_reject_confession: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('view_comments_'))
def handle_view_comments_wrapper(call: CallbackQuery):
    """Handle 'View / Add Comments' button - delegates to handlers module"""
    from bot.handlers.comment_handlers import handle_view_comments
    handle_view_comments(bot, call)


@bot.callback_query_handler(func=lambda call: call.data.startswith('comments_page_'))
def handle_comments_pagination_wrapper(call: CallbackQuery):
    """Handle pagination button callbacks - delegates to handlers module"""
    from bot.handlers.comment_handlers import handle_comments_pagination
    handle_comments_pagination(bot, call)

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_comment_'))
def handle_add_comment_button(call: CallbackQuery):
    """Handle 'Add Comment' button callback"""
    try:
        telegram_id = call.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.answer_callback_query(call.id, "❌ You need to /register first.")
            return
        
        # Extract and validate confession ID from callback data
        try:
            confession_id = int(call.data.split('_')[2])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Invalid confession ID in callback.")
            return
        
        # Get the confession
        confession, error = get_confession_or_error(confession_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Confession not found.")
            return
        
        # Check if confession is approved
        if confession.status != 'approved':
            bot.answer_callback_query(call.id, f"❌ You can only comment on approved confessions.")
            return
        
        # Set user state to waiting for comment text
        set_user_state(telegram_id, 'waiting_comment_text', {'confession_id': confession_id})
        
        # Show confession preview
        confession_preview = confession.text[:200] + "..." if len(confession.text) > 200 else confession.text
        
        response_text = f"""
💬 <b>Add a Comment</b>

<b>Confession {confession_id}:</b>
{confession_preview}

Please type your comment below. You can write up to 1000 characters.

Type /cancel to cancel.
        """
        
        bot.send_message(call.message.chat.id, response_text, parse_mode='HTML')
        bot.answer_callback_query(call.id, "Type your comment in the chat.")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "adding comment")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error adding comment: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "adding comment")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_add_comment_button: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('like_comment_'))
def handle_like_comment(call: CallbackQuery):
    """Handle like button callback for comments"""
    try:
        telegram_id = call.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.answer_callback_query(call.id, "❌ You need to /register first.")
            return
        
        # Extract and validate comment ID from callback data
        try:
            comment_id = int(call.data.split('_')[2])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Invalid comment ID in callback.")
            return
        
        # Get the comment
        comment, error = get_comment_or_error(comment_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Comment not found.")
            return
        
        # Check if user already liked this comment
        from bot.models import Reaction
        existing_reaction = Reaction.objects.filter(comment=comment, user=user).first()
        
        if existing_reaction and existing_reaction.reaction_type == 'like':
            bot.answer_callback_query(call.id, "ℹ️ You already liked this comment!")
            return
        
        # Add reaction
        from bot.services.comment_service import add_reaction
        add_reaction(user, comment, 'like')
        
        # Update the message with new counts
        try:
            update_comment_message(bot, call.message.chat.id, call.message.message_id, comment)
        except Exception as update_error:
            logger.warning(f"Could not update message after like: {update_error}")
        
        bot.answer_callback_query(call.id, "👍 Liked!")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "liking comment")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error liking comment: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "liking comment")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_like_comment: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('dislike_comment_'))
def handle_dislike_comment(call: CallbackQuery):
    """Handle dislike button callback for comments"""
    try:
        telegram_id = call.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.answer_callback_query(call.id, "❌ You need to /register first.")
            return
        
        # Extract and validate comment ID from callback data
        try:
            comment_id = int(call.data.split('_')[2])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Invalid comment ID in callback.")
            return
        
        # Get the comment
        comment, error = get_comment_or_error(comment_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Comment not found.")
            return
        
        # Check if user already disliked this comment
        from bot.models import Reaction
        existing_reaction = Reaction.objects.filter(comment=comment, user=user).first()
        
        if existing_reaction and existing_reaction.reaction_type == 'dislike':
            bot.answer_callback_query(call.id, "ℹ️ You already disliked this comment!")
            return
        
        # Add reaction
        from bot.services.comment_service import add_reaction
        add_reaction(user, comment, 'dislike')
        
        # Update the message with new counts
        try:
            update_comment_message(bot, call.message.chat.id, call.message.message_id, comment)
        except Exception as update_error:
            logger.warning(f"Could not update message after dislike: {update_error}")
        
        bot.answer_callback_query(call.id, "👎 Disliked!")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "disliking comment")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error disliking comment: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "disliking comment")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_dislike_comment: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('report_comment_'))
def handle_report_comment(call: CallbackQuery):
    """Handle report button callback for comments"""
    try:
        telegram_id = call.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.answer_callback_query(call.id, "❌ You need to /register first.")
            return
        
        # Extract and validate comment ID from callback data
        try:
            comment_id = int(call.data.split('_')[2])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Invalid comment ID in callback.")
            return
        
        # Get the comment
        comment, error = get_comment_or_error(comment_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Comment not found.")
            return
        
        # Check if user already reported this comment
        from bot.models import Reaction
        existing_reaction = Reaction.objects.filter(comment=comment, user=user).first()
        
        if existing_reaction and existing_reaction.reaction_type == 'report':
            bot.answer_callback_query(call.id, "ℹ️ You already reported this comment!")
            return
        
        # Add reaction
        from bot.services.comment_service import add_reaction
        add_reaction(user, comment, 'report')
        
        # Refresh the comment to get updated counts
        comment.refresh_from_db()
        
        # Check if report threshold is exceeded (e.g., 5 reports)
        REPORT_THRESHOLD = 5
        if comment.report_count >= REPORT_THRESHOLD:
            # Notify admins
            from django.conf import settings
            admin_notification = f"""
🚩 <b>Comment Reported Multiple Times</b>

<b>Comment ID {comment.id}</b>
<b>Confession ID {comment.confession.id}</b>
<b>Report Count:</b> {comment.report_count}
<b>Author:</b> {comment.user.first_name}

<b>Comment Text:</b>
{comment.text[:200]}{'...' if len(comment.text) > 200 else ''}

Please review this comment.
            """
            
            for admin_id in settings.ADMINS:
                try:
                    bot.send_message(admin_id, admin_notification, parse_mode='HTML')
                except Exception as notify_error:
                    logger.warning(f"Failed to notify admin {admin_id}: {notify_error}")
        
        # Update the message with new counts
        try:
            update_comment_message(bot, call.message.chat.id, call.message.message_id, comment)
        except Exception as update_error:
            logger.warning(f"Could not update message after report: {update_error}")
        
        bot.answer_callback_query(call.id, "🚩 Comment reported. Thank you for helping keep the community safe.")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "reporting comment")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error reporting comment: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "reporting comment")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_report_comment: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_comment_'))
def handle_reply_comment(call: CallbackQuery):
    """Handle reply button callback for comments"""
    try:
        telegram_id = call.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.answer_callback_query(call.id, "❌ You need to /register first.")
            return
        
        # Extract and validate comment ID from callback data
        try:
            comment_id = int(call.data.split('_')[2])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Invalid comment ID in callback.")
            return
        
        # Get the comment
        comment, error = get_comment_or_error(comment_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Comment not found.")
            return
        
        # Set user state to waiting for reply text
        set_user_state(telegram_id, 'waiting_reply_text', {
            'confession_id': comment.confession.id,
            'parent_comment_id': comment_id
        })
        
        # Show comment preview (without revealing commenter identity)
        comment_preview = comment.text[:200] + "..." if len(comment.text) > 200 else comment.text
        
        response_text = f"""
💬 <b>Reply to Comment</b>

<b>Original Comment:</b>
{comment_preview}

Please type your reply below. You can write up to 1000 characters.

Type /cancel to cancel.
        """
        
        bot.send_message(call.message.chat.id, response_text, parse_mode='HTML')
        bot.answer_callback_query(call.id, "Type your reply in the chat.")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "replying to comment")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error replying to comment: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "replying to comment")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_reply_comment: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "send_feedback")
def handle_send_feedback(call: CallbackQuery):
    """Handle feedback button click"""
    telegram_id = call.from_user.id
    try:
        # Get or create user
        user, error = get_user_or_error(telegram_id)
        if error:
            # Try to create user if they don't exist
            first_name = call.from_user.first_name or "User"
            username = call.from_user.username
            from bot.utils import retry_db_operation
            
            @retry_db_operation(max_retries=3)
            def register_with_retry():
                return register_user(telegram_id, first_name, username)
            
            user = register_with_retry()
        
        # Set user state to waiting for feedback
        set_user_state(telegram_id, 'waiting_feedback_text')
        
        bot.edit_message_text(
            "📝 <b>Anonymous Feedback</b>\n\n"
            "Your feedback is completely anonymous and helps us improve the bot.\n\n"
            "Please write your feedback, suggestions, or report any issues:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred. Please try again.")
        logger.error(f"Error in send_feedback: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def handle_back_to_main(call: CallbackQuery):
    """Handle back to main menu button"""
    telegram_id = call.from_user.id
    
    # Clear any pending state
    if telegram_id in user_states:
        del user_states[telegram_id]
    
    # Show main menu
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("✍️ Confess"),
        KeyboardButton("👤 Profile"),
        KeyboardButton("ℹ️ Help")
    )
    
    bot.edit_message_text(
        "🏠 <b>Main Menu</b>\n\n"
        "Welcome back! Choose an option below or use the keyboard buttons:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode='HTML'
    )
    bot.send_message(
        call.message.chat.id,
        "Choose an option:",
        reply_markup=keyboard
    )
    bot.answer_callback_query(call.id)


# Feedback management callback handlers

@bot.callback_query_handler(func=lambda call: call.data.startswith('resolve_feedback_'))
def handle_resolve_feedback_button(call: CallbackQuery):
    """Handle resolve feedback button"""
    logger.info(f"Resolve feedback button clicked: {call.data}")
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[2])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Update feedback
        feedback.status = 'resolved'
        feedback.reviewed_by = admin_user
        feedback.reviewed_at = timezone.now()
        feedback.save()
        
        # Notify the user
        logger.info(f"About to notify user for resolved feedback #{feedback.id} with admin_notes: '{feedback.admin_notes}'")
        notify_user_feedback_status(feedback, 'resolved')
        
        # Update the message with new status
        send_feedback_with_buttons(bot, call.message.chat.id, feedback)
        
        # Delete the old message
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        bot.answer_callback_query(call.id, "✅ Feedback marked as resolved!")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error resolving feedback: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('review_feedback_'))
def handle_review_feedback_button(call: CallbackQuery):
    """Handle mark as reviewed button"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[2])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Update feedback
        feedback.status = 'reviewed'
        feedback.reviewed_by = admin_user
        feedback.reviewed_at = timezone.now()
        feedback.save()
        
        # Notify the user
        notify_user_feedback_status(feedback, 'reviewed')
        
        # Update the message with new status
        send_feedback_with_buttons(bot, call.message.chat.id, feedback)
        
        # Delete the old message
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        bot.answer_callback_query(call.id, "✅ Feedback marked as reviewed!")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error reviewing feedback: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('pending_feedback_'))
def handle_pending_feedback_button(call: CallbackQuery):
    """Handle mark as pending button"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[2])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Update feedback
        feedback.status = 'pending'
        feedback.save()
        
        # Update the message with new status
        send_feedback_with_buttons(bot, call.message.chat.id, feedback)
        
        # Delete the old message
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        bot.answer_callback_query(call.id, "✅ Feedback marked as pending!")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error marking feedback as pending: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('reopen_feedback_'))
def handle_reopen_feedback_button(call: CallbackQuery):
    """Handle reopen feedback button"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[2])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user for notification
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Update feedback
        feedback.status = 'reviewed'  # Reopen to reviewed status
        feedback.save()
        
        # Notify the user
        notify_user_feedback_status(feedback, 'reopened')
        
        # Update the message with new status
        send_feedback_with_buttons(bot, call.message.chat.id, feedback)
        
        # Delete the old message
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        bot.answer_callback_query(call.id, "✅ Feedback reopened!")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error reopening feedback: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('add_note_feedback_'))
def handle_add_note_feedback_button(call: CallbackQuery):
    """Handle add note button - starts conversation for note input"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[3])
        
        # Set user state for note input
        set_user_state(telegram_id, 'waiting_feedback_note', {'feedback_id': feedback_id})
        
        bot.edit_message_text(
            f"📝 <b>Add Note to Feedback #{feedback_id}</b>\n\n"
            "Please type your admin note below.\n\n"
            "Use /cancel to cancel.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML'
        )
        
        bot.answer_callback_query(call.id, "Type your note below")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error starting note input: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('categorize_feedback_'))
def handle_categorize_feedback_button(call: CallbackQuery):
    """Handle categorize button - shows category selection"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[2])
        
        # Create category selection keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("🐛 Bug", callback_data=f"cat_bug_{feedback_id}"),
            InlineKeyboardButton("✨ Feature", callback_data=f"cat_feature_{feedback_id}")
        )
        keyboard.row(
            InlineKeyboardButton("🔧 Improvement", callback_data=f"cat_improvement_{feedback_id}"),
            InlineKeyboardButton("❓ Question", callback_data=f"cat_question_{feedback_id}")
        )
        keyboard.row(
            InlineKeyboardButton("😠 Complaint", callback_data=f"cat_complaint_{feedback_id}"),
            InlineKeyboardButton("👏 Praise", callback_data=f"cat_praise_{feedback_id}")
        )
        keyboard.row(
            InlineKeyboardButton("📝 Other", callback_data=f"cat_other_{feedback_id}"),
            InlineKeyboardButton("🔙 Back", callback_data=f"back_feedback_{feedback_id}")
        )
        
        bot.edit_message_text(
            f"🏷️ <b>Categorize Feedback #{feedback_id}</b>\n\n"
            "Select a category:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error showing categories: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('priority_feedback_'))
def handle_priority_feedback_button(call: CallbackQuery):
    """Handle priority button - shows priority selection"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[2])
        
        # Create priority selection keyboard
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("🔴 Urgent", callback_data=f"pri_urgent_{feedback_id}"),
            InlineKeyboardButton("🟠 High", callback_data=f"pri_high_{feedback_id}")
        )
        keyboard.row(
            InlineKeyboardButton("🟡 Medium", callback_data=f"pri_medium_{feedback_id}"),
            InlineKeyboardButton("🟢 Low", callback_data=f"pri_low_{feedback_id}")
        )
        keyboard.row(
            InlineKeyboardButton("🔙 Back", callback_data=f"back_feedback_{feedback_id}")
        )
        
        bot.edit_message_text(
            f"⚡ <b>Set Priority for Feedback #{feedback_id}</b>\n\n"
            "Select a priority level:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error showing priorities: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def handle_category_selection(call: CallbackQuery):
    """Handle category selection"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        parts = call.data.split('_')
        category = parts[1]
        feedback_id = int(parts[2])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Add category note
        timestamp = timezone.now().strftime('%b %d, %Y • %I:%M %p')
        admin_name = admin_user.username or admin_user.first_name
        category_note = f"[{timestamp}] {admin_name}: Categorized as '{category.upper()}'"
        
        current_notes = feedback.admin_notes or ""
        if current_notes:
            feedback.admin_notes = current_notes + "\n\n" + category_note
        else:
            feedback.admin_notes = category_note
        
        # Update review info
        feedback.reviewed_by = admin_user
        feedback.reviewed_at = timezone.now()
        if feedback.status == 'pending':
            feedback.status = 'reviewed'
        
        feedback.save()
        
        # Show updated feedback
        send_feedback_with_buttons(bot, call.message.chat.id, feedback)
        
        # Delete the old message
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        category_emoji = {
            'bug': '🐛', 'feature': '✨', 'improvement': '🔧',
            'question': '❓', 'complaint': '😠', 'praise': '👏', 'other': '📝'
        }.get(category, '📝')
        
        bot.answer_callback_query(call.id, f"✅ Categorized as {category_emoji} {category.upper()}")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error setting category: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('pri_'))
def handle_priority_selection(call: CallbackQuery):
    """Handle priority selection"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        parts = call.data.split('_')
        priority = parts[1]
        feedback_id = int(parts[2])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Get admin user
        admin_user = User.objects.get(telegram_id=telegram_id)
        
        # Add priority note
        timestamp = timezone.now().strftime('%b %d, %Y • %I:%M %p')
        admin_name = admin_user.username or admin_user.first_name
        priority_note = f"[{timestamp}] {admin_name}: Priority set to '{priority.upper()}'"
        
        current_notes = feedback.admin_notes or ""
        if current_notes:
            feedback.admin_notes = current_notes + "\n\n" + priority_note
        else:
            feedback.admin_notes = priority_note
        
        # Update review info
        feedback.reviewed_by = admin_user
        feedback.reviewed_at = timezone.now()
        if feedback.status == 'pending':
            feedback.status = 'reviewed'
        
        feedback.save()
        
        # Show updated feedback
        send_feedback_with_buttons(bot, call.message.chat.id, feedback)
        
        # Delete the old message
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        priority_emoji = {
            'low': '🟢', 'medium': '🟡', 'high': '🟠', 'urgent': '🔴'
        }.get(priority, '⚪')
        
        bot.answer_callback_query(call.id, f"✅ Priority set to {priority_emoji} {priority.upper()}")
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error setting priority: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('back_feedback_'))
def handle_back_to_feedback(call: CallbackQuery):
    """Handle back button - return to feedback view"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[2])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Show feedback with buttons
        send_feedback_with_buttons(bot, call.message.chat.id, feedback)
        
        # Delete the old message
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error going back to feedback: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('details_feedback_'))
def handle_feedback_details(call: CallbackQuery):
    """Handle view details button"""
    telegram_id = call.from_user.id
    if not is_admin(telegram_id):
        bot.answer_callback_query(call.id, "❌ Admin access required.")
        return
    
    try:
        feedback_id = int(call.data.split('_')[2])
        
        from bot.models import Feedback
        feedback = Feedback.objects.get(id=feedback_id)
        
        # Show detailed view
        status_emoji = {
            'pending': '🟡',
            'reviewed': '🔵', 
            'resolved': '🟢'
        }.get(feedback.status, '⚪')
        
        details_text = f"""
{status_emoji} <b>Feedback #{feedback.id} - Detailed View</b>

<b>Status:</b> {feedback.status.title()}
<b>Submitted:</b> {feedback.created_at.strftime('%b %d, %Y • %I:%M %p')}

<b>Full Feedback:</b>
{feedback.text}
        """
        
        if feedback.reviewed_by:
            details_text += f"\n\n<b>Reviewed by:</b> {feedback.reviewed_by.username or feedback.reviewed_by.first_name}"
            details_text += f"\n<b>Reviewed at:</b> {feedback.reviewed_at.strftime('%b %d, %Y • %I:%M %p')}"
        
        if feedback.admin_notes:
            details_text += f"\n\n<b>Admin Notes:</b>\n{feedback.admin_notes}"
        
        # Create back button
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("🔙 Back to Actions", callback_data=f"back_feedback_{feedback_id}")
        )
        
        bot.edit_message_text(
            details_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Error occurred.")
        logger.error(f"Error showing feedback details: {e}")


# Debug callback handler - should be LAST callback handler
@bot.callback_query_handler(func=lambda call: True)
def handle_unknown_callback(call: CallbackQuery):
    """Handle unknown callback queries for debugging"""
    logger.error(f"Unknown callback data: {call.data}")
    bot.answer_callback_query(call.id, f"❌ This button action is not recognized: {call.data}")


@bot.message_handler(func=lambda message: True)
def handle_unknown_command(message: Message):
    """Handle unknown commands and messages"""
    telegram_id = message.from_user.id
    
    # Clean expired states periodically
    clean_expired_user_states()
    
    # Check if user state has timed out
    timed_out, expired_state = check_user_state_timeout(telegram_id)
    if timed_out:
        timeout_message = f"""
⏰ <b>Session Timed Out</b>

Your {expired_state.replace('waiting_', '').replace('_', ' ')} session has expired due to inactivity (10 minutes).

Please start over using the appropriate command:
• /confess - to submit a confession
• /comment <id> - to add a comment
• Use the buttons below for other actions
        """
        
        # Show main menu keyboard
        from telebot.types import ReplyKeyboardMarkup, KeyboardButton
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(
            KeyboardButton("✍️ Confess"),
            KeyboardButton("👤 Profile"),
            KeyboardButton("ℹ️ Help")
        )
        
        bot.reply_to(message, timeout_message, reply_markup=keyboard)
        return
    
    # Check if user is in a conversation state
    if telegram_id in user_states:
        # Update timestamp to show user is still active
        update_user_state_timestamp(telegram_id)
        state = user_states[telegram_id].get('state')
        
        if state == 'waiting_confession_text':
            # Check if user clicked Cancel button
            if message.text == "❌ Cancel":
                del user_states[telegram_id]
                
                # Show main menu keyboard
                from telebot.types import ReplyKeyboardMarkup, KeyboardButton
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                keyboard.add(
                    KeyboardButton("✍️ Confess"),
                    KeyboardButton("👤 Profile"),
                    KeyboardButton("ℹ️ Help")
                )
                
                bot.reply_to(message, "❌ Confession submission cancelled.", reply_markup=keyboard)
                return
            
            # User is submitting confession text
            confession_text = message.text
            
            if not confession_text or len(confession_text.strip()) == 0:
                bot.reply_to(message, "❌ Confession cannot be empty. Please type your confession or use the Cancel button.")
                return
            
            # Check character limit
            if len(confession_text) > 4096:
                bot.reply_to(
                    message,
                    f"❌ Your confession is too long ({len(confession_text)} characters). The maximum length is 4096 characters. Please shorten it and try again."
                )
                return
            
            # Get user to show anonymity setting
            user, error = get_user_or_error(telegram_id)
            if error:
                bot.reply_to(message, error)
                del user_states[telegram_id]
                return
            
            # Store the confession text and update state
            user_states[telegram_id]['state'] = 'waiting_confession_confirmation'
            user_states[telegram_id]['data']['text'] = confession_text
            update_user_state_timestamp(telegram_id)
            
            # Show confirmation with preview
            anonymity_status = "anonymously" if user.is_anonymous_mode else "with your name"
            preview_text = confession_text[:500] + "..." if len(confession_text) > 500 else confession_text
            
            confirmation_text = f"""
📝 <b>Confirm Your Confession</b>

<b>Your confession will be posted {anonymity_status}.</b>

<b>Preview:</b>
{preview_text}

<b>Character count:</b> {len(confession_text)} / 4096

Do you want to submit this confession?
            """
            
            # Create confirmation keyboard
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("✅ Yes, Submit", callback_data="confirm_confession_yes"),
                InlineKeyboardButton("❌ No, Cancel", callback_data="confirm_confession_no")
            )
            
            bot.reply_to(message, confirmation_text, reply_markup=keyboard)
            return
        
        elif state == 'waiting_feedback_note':
            # User is adding a note to feedback
            note_text = message.text.strip()
            
            if len(note_text) > 1000:
                bot.reply_to(message, "❌ Note is too long. Please keep it under 1000 characters.")
                return
            
            if len(note_text) < 5:
                bot.reply_to(message, "❌ Note is too short. Please provide at least 5 characters.")
                return
            
            try:
                feedback_id = user_states[telegram_id]['data']['feedback_id']
                
                from bot.models import Feedback
                feedback = Feedback.objects.get(id=feedback_id)
                
                # Get admin user
                admin_user = User.objects.get(telegram_id=telegram_id)
                
                # Add note to existing admin notes
                timestamp = timezone.now().strftime('%b %d, %Y • %I:%M %p')
                admin_name = admin_user.username or admin_user.first_name
                new_note = f"[{timestamp}] {admin_name}: {note_text}"
                
                current_notes = feedback.admin_notes or ""
                if current_notes:
                    feedback.admin_notes = current_notes + "\n\n" + new_note
                else:
                    feedback.admin_notes = new_note
                
                # Update review info
                feedback.reviewed_by = admin_user
                feedback.reviewed_at = timezone.now()
                if feedback.status == 'pending':
                    feedback.status = 'reviewed'
                
                feedback.save()
                
                # Clear user state
                del user_states[telegram_id]
                
                # Send updated feedback with buttons
                send_feedback_with_buttons(bot, message.chat.id, feedback)
                
                bot.reply_to(message, f"✅ Note added to feedback #{feedback_id}")
                
            except Exception as e:
                bot.reply_to(message, f"❌ Error adding note: {str(e)[:100]}")
                logger.error(f"Error adding feedback note: {e}")
                del user_states[telegram_id]
            
            return
        
        elif state == 'waiting_feedback_text':
            # User is submitting feedback text
            feedback_text = message.text.strip()
            
            if len(feedback_text) > 2000:
                bot.reply_to(message, "❌ Feedback is too long. Please keep it under 2000 characters.")
                return
            
            if len(feedback_text) < 10:
                bot.reply_to(message, "❌ Feedback is too short. Please provide at least 10 characters.")
                return
            
            try:
                # Get user
                user, error = get_user_or_error(telegram_id)
                if error:
                    bot.reply_to(message, error)
                    del user_states[telegram_id]
                    return
                
                # Create feedback
                from bot.models import Feedback
                from django.db import connection
                
                # Check if table exists
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'bot_feedback'
                        );
                    """)
                    table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    bot.reply_to(
                        message,
                        "❌ Feedback system is not yet set up. Please contact an administrator.\n\n"
                        "Admin: Run 'python manage.py migrate bot' to enable feedback."
                    )
                    del user_states[telegram_id]
                    return
                
                feedback = Feedback.objects.create(
                    user=user,
                    text=feedback_text
                )
                
                # Notify admins
                admin_ids = [admin_id for admin_id in settings.ADMINS]
                admin_message = f"""
📬 <b>New Anonymous Feedback #{feedback.id}</b>

<b>Feedback:</b>
{feedback_text}

<b>Submitted:</b> {feedback.created_at.strftime('%b %d, %Y • %I:%M %p')}

Use /viewfeedback to see all feedback.
                """
                
                for admin_id in admin_ids:
                    try:
                        bot.send_message(admin_id, admin_message, parse_mode='HTML')
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_id}: {e}")
                
                # Confirm to user
                from telebot.types import ReplyKeyboardMarkup, KeyboardButton
                keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                keyboard.add(
                    KeyboardButton("✍️ Confess"),
                    KeyboardButton("👤 Profile"),
                    KeyboardButton("ℹ️ Help")
                )
                
                bot.reply_to(
                    message, 
                    "✅ <b>Feedback Submitted!</b>\n\n"
                    "Thank you for your anonymous feedback. It helps us improve the bot!\n\n"
                    "Your feedback has been sent to the administrators.",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                
                # Clear user state
                del user_states[telegram_id]
                return
                
            except Exception as e:
                bot.reply_to(message, f"❌ Failed to submit feedback. Please try again.\n\nError: {str(e)[:100]}")
                logger.error(f"Error creating feedback: {e}", exc_info=True)
                del user_states[telegram_id]
                return
        
        elif state == 'waiting_comment_text':
            # User is submitting comment text
            comment_text = message.text
            
            if not comment_text or len(comment_text.strip()) == 0:
                bot.reply_to(message, "❌ Comment cannot be empty. Please type your comment or use /cancel to cancel.")
                return
            
            # Check character limit
            if len(comment_text) > 1000:
                bot.reply_to(
                    message,
                    f"❌ Your comment is too long ({len(comment_text)} characters). The maximum length is 1000 characters. Please shorten it and try again."
                )
                return
            
            # Get user
            user, error = get_user_or_error(telegram_id)
            if error:
                bot.reply_to(message, error)
                del user_states[telegram_id]
                return
            
            # Get confession
            confession_id = user_states[telegram_id]['data']['confession_id']
            confession, error = get_confession_or_error(confession_id)
            if error:
                bot.reply_to(message, error)
                del user_states[telegram_id]
                return
            
            # Create the comment
            try:
                from bot.services.comment_service import create_comment
                comment = create_comment(user, confession, comment_text, bot_instance=bot)
                
                # Clear user state
                del user_states[telegram_id]
                
                # Send success message
                success_text = f"""
✅ <b>Comment Posted Successfully!</b>

Your comment has been added to confession {confession_id}.

<b>Your comment:</b>
{comment_text[:200]}{'...' if len(comment_text) > 200 else ''}

Use /comments {confession_id} to view all comments on this confession.
                """
                
                bot.reply_to(message, success_text)
                
            except ValueError as e:
                # Character limit exceeded (should not happen due to earlier check)
                bot.reply_to(message, f"❌ {str(e)}")
                del user_states[telegram_id]
            except DatabaseError as e:
                error_text = handle_database_error(e, "posting comment")
                bot.reply_to(message, error_text)
                del user_states[telegram_id]
            except Exception as e:
                error_text = handle_generic_error(e, "posting comment")
                bot.reply_to(message, error_text)
                del user_states[telegram_id]
            
            return
        
        elif state == 'waiting_reply_text':
            # User is submitting reply text
            reply_text = message.text
            
            if not reply_text or len(reply_text.strip()) == 0:
                bot.reply_to(message, "❌ Reply cannot be empty. Please type your reply or use /cancel to cancel.")
                return
            
            # Check character limit
            if len(reply_text) > 1000:
                bot.reply_to(
                    message,
                    f"❌ Your reply is too long ({len(reply_text)} characters). The maximum length is 1000 characters. Please shorten it and try again."
                )
                return
            
            # Get user
            user, error = get_user_or_error(telegram_id)
            if error:
                bot.reply_to(message, error)
                del user_states[telegram_id]
                return
            
            # Get confession and parent comment
            confession_id = user_states[telegram_id]['data']['confession_id']
            parent_comment_id = user_states[telegram_id]['data']['parent_comment_id']
            
            confession, error = get_confession_or_error(confession_id)
            if error:
                bot.reply_to(message, error)
                del user_states[telegram_id]
                return
            
            parent_comment, error = get_comment_or_error(parent_comment_id)
            if error:
                bot.reply_to(message, error)
                del user_states[telegram_id]
                return
            
            # Create the reply
            try:
                from bot.services.comment_service import create_comment
                reply = create_comment(user, confession, reply_text, parent_comment=parent_comment, bot_instance=bot)
                
                # Clear user state
                del user_states[telegram_id]
                
                # Send success message
                success_text = f"""
✅ <b>Reply Posted Successfully!</b>

Your reply has been added to comment #{parent_comment_id}.

<b>Your reply:</b>
{reply_text[:200]}{'...' if len(reply_text) > 200 else ''}

Use /comments {confession_id} to view all comments on this confession.
                """
                
                bot.reply_to(message, success_text)
                
            except ValueError as e:
                # Character limit exceeded (should not happen due to earlier check)
                bot.reply_to(message, f"❌ {str(e)}")
                del user_states[telegram_id]
            except DatabaseError as e:
                error_text = handle_database_error(e, "posting reply")
                bot.reply_to(message, error_text)
                del user_states[telegram_id]
            except Exception as e:
                error_text = handle_generic_error(e, "posting reply")
                bot.reply_to(message, error_text)
                del user_states[telegram_id]
            
            return
        
        # If user is in a state but we didn't handle it above, give them guidance
        else:
            state_guidance = {
                'waiting_confession_text': "📝 Please type your confession text, or use the ❌ Cancel button to stop.",
                'waiting_comment_text': "💬 Please type your comment text, or use /cancel to stop.",
                'waiting_reply_text': "↩️ Please type your reply text, or use /cancel to stop.",
                'waiting_feedback_text': "📝 Please type your feedback text, or use /cancel to stop.",
                'waiting_feedback_note': "📝 Please type your admin note, or use /cancel to stop."
            }
            
            guidance = state_guidance.get(state, "Please complete your current action or use /cancel to stop.")
            bot.reply_to(message, guidance)
            return
    
    # Check if it's a command (starts with /)
    if message.text and message.text.startswith('/'):
        error_text = """
❌ <b>Unknown Command</b>

I don't recognize that command. Here are the available commands:

<b>User Commands:</b>
• /register - Register with the bot
• /confess - Submit a confession
• /comment <id> - Add a comment to a confession
• /comments <id> - View comments on a confession
• /anonymous_on - Enable anonymous mode
• /anonymous_off - Disable anonymous mode
• /profile - View your profile
• /myconfessions - View your confessions
• /mycomments - View your comments
• /help - Get help

<b>Admin Commands:</b>
• /pending - View pending confessions
• /stats - View system statistics
• /delete <id> - Delete a confession
• /feedbackhelp - Feedback management commands

Use /help for more information.
        """
        bot.reply_to(message, error_text)
    else:
        # Regular message
        bot.reply_to(message, "Please use /help to see available commands.")
