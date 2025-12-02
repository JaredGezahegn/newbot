"""
Confession service for managing confession lifecycle.
"""
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from bot.models import Confession, User


def create_confession(user, text, is_anonymous=None):
    """
    Create a new confession in pending state.
    
    Args:
        user: User instance
        text: Confession text (max 4096 characters)
        is_anonymous: Boolean indicating if confession is anonymous (defaults to user's setting)
    
    Returns:
        Confession: The created confession
    
    Raises:
        ValueError: If text exceeds 4096 characters
    """
    if len(text) > 4096:
        raise ValueError(f"Confession text exceeds maximum length of 4096 characters (current: {len(text)})")
    
    # Use user's anonymity setting if not explicitly specified
    if is_anonymous is None:
        is_anonymous = user.is_anonymous_mode
    
    confession = Confession.objects.create(
        user=user,
        text=text,
        is_anonymous=is_anonymous,
        status='pending'
    )
    
    return confession


def approve_confession(confession, admin, bot_instance=None):
    """
    Approve a confession and publish it to the channel.
    
    Args:
        confession: Confession instance
        admin: User instance with admin privileges
        bot_instance: TeleBot instance for publishing (optional)
    
    Returns:
        Confession: The approved confession
    """
    with transaction.atomic():
        confession.status = 'approved'
        confession.reviewed_by = admin
        confession.reviewed_at = timezone.now()
        confession.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        
        # Increment user's confession count
        confession.user.total_confessions += 1
        confession.user.save(update_fields=['total_confessions'])
        
        # Publish to channel if bot instance provided
        if bot_instance:
            channel_message_id = publish_to_channel(confession, bot_instance)
            confession.channel_message_id = channel_message_id
            confession.save(update_fields=['channel_message_id'])
    
    return confession


def reject_confession(confession, admin):
    """
    Reject a confession.
    
    Args:
        confession: Confession instance
        admin: User instance with admin privileges
    
    Returns:
        Confession: The rejected confession
    """
    confession.status = 'rejected'
    confession.reviewed_by = admin
    confession.reviewed_at = timezone.now()
    confession.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    
    return confession


def delete_confession(confession, bot_instance=None):
    """
    Delete a confession from the database and channel.
    
    Args:
        confession: Confession instance
        bot_instance: TeleBot instance for deleting from channel (optional)
    
    Returns:
        bool: True if deleted successfully
    """
    # Delete from channel if published
    if confession.channel_message_id and bot_instance:
        try:
            channel_id = getattr(settings, 'CHANNEL_ID', None)
            if channel_id:
                bot_instance.delete_message(channel_id, confession.channel_message_id)
        except Exception as e:
            # Log error but continue with database deletion
            print(f"Error deleting message from channel: {e}")
    
    # Delete from database
    confession.delete()
    return True


def get_pending_confessions():
    """
    Get all confessions in pending state.
    
    Returns:
        QuerySet: Confessions with status 'pending'
    """
    return Confession.objects.filter(status='pending').select_related('user').order_by('created_at')


def publish_to_channel(confession, bot_instance):
    """
    Publish a confession to the configured Telegram channel.
    
    Args:
        confession: Confession instance
        bot_instance: TeleBot instance
    
    Returns:
        int: Message ID of the published message
    
    Raises:
        ValueError: If CHANNEL_ID is not configured
    """
    channel_id = getattr(settings, 'CHANNEL_ID', None)
    if not channel_id:
        raise ValueError("CHANNEL_ID not configured in settings")
    
    # Format the message
    author = "Anonymous" if confession.is_anonymous else f"{confession.user.first_name}"
    if not confession.is_anonymous and confession.user.username:
        author += f" (@{confession.user.username})"
    
    message_text = f"""
📝 <b>Confession {confession.id}</b>

{confession.text}

<i>— {author}</i>
"""
    
    # Create inline keyboard with "View / Add Comments" button
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("View / Add Comments", callback_data=f"view_comments_{confession.id}"))
    
    # Send to channel
    sent_message = bot_instance.send_message(
        channel_id,
        message_text,
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
    return sent_message.message_id
