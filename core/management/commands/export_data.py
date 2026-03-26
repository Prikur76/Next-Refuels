# mypy: ignore-missing-imports
import os

from django.core.management.base import BaseCommand

from core.services.export_service import ExportService


class Command(BaseCommand):
    help = "Экспорт данных в CSV и Excel"

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            choices=["cars", "fuel_records", "all"],
            default="all",
            help="Модель для экспорта (cars, fuel_records, all)",
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=["csv", "xlsx"],
            default="csv",
            help="Формат экспорта (csv, xlsx)",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            help="Директория для сохранения файлов (по умолчанию - текущая)",
        )

    def handle(self, *args, **options):
        model = options["model"]
        format_type = options["format"]
        output_dir = options["output_dir"] or os.getcwd()

        self.stdout.write("Начинаю экспорт данных...")
        self.stdout.write(f"   Модель: {model}")
        self.stdout.write(f"   Формат: {format_type}")
        self.stdout.write(f"   Директория: {output_dir}")

        try:
            if model in ["cars", "all"]:
                self.export_cars(format_type, output_dir)

            if model in ["fuel_records", "all"]:
                self.export_fuel_records(format_type, output_dir)

            self.stdout.write(self.style.SUCCESS("Экспорт завершен успешно!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка экспорта: {e}"))

    def export_cars(self, format_type: str, output_dir: str):
        """Экспорт автомобилей"""
        self.stdout.write("Экспорт автомобилей...")

        response = ExportService.export_cars_data(format_type)
        filename = (
            response["Content-Disposition"]
            .split('filename="')[1]
            .split('"')[0]
        )
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "wb") as f:
            f.write(response.content)

        self.stdout.write(f"   Сохранено: {filepath}")

    def export_fuel_records(self, format_type: str, output_dir: str):
        """Экспорт заправок"""
        self.stdout.write("Экспорт заправок...")

        response = ExportService.export_fuel_records_data(format_type)
        filename = (
            response["Content-Disposition"]
            .split('filename="')[1]
            .split('"')[0]
        )
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "wb") as f:
            f.write(response.content)

        self.stdout.write(f"   Сохранено: {filepath}")
