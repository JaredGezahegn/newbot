"""
Ad service for broadcasting advertisements to all bot users.
"""
import html as html_module
import logging
from django.utils import timezone
from bot.models import Ad, User

logger = logging.getLogger(__name__)


def create_ad(admin_user, text):
    """
    Create a draft ad.

    Args:
        admin_user: User instance (must be admin)
        text: Ad message text (max 4096 characters)

    Returns:
        Ad: The created Ad instance

    Raises:
        ValueError: If text exceeds 4096 characters
    """
    if len(text) > 4096:
        raise ValueError(f"Ad text exceeds maximum length of 4096 characters (current: {len(text)})")

    return Ad.objects.create(created_by=admin_user, text=text, status='draft')


def broadcast_ad(ad, bot_instance):
    """
    Send an ad to all registered bot users (excluding the sender).

    Args:
        ad: Ad instance (should be in 'draft' status)
        bot_instance: TeleBot instance

    Returns:
        dict: {'sent': int, 'failed': int}
    """
    sender_id = ad.created_by_id  # exclude the admin who created the ad
    users = User.objects.exclude(id=sender_id).values_list('telegram_id', flat=True)

    sent = 0
    failed = 0

    message_text = f"📢 <b>Announcement</b>\n\n{html_module.escape(ad.text)}"

    for telegram_id in users:
        try:
            bot_instance.send_message(telegram_id, message_text, parse_mode='HTML')
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send ad to user {telegram_id}: {e}")
            failed += 1

    ad.status = 'sent'
    ad.sent_at = timezone.now()
    ad.total_recipients = sent
    ad.failed_count = failed
    ad.save(update_fields=['status', 'sent_at', 'total_recipients', 'failed_count'])

    logger.info(f"Ad #{ad.id} broadcast complete: {sent} sent, {failed} failed")
    return {'sent': sent, 'failed': failed}
