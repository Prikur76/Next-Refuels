from django.core.management.base import BaseCommand

from core.services.car_service import CarService


class Command(BaseCommand):
    help = "Отчет по возрасту автомобилей"

    def add_arguments(self, parser):
        parser.add_argument(
            "--detail",
            action="store_true",
            help="Детальный отчет с распределением",
        )

    def handle(self, *args, **options):
        if options["detail"]:
            self.detailed_report()
        else:
            self.basic_report()

    def basic_report(self):
        """Базовый отчет по возрасту"""
        report = CarService.get_fleet_age_report()

        self.stdout.write("📊 ОТЧЕТ ПО ВОЗРАСТУ АВТОПАРКА")
        self.stdout.write("=" * 40)
        self.stdout.write(f"Всего автомобилей: {report['total_cars']}")
        self.stdout.write(f"Активных: {report['active_cars']}")
        self.stdout.write(f"Средний возраст: {report['avg_age']} лет")
        self.stdout.write(f"Диапазон возрастов: {report['age_range']}")
        self.stdout.write(f"Года выпуска: {report['year_range']}")

        self.stdout.write("\n📈 ВОЗРАСТНЫЕ ГРУППЫ:")
        for group, count in report["age_distribution"].items():
            self.stdout.write(f"  {group}: {count} автомобилей")

    def detailed_report(self):
        """Детальный отчет с распределением"""
        age_stats = CarService.get_age_statistics()

        self.stdout.write("📊 ДЕТАЛЬНЫЙ ОТЧЕТ ПО ВОЗРАСТУ")
        self.stdout.write("=" * 50)

        stats = age_stats["basic_stats"]
        self.stdout.write(f"Средний возраст: {stats['avg_age']:.1f} лет")
        self.stdout.write(f"Минимальный возраст: {stats['min_age']} лет")
        self.stdout.write(f"Максимальный возраст: {stats['max_age']} лет")
        self.stdout.write(
            f"Самый новый автомобиль: {stats['newest_year']} года"
        )
        self.stdout.write(
            f"Самый старый автомобиль: {stats['oldest_year']} года"
        )

        self.stdout.write("\n📊 РАСПРЕДЕЛЕНИЕ ПО ВОЗРАСТАМ:")
        for item in age_stats["age_distribution"]:
            age = item["age"]
            count = item["count"]
            self.stdout.write(f"  {age} лет: {count} автомобилей")
