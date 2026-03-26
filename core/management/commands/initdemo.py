# core/management/commands/initdemo.py
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Car, Region

User = get_user_model()


class Command(BaseCommand):
    help = "Создаёт демо-данные для теста Telegram-бота и системы"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("🚀 Инициализация тестовых данных...")

        # Проверяем наличие групп (если нет — создадим через signal)
        groups = ["Заправщик", "Менеджер", "Администратор"]
        for name in groups:
            group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(f"✅ Создана группа: {name}")
            else:
                self.stdout.write(f"ℹ️ Группа '{name}' уже существует")

        # Создаём регионы
        ekb, _ = Region.objects.get_or_create(
            name="Екатеринбург", short_name="ЕКБ"
        )
        perm, _ = Region.objects.get_or_create(
            name="Пермь", short_name="ПЕРМЬ"
        )

        self.stdout.write("🌍 Добавлены регионы")

        # Создаём тестовый автомобиль
        car, _ = Car.objects.get_or_create(
            code="CAR001",
            defaults={
                "state_number": "A001AA66",
                "vin": "MR0HA3CD500700016",
                "model": "Toyota Hilux",
                "manufacture_year": 2015,
                "fuel_type": "gasoline",
                "owner_inn": "123456789012",
                "department": "Department A",
                "is_active": True,
                "status": "test",
                "region": ekb,
            },
        )

        self.stdout.write(
            f"🚗 Добавлен автомобиль: {car.code} ({car.state_number})"
        )

        # Создаём тестового пользователя-заправщика
        tg_id = 8534784713  # можно заменить на свой ID из Telegram
        user, created = User.objects.get_or_create(
            username="fuelman",
            defaults={
                "telegram_id": tg_id,
                "full_name": "Иван Заправкин",
                "is_active": True,
                "region": ekb,
            },
        )
        if created:
            user.set_password("demo1234")
            user.save()
            user.groups.add(Group.objects.get(name="Заправщик"))
            self.stdout.write(
                f"👤 Создан пользователь-заправщик: {user.username} (пароль demo1234)"
            )
        else:
            self.stdout.write(f"ℹ️ Пользователь {user.username} уже существует")

        self.stdout.write("✅ Инициализация завершена.")
        self.stdout.write(
            "Теперь вы можете войти в админку и протестировать Telegram-бота!"
        )
