from typing import Any, Dict, List

from django.db import transaction
from django.db.models import Avg, Count, F, Max, Min, Q
from django.utils import timezone

from core.models import Car


class CarService:
    """Сервис для бизнес-логики работы с автомобилями"""

    @staticmethod
    @transaction.atomic
    def create_car_with_validation(car_data: Dict[str, Any]) -> Car:
        """
        Создание автомобиля с комплексной валидацией
        """
        # Валидация обязательных полей
        required_fields = ["code", "state_number", "model"]
        for field in required_fields:
            if not car_data.get(field):
                raise ValueError(f"Обязательное поле {field} не заполнено")

        # Проверяем, не архивный ли автомобиль
        if car_data.get("status") == "АРХИВ" or not car_data.get(
            "is_active", True
        ):
            raise ValueError(
                "Нельзя создавать архивные автомобили через этот метод"
            )

        # Используем менеджер для создания
        return Car.objects.create_car(**car_data)

    @staticmethod
    def validate_car_uniqueness(
        car_data: Dict[str, Any], exclude_car_id: int = None
    ) -> List[str]:
        """
        Проверяет уникальность данных автомобиля
        Возвращает список ошибок
        """
        errors = []

        # Проверяем код среди активных автомобилей
        code_qs = Car.objects.active()
        if exclude_car_id:
            code_qs = code_qs.exclude(id=exclude_car_id)

        if code_qs.filter(code=car_data["code"]).exists():
            errors.append(
                f"Код {car_data['code']} уже используется активным автомобилем"
            )

        # Проверяем госномер среди активных
        state_number_qs = Car.objects.active()
        if exclude_car_id:
            state_number_qs = state_number_qs.exclude(id=exclude_car_id)

        if state_number_qs.filter(
            state_number=car_data["state_number"]
        ).exists():
            errors.append(
                f"Госномер {car_data['state_number']} уже используется активным автомобилем"
            )

        # Проверяем VIN среди активных (если указан)
        vin = car_data.get("vin")
        if vin and vin.strip():
            vin_qs = Car.objects.active()
            if exclude_car_id:
                vin_qs = vin_qs.exclude(id=exclude_car_id)

            if vin_qs.filter(vin=vin).exists():
                errors.append(
                    f"VIN {vin} уже используется активным автомобилем"
                )

        return errors

    @staticmethod
    def bulk_archive_cars(
        car_ids: List[int], reason: str = "Массовая архивация"
    ):
        """
        Массовая архивация автомобилей
        """
        archived_count = 0
        for car_id in car_ids:
            try:
                car = Car.objects.get(id=car_id)
                if not car.is_archived:
                    car.archive(reason)
                    archived_count += 1
            except Car.DoesNotExist:
                continue

        return archived_count

    @staticmethod
    def get_age_statistics():
        """Детальная статистика по возрасту автомобилей"""
        current_year = timezone.now().year

        stats = Car.objects.aggregate(
            total_cars=Count("id"),
            active_cars=Count("id", filter=Q(is_active=True)),
            avg_age=Avg(current_year - F("manufacture_year")),
            min_age=Min(current_year - F("manufacture_year")),
            max_age=Max(current_year - F("manufacture_year")),
            newest_year=Max("manufacture_year"),
            oldest_year=Min("manufacture_year"),
        )

        # Возрастное распределение
        age_groups = (
            Car.objects.filter(manufacture_year__isnull=False)
            .annotate(age=current_year - F("manufacture_year"))
            .values("age")
            .annotate(count=Count("id"))
            .order_by("age")
        )

        # Группировка по диапазонам
        ranges = {
            "0_3_years": Car.objects.filter(
                manufacture_year__gte=current_year - 3
            ).count(),
            "4_7_years": Car.objects.filter(
                manufacture_year__range=[current_year - 7, current_year - 4]
            ).count(),
            "8_12_years": Car.objects.filter(
                manufacture_year__range=[current_year - 12, current_year - 8]
            ).count(),
            "13_plus_years": Car.objects.filter(
                manufacture_year__lte=current_year - 13
            ).count(),
        }

        return {
            "basic_stats": stats,
            "age_distribution": list(age_groups),
            "age_ranges": ranges,
        }

    @staticmethod
    def get_fleet_age_report():
        """Отчет по возрасту автопарка"""
        age_stats = CarService.get_age_statistics()
        basic_stats = age_stats["basic_stats"]

        report = {
            "total_cars": basic_stats["total_cars"],
            "active_cars": basic_stats["active_cars"],
            "avg_age": round(basic_stats["avg_age"] or 0, 1),
            "age_range": f"{basic_stats['min_age'] or 0}-{basic_stats['max_age'] or 0} лет",
            "year_range": f"{basic_stats['oldest_year'] or 0}-{basic_stats['newest_year'] or 0}",
            "age_distribution": age_stats["age_ranges"],
        }

        return report
