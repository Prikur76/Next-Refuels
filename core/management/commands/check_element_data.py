import asyncio

from django.core.management.base import BaseCommand

from core.clients.element_car_client import ElementCarClient


class Command(BaseCommand):
    help = "Проверка данных из 1С:Элемент"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Лимит вывода",
        )

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        self.stdout.write("🔍 Проверка данных из 1С:Элемент...")

        try:
            async with ElementCarClient() as client:
                # Проверяем доступность
                if not await client.check_availability():
                    self.stdout.write(self.style.ERROR("❌ API недоступно"))
                    return

                # Получаем данные
                cars = await client.fetch_cars()

                if not cars:
                    self.stdout.write(self.style.WARNING("⚠️ Нет данных"))
                    return

                self.stdout.write(f"📊 Найдено {len(cars)} автомобилей:\n")

                # Выводим информацию о первых N автомобилях
                for i, car in enumerate(cars[: options["limit"]], 1):
                    self.stdout.write(
                        f"{i}. {car.get('Number', 'N/A')} | {car.get('Model', 'N/A')}"
                    )
                    self.stdout.write(f"   Код: {car.get('Code', 'N/A')}")
                    self.stdout.write(f"   VIN: {car.get('VIN', 'N/A')}")
                    self.stdout.write(
                        f"   Год выпуска: {car.get('YearCar', 'N/A')}"
                    )
                    self.stdout.write(
                        f"   Регион: {car.get('Region', 'Не указан')}"
                    )
                    self.stdout.write(
                        f"   Подразделение: {car.get('Department', 'Не указано')}"
                    )
                    self.stdout.write(
                        f"   ИНН владельца: {car.get('INN', 'Не указано')}"
                    )
                    self.stdout.write(
                        f"   Активен: {car.get('Activity', 'N/A')}"
                    )
                    self.stdout.write(
                        f"   Статус: {car.get('Status', 'Не указан')}"
                    )
                    self.stdout.write("   " + "-" * 40)

                if len(cars) > options["limit"]:
                    self.stdout.write(
                        f"... и еще {len(cars) - options['limit']} автомобилей"
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Ошибка: {str(e)}"))
