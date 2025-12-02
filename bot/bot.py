import time, re
import logging
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

# Configure logging
logger = logging.getLogger(__name__)

bot = TeleBot(settings.BOT_TOKEN, parse_mode="HTML", threaded=False)

# Dictionary to store user conversation states
# Format: {user_id: {'state': 'waiting_confession_text', 'data': {...}}}
user_states = {}


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


# Message Handlers
@bot.message_handler(commands=['start'])
def start_command(message: Message):
    """Handle /start command"""
    user_name = message.from_user.first_name
    welcome_text = f"""
👋 <b>Hello {user_name}!</b>

Welcome to the Anonymous Confession Bot!

Available commands:
/register - Register with the bot
/confess - Submit a confession
/comment [id] - Add a comment to a confession
/comments [id] - View comments on a confession
/anonymous_on - Enable anonymous mode
/anonymous_off - Disable anonymous mode
/profile - View your profile and stats
/myconfessions - View your confessions
/mycomments - View your comments
/help - Get help

Admin commands:
/pending - View pending confessions
/stats - View system statistics
/delete - Delete a confession
    """
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['help'])
def help_command(message: Message):
    """Handle /help command"""
    help_text = """
<b>📚 Help Menu</b>

<b>User Commands:</b>
• /register - Register with the bot to start using it
• /confess - Submit an anonymous or attributed confession
• /comment [id] - Add a comment to a confession
• /comments [id] - View all comments on a confession
• /anonymous_on - Enable anonymous mode (default)
• /anonymous_off - Disable anonymous mode (show your name)
• /profile - View your profile statistics
• /myconfessions - View all your confessions and their status
• /mycomments - View all your comments

<b>Admin Commands:</b>
• /pending - View all pending confessions
• /stats - View system statistics
• /delete [id] - Delete a confession by ID

<b>About Anonymity:</b>
When anonymous mode is ON, your confessions will be posted without your name.
When anonymous mode is OFF, your confessions will show your name.
    """
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['register'])
def register_command(message: Message):
    """Handle /register command"""
    try:
        telegram_id = message.from_user.id
        first_name = message.from_user.first_name or "User"
        username = message.from_user.username
        
        # Register the user
        user = register_user(telegram_id, first_name, username)
        
        response_text = f"""
✅ <b>Registration Successful!</b>

Welcome, {first_name}! Your profile has been created.

<b>Your Settings:</b>
• Anonymous Mode: {'ON' if user.is_anonymous_mode else 'OFF'}
• Total Confessions: {user.total_confessions}
• Total Comments: {user.total_comments}
• Impact Points: {user.impact_points}

Use /confess to submit your first confession!
Use /anonymous_on or /anonymous_off to change your anonymity setting.
        """
        
        bot.reply_to(message, response_text)
        
    except IntegrityError as e:
        # User already exists
        logger.warning(f"Duplicate registration attempt for telegram_id {message.from_user.id}: {e}")
        error_text = "ℹ️ You are already registered! Use /profile to view your profile."
        bot.reply_to(message, error_text)
    except DatabaseError as e:
        error_text = handle_database_error(e, "registration")
        bot.reply_to(message, error_text)
    except Exception as e:
        error_text = handle_generic_error(e, "registration")
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
        user_states[telegram_id] = {
            'state': 'waiting_confession_text',
            'data': {}
        }
        
        # Inform user about their current anonymity setting
        anonymity_status = "anonymously" if user.is_anonymous_mode else "with your name"
        
        response_text = f"""
📝 <b>Submit a Confession</b>

Your confession will be posted <b>{anonymity_status}</b>.

Please type your confession below. You can write up to 4096 characters.

<i>To change your anonymity setting, use /anonymous_on or /anonymous_off before submitting.</i>

Type /cancel to cancel this confession.
        """
        
        bot.reply_to(message, response_text)
        
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
        
        response_text = f"<b>📋 Pending Confessions ({pending_confessions.count()})</b>\n\n"
        
        for confession in pending_confessions[:20]:  # Limit to 20 to avoid message length issues
            text_preview = confession.text[:100] + "..." if len(confession.text) > 100 else confession.text
            author = confession.user.first_name
            if confession.user.username:
                author += f" (@{confession.user.username})"
            
            response_text += f"<b>ID {confession.id}</b>\n"
            response_text += f"From: {author}\n"
            response_text += f"Anonymous: {'Yes' if confession.is_anonymous else 'No'}\n"
            response_text += f"Preview: {text_preview}\n"
            response_text += f"Submitted: {confession.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        if pending_confessions.count() > 20:
            response_text += f"\n<i>Showing 20 of {pending_confessions.count()} pending confessions.</i>"
        
        bot.reply_to(message, response_text)
        
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
        user_states[telegram_id] = {
            'state': 'waiting_comment_text',
            'data': {
                'confession_id': confession_id
            }
        }
        
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
            commenter_name = comment.user.first_name
            if comment.user.username:
                commenter_name += f" (@{comment.user.username})"
            
            comment_text = comment.text[:150] + "..." if len(comment.text) > 150 else comment.text
            
            response_text += f"<b>Comment #{comment.id}</b> by {commenter_name}\n"
            response_text += f"{comment_text}\n"
            response_text += f"👍 {comment.like_count} | 👎 {comment.dislike_count} | 🚩 {comment.report_count}\n"
            response_text += f"<i>{comment.created_at.strftime('%Y-%m-%d %H:%M')}</i>\n\n"
        
        # Add pagination info
        if comments_data['has_next'] or comments_data['has_previous']:
            response_text += f"\n<i>Use /comments {confession_id} to view comments. Pagination coming soon!</i>"
        
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
        else:
            bot.reply_to(message, "✅ Operation cancelled.")
    else:
        bot.reply_to(message, "ℹ️ No active operation to cancel.")


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
        
        # Check admin permission
        if not is_admin(telegram_id):
            bot.answer_callback_query(call.id, "❌ You don't have permission to perform this action.")
            return
        
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
            bot.answer_callback_query(call.id, f"❌ This confession has already been {confession.status}.")
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
        
        # Check admin permission
        if not is_admin(telegram_id):
            bot.answer_callback_query(call.id, "❌ You don't have permission to perform this action.")
            return
        
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
            bot.answer_callback_query(call.id, f"❌ This confession has already been {confession.status}.")
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
def handle_view_comments(call: CallbackQuery):
    """Handle 'View / Add Comments' button callback"""
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
        
        # Get comments (first page)
        from bot.services.comment_service import get_comments
        comments_data = get_comments(confession, page=1, page_size=5)
        
        # Build response text
        confession_preview = confession.text[:150] + "..." if len(confession.text) > 150 else confession.text
        
        response_text = f"<b>💬 Comments on Confession {confession_id}</b>\n\n"
        response_text += f"<i>{confession_preview}</i>\n\n"
        
        if not comments_data['comments']:
            response_text += "No comments yet. Be the first to comment!\n\n"
        else:
            response_text += f"<b>Comments (Page {comments_data['current_page']} of {comments_data['total_pages']}):</b>\n\n"
            
            for comment in comments_data['comments']:
                commenter_name = comment.user.first_name
                comment_text = comment.text[:100] + "..." if len(comment.text) > 100 else comment.text
                
                response_text += f"<b>#{comment.id}</b> by {commenter_name}\n"
                response_text += f"{comment_text}\n"
                response_text += f"👍 {comment.like_count} | 👎 {comment.dislike_count} | 🚩 {comment.report_count}\n\n"
        
        # Create inline keyboard with action buttons
        keyboard = InlineKeyboardMarkup()
        
        # Add comment button
        keyboard.row(
            InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
        )
        
        # Add pagination buttons if needed
        if comments_data['total_pages'] > 1:
            buttons = []
            if comments_data['has_previous']:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] - 1}"))
            if comments_data['has_next']:
                buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] + 1}"))
            if buttons:
                keyboard.row(*buttons)
        
        # Send or edit message
        try:
            bot.edit_message_text(
                response_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except:
            # If edit fails, send new message
            bot.send_message(
                call.message.chat.id,
                response_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        
        bot.answer_callback_query(call.id)
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "viewing comments")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error viewing comments: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "viewing comments")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_view_comments: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('comments_page_'))
def handle_comments_pagination(call: CallbackQuery):
    """Handle pagination button callbacks for comments"""
    try:
        telegram_id = call.from_user.id
        
        # Check if user is registered
        try:
            user = User.objects.get(telegram_id=telegram_id)
        except User.DoesNotExist:
            bot.answer_callback_query(call.id, "❌ You need to /register first.")
            return
        
        # Extract confession ID and page number from callback data
        parts = call.data.split('_')
        confession_id = int(parts[2])
        page = int(parts[3])
        
        # Get the confession
        try:
            confession = Confession.objects.get(id=confession_id)
        except Confession.DoesNotExist:
            bot.answer_callback_query(call.id, "❌ Confession not found.")
            return
        
        # Get comments for the requested page
        from bot.services.comment_service import get_comments
        comments_data = get_comments(confession, page=page, page_size=5)
        
        # Build response text
        confession_preview = confession.text[:150] + "..." if len(confession.text) > 150 else confession.text
        
        response_text = f"<b>💬 Comments on Confession {confession_id}</b>\n\n"
        response_text += f"<i>{confession_preview}</i>\n\n"
        
        if not comments_data['comments']:
            response_text += "No comments on this page.\n\n"
        else:
            response_text += f"<b>Comments (Page {comments_data['current_page']} of {comments_data['total_pages']}):</b>\n\n"
            
            for comment in comments_data['comments']:
                commenter_name = comment.user.first_name
                comment_text = comment.text[:100] + "..." if len(comment.text) > 100 else comment.text
                
                response_text += f"<b>#{comment.id}</b> by {commenter_name}\n"
                response_text += f"{comment_text}\n"
                response_text += f"👍 {comment.like_count} | 👎 {comment.dislike_count} | 🚩 {comment.report_count}\n\n"
        
        # Create inline keyboard with action buttons
        keyboard = InlineKeyboardMarkup()
        
        # Add comment button
        keyboard.row(
            InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
        )
        
        # Add pagination buttons if needed
        if comments_data['total_pages'] > 1:
            buttons = []
            if comments_data['has_previous']:
                buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] - 1}"))
            if comments_data['has_next']:
                buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] + 1}"))
            if buttons:
                keyboard.row(*buttons)
        
        # Edit message
        bot.edit_message_text(
            response_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        print(f"Error in handle_comments_pagination: {e}")


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
        user_states[telegram_id] = {
            'state': 'waiting_comment_text',
            'data': {
                'confession_id': confession_id
            }
        }
        
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
        
        # Add reaction
        from bot.services.comment_service import add_reaction
        add_reaction(user, comment, 'like')
        
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
        
        # Add reaction
        from bot.services.comment_service import add_reaction
        add_reaction(user, comment, 'dislike')
        
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
        
        # Add reaction
        from bot.services.comment_service import add_reaction
        add_reaction(user, comment, 'report')
        
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
        user_states[telegram_id] = {
            'state': 'waiting_reply_text',
            'data': {
                'confession_id': comment.confession.id,
                'parent_comment_id': comment_id
            }
        }
        
        # Show comment preview
        comment_preview = comment.text[:200] + "..." if len(comment.text) > 200 else comment.text
        
        response_text = f"""
💬 <b>Reply to Comment</b>

<b>Original Comment by {comment.user.first_name}:</b>
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


@bot.callback_query_handler(func=lambda call: True)
def handle_unknown_callback(call: CallbackQuery):
    """Handle unknown callback queries"""
    logger.warning(f"Unknown callback query received: {call.data}")
    bot.answer_callback_query(
        call.id,
        "❌ This button action is not recognized. Please try again or use /help for assistance.",
        show_alert=True
    )


@bot.message_handler(func=lambda message: True)
def handle_unknown_command(message: Message):
    """Handle unknown commands and messages"""
    telegram_id = message.from_user.id
    
    # Check if user is in a conversation state
    if telegram_id in user_states:
        state = user_states[telegram_id].get('state')
        
        if state == 'waiting_confession_text':
            # User is submitting confession text
            confession_text = message.text
            
            if not confession_text or len(confession_text.strip()) == 0:
                bot.reply_to(message, "❌ Confession cannot be empty. Please type your confession or use /cancel to cancel.")
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
                comment = create_comment(user, confession, comment_text)
                
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
                reply = create_comment(user, confession, reply_text, parent_comment=parent_comment)
                
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

Use /help for more information.
        """
        bot.reply_to(message, error_text)
    else:
        # Regular message
        bot.reply_to(message, "Please use /help to see available commands.")
