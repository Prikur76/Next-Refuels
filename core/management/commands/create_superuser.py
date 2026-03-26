import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates a superuser from environment variables if it doesn't already exist."

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.getenv("DJANGO_SUPERUSER_USERNAME")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

        # Если данные не заданы — ничего не делаем (не ошибка)
        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Superuser env variables not set — skipping."
                )
            )
            return

        # Проверяем по username и email
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Superuser '{username}' already exists — skipping."
                )
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"User with email '{email}' already exists — skipping."
                )
            )
            return

        # Создаём суперпользователя
        self.stdout.write("Creating superuser...")

        User.objects.create_superuser(
            username=username, email=email, password=password
        )

        self.stdout.write(
            self.style.SUCCESS(f"Superuser '{username}' created successfully.")
        )
