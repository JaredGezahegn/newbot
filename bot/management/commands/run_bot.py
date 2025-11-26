from typing import Any
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from bot.bot import bot


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any):
        bot.remove_webhook()
        bot.infinity_polling()
