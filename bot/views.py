import json
import telebot
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# Lazy import bot to avoid initialization issues
_bot_instance = None

def get_bot():
    """Lazy load bot instance to avoid cold start issues"""
    global _bot_instance
    if _bot_instance is None:
        from bot.bot import bot
        _bot_instance = bot
    return _bot_instance


@csrf_exempt
@require_http_methods(["POST"])
def webhook(request, *args, **kwargs):
    try:
        raw_data = request.body.decode("utf-8")

        if not raw_data:
            return JsonResponse({"status": "ignored-empty"}, status=200)

        data = json.loads(raw_data)
        
        # Log the update type for debugging
        update_type = "unknown"
        if "message" in data:
            update_type = "message"
        elif "callback_query" in data:
            update_type = "callback_query"
            print(f"Callback query data: {data.get('callback_query', {}).get('data', 'N/A')}")
        elif "edited_message" in data:
            update_type = "edited_message"
        
        print(f"Webhook received update type: {update_type}")

        update = telebot.types.Update.de_json(data)

        bot = get_bot()
        bot.process_new_updates([update])

        return JsonResponse({"status": "ok"}, status=200)

    except Exception as e:
        # Never return 400 to Telegram — it will disable your webhook
        print("Webhook error:", e)
        import traceback
        traceback.print_exc()
        return JsonResponse({"status": "ok"}, status=200)


def test(request):
    """Simple test endpoint to verify deployment"""
    try:
        # Test database connection
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    try:
        # Test bot initialization
        bot = get_bot()
        bot_status = f"initialized (@{bot.get_me().username})"
    except Exception as e:
        bot_status = f"error: {str(e)}"
    
    return JsonResponse({
        "status": "ok", 
        "message": "Bot is running",
        "database": db_status,
        "bot": bot_status
    }, status=200)
