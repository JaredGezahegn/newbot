import json
import telebot
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from bot.bot import bot


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
    return JsonResponse({"status": "ok", "message": "Bot is running"}, status=200)
