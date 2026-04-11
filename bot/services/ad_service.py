"""
Ad service for broadcasting advertisements to all bot users.
Supports resumable broadcast for serverless environments (Vercel).
"""
import html as html_module
import logging
import time
from django.utils import timezone
from bot.models import Ad, User

logger = logging.getLogger(__name__)

# Leave 2s buffer before Vercel's 10s limit
VERCEL_SAFE_SECONDS = 7


def create_ad(admin_user, text):
    """
    Create a draft ad.

    Raises:
        ValueError: If text exceeds 4096 characters
    """
    if len(text) > 4096:
        raise ValueError(f"Ad text exceeds maximum length of 4096 characters (current: {len(text)})")
    return Ad.objects.create(created_by=admin_user, text=text, status='draft')


def broadcast_ad(ad, bot_instance):
    """
    Send an ad to all registered bot users (excluding the sender).
    Saves progress so it can be resumed if the serverless function times out.

    Returns:
        dict: {'sent': int, 'failed': int, 'done': bool}
              done=False means there are still users left (call again to resume)
    """
    start_time = time.time()

    sender_id = ad.created_by_id

    # Resume from where we left off
    qs = User.objects.exclude(id=sender_id).order_by('id')
    if ad.last_sent_user_id:
        qs = qs.filter(id__gt=ad.last_sent_user_id)

    # Mark as sending on first run
    if ad.status == 'draft':
        ad.status = 'sending'
        ad.save(update_fields=['status'])

    message_text = f"📢 <b>Announcement</b>\n\n{html_module.escape(ad.text)}"

    sent = ad.total_recipients
    failed = ad.failed_count
    last_user_id = ad.last_sent_user_id
    done = True

    for user in qs.iterator():
        # Check if we're approaching the time limit
        if time.time() - start_time > VERCEL_SAFE_SECONDS:
            done = False
            break

        try:
            bot_instance.send_message(user.telegram_id, message_text, parse_mode='HTML')
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send ad to user {user.telegram_id}: {e}")
            failed += 1

        last_user_id = user.id

        # Respect Telegram rate limit: ~30 msg/sec, sleep every 25
        if (sent + failed) % 25 == 0:
            time.sleep(1)

    # Save progress
    update_fields = ['total_recipients', 'failed_count', 'last_sent_user_id']
    ad.total_recipients = sent
    ad.failed_count = failed
    ad.last_sent_user_id = last_user_id

    if done:
        ad.status = 'sent'
        ad.sent_at = timezone.now()
        update_fields += ['status', 'sent_at']

    ad.save(update_fields=update_fields)

    logger.info(f"Ad #{ad.id} batch: sent={sent}, failed={failed}, done={done}")
    return {'sent': sent, 'failed': failed, 'done': done}
