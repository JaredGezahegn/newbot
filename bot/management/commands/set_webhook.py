from typing import Any
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser
from django.conf import settings
from bot.bot import bot


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any):
        bot.set_webhook(settings.WEB_HOOK_URL)
