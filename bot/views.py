@csrf_exempt
@require_http_methods(["POST"])
def webhook(request, *args, **kwargs):
    try:
        raw_data = request.body.decode("utf-8")

        if not raw_data:
            return JsonResponse({"status": "ignored-empty"}, status=200)

        data = json.loads(raw_data)

        update = telebot.types.Update.de_json(data)

        bot.process_new_updates([update])

        return JsonResponse({"status": "ok"}, status=200)

    except Exception as e:
        # Never return 400 to Telegram — it will disable your webhook
        print("Webhook error:", e)
        return JsonResponse({"status": "ok"}, status=200)
