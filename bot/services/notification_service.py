"""
Notification service for admin and user notifications.
"""
from django.conf import settings
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def notify_admins_new_confession(confession, bot_instance):
    """
    Notify all configured admins about a new pending confession.
    
    Args:
        confession: Confession instance in pending state
        bot_instance: TeleBot instance for sending messages
    
    Returns:
        list: List of message IDs sent to admins
    """
    admins = getattr(settings, 'ADMINS', [])
    if not admins:
        return []
    
    # Format the notification message
    author = "Anonymous" if confession.is_anonymous else f"{confession.user.first_name}"
    if not confession.is_anonymous and confession.user.username:
        author += f" (@{confession.user.username})"
    
    # Truncate text for preview if too long
    preview_text = confession.text
    if len(preview_text) > 200:
        preview_text = preview_text[:200] + "..."
    
    message_text = f"""
🔔 <b>New Confession Pending Review</b>

<b>ID:</b> {confession.id}
<b>From:</b> {author}
<b>Submitted:</b> {confession.created_at.strftime('%Y-%m-%d %H:%M UTC')}

<b>Preview:</b>
{preview_text}
"""
    
    # Create inline keyboard with approve/reject buttons
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{confession.id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{confession.id}")
    )
    
    # Send to all admins
    sent_message_ids = []
    for admin_id in admins:
        try:
            sent_message = bot_instance.send_message(
                admin_id,
                message_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
            sent_message_ids.append(sent_message.message_id)
        except Exception as e:
            # Log error but continue notifying other admins
            print(f"Error notifying admin {admin_id}: {e}")
    
    return sent_message_ids


def notify_user_confession_status(confession, status, bot_instance):
    """
    Notify user about their confession status (approved or rejected).
    
    Args:
        confession: Confession instance
        status: Status string ('approved' or 'rejected')
        bot_instance: TeleBot instance for sending messages
    
    Returns:
        int: Message ID of the notification, or None if failed
    """
    user_telegram_id = confession.user.telegram_id
    
    if status == 'approved':
        message_text = f"""
✅ <b>Confession Approved</b>

Your confession (ID: {confession.id}) has been approved and published to the channel!

You can view it and see comments from the community.
"""
    elif status == 'rejected':
        message_text = f"""
❌ <b>Confession Rejected</b>

Your confession (ID: {confession.id}) was not approved for publication.

If you have questions, please contact an administrator.
"""
    else:
        # Unknown status
        return None
    
    try:
        sent_message = bot_instance.send_message(
            user_telegram_id,
            message_text,
            parse_mode='HTML'
        )
        return sent_message.message_id
    except Exception as e:
        # Log error
        print(f"Error notifying user {user_telegram_id}: {e}")
        return None
