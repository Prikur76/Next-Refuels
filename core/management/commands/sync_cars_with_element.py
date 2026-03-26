# mypy: ignore-missing-imports
import asyncio

from django.core.management.base import BaseCommand

from core.clients.element_car_client import ElementCarClient
from core.utils.logging import log_sync_failure, log_sync_success


class Command(BaseCommand):
    help = "Синхронизация автомобилей с 1С:Элемент"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Принудительная синхронизация независимо от расписания",
        )
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Только проверка доступности API",
        )
        parser.add_argument(
            "--sample",
            action="store_true",
            help="Показать пример данных без синхронизации",
        )

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        self.stdout.write("Начинаю синхронизацию с 1С:Элемент...")

        try:
            # =================== ВСЁ ДЕЛАЕМ ТОЛЬКО ЧЕРЕЗ async with ===================
            async with ElementCarClient() as client:
                # =================== CHECK ONLY / SAMPLE ===================
                if options["check_only"] or options["sample"]:
                    sample_count = 2 if options["check_only"] else 5
                    sample_raw = await client.get_sample_data(sample_count)
                    sample = [
                        client._map_external_to_internal(car)
                        for car in sample_raw
                        if client._map_external_to_internal(car)
                    ]

                    if not sample:
                        self.stdout.write(
                        self.style.WARNING("Нет данных для отображения")
                        )
                        return

                    self.stdout.write("Пример данных из 1С:")

                    headers = [
                        "№",
                        "Госномер",
                        "Модель",
                        "Регион",
                        "Активен",
                        "Статус",
                    ]

                    col_widths = [
                        3,
                        max(
                            max(
                                len(c.get("state_number", "")) for c in sample
                            ),
                            len("Госномер"),
                        ),
                        max(
                            max(len(c.get("model", "")) for c in sample),
                            len("Модель"),
                        ),
                        max(
                            max(len(c.get("region_name", "")) for c in sample),
                            len("Регион"),
                        ),
                        max(
                            max(
                                len(str(c.get("is_active", "")))
                                for c in sample
                            ),
                            len("Активен"),
                        ),
                        max(
                            max(len(str(c.get("status", ""))) for c in sample),
                            len("Статус"),
                        ),
                    ]

                    header_line = " | ".join(
                        h.ljust(col_widths[i]) for i, h in enumerate(headers)
                    )
                    self.stdout.write(header_line)
                    self.stdout.write("-" * len(header_line))

                    for i, car in enumerate(sample, 1):
                        line = " | ".join(
                            [
                                str(i).ljust(col_widths[0]),
                                car.get("state_number", "").ljust(
                                    col_widths[1]
                                ),
                                car.get("model", "").ljust(col_widths[2]),
                                car.get("region_name", "").ljust(
                                    col_widths[3]
                                ),
                                str(car.get("is_active", "")).ljust(
                                    col_widths[4]
                                ),
                                str(car.get("status", "") or "").ljust(
                                    col_widths[5]
                                ),
                            ]
                        )
                        self.stdout.write(line)

                    return

                # =================== ПРОВЕРКА ДОСТУПНОСТИ API ===================
                if not await client.check_availability():
                    self.stdout.write(
                        self.style.ERROR(
                            "API 1С:Элемент недоступен, пропускаю синхронизацию"
                        )
                    )
                    await log_sync_failure("API недоступен")
                    return

                # =================== СИНХРОНИЗАЦИЯ ===================
                stats = await client.sync_with_database()
                message = self._format_stats_message(stats)
                self.stdout.write(self.style.SUCCESS(message))
                await log_sync_success(message, stats)

        except Exception as e:
            error_msg = f"Ошибка синхронизации: {str(e)}"
            self.stdout.write(self.style.ERROR(error_msg))
            await log_sync_failure(error_msg)

    def _format_stats_message(self, stats: dict) -> str:
        parts = []

        if stats.get("created", 0) > 0:
            parts.append(f"создано: {stats['created']}")
        if stats.get("updated", 0) > 0:
            parts.append(f"обновлено: {stats['updated']}")
        if stats.get("restored", 0) > 0:
            parts.append(f"восстановлено: {stats['restored']}")
        if stats.get("archived", 0) > 0:
            parts.append(f"архивировано: {stats['archived']}")
        if stats.get("regions_created", 0) > 0:
            parts.append(f"регионов создано: {stats['regions_created']}")
        if stats.get("regions_updated", 0) > 0:
            parts.append(f"регионов обновлено: {stats['regions_updated']}")
        if stats.get("errors", 0) > 0:
            parts.append(f"ошибок: {stats['errors']}")

        parts.append(f"всего обработано: {stats['total_processed']}")

        return "Синхронизация завершена: " + ", ".join(parts)
