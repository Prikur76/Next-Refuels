# core/management/commands/runbot.py
from django.core.management.base import BaseCommand

from core.refuel_bot.main import run_bot


class Command(BaseCommand):
    help = "Run Telegram bot"

    def handle(self, *args, **options):
        self.stdout.write("Starting Telegram bot...")
        run_bot()
