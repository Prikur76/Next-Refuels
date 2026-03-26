from datetime import datetime, time, timedelta

from django.db import models
from django.db.models import Avg, Count, Max, Min, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class FuelRecordQuerySet(models.QuerySet):
    """Кастомный QuerySet для модели FuelRecord"""

    def by_car(self, car):
        """Записи по конкретному автомобилю"""
        if isinstance(car, models.Model):
            return self.filter(car=car)
        return self.filter(car__state_number=car)

    def by_employee(self, employee):
        """Записи по сотруднику"""
        if isinstance(employee, models.Model):
            return self.filter(employee=employee)
        return self.filter(employee__username=employee)

    def by_region(self, region):
        """Записи по региону"""
        if isinstance(region, models.Model):
            return self.filter(car__region=region)
        return self.filter(car__region__name=region)

    def by_source(self, source):
        """Записи по источнику заправки"""
        return self.filter(source=source)

    def by_fuel_type(self, fuel_type):
        """Записи по типу топлива"""
        return self.filter(fuel_type=fuel_type)

    def recent(self, days=30):
        """Записи за последние N дней"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(filled_at__gte=cutoff_date)

    def today(self):
        """Записи за сегодня"""
        today = timezone.now().date()
        start = timezone.make_aware(datetime.combine(today, time.min))
        end = start + timedelta(days=1)
        return self.filter(filled_at__gte=start, filled_at__lt=end)

    def this_week(self):
        """Записи за текущую неделю"""
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        start = timezone.make_aware(datetime.combine(start_of_week, time.min))
        return self.filter(filled_at__gte=start)

    def this_month(self):
        """Записи за текущий месяц"""
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start = timezone.make_aware(datetime.combine(start_of_month, time.min))
        return self.filter(filled_at__gte=start)

    def with_related_data(self):
        """Оптимизация запросов с подгрузкой связанных данных"""
        return self.select_related("car", "employee", "car__region")

    def total_liters(self):
        """Общее количество литров в выборке"""
        result = self.aggregate(total=Sum("liters"))
        return result["total"] or 0

    def avg_liters_per_record(self):
        """Среднее количество литров на заправку"""
        result = self.aggregate(avg=Avg("liters"))
        return result["avg"] or 0

    def fuel_statistics(self):
        """Расширенная статистика по топливу"""
        return self.aggregate(
            total_records=Count("id"),
            total_liters=Sum("liters"),
            avg_liters=Avg("liters"),
            max_liters=Max("liters"),
            min_liters=Min("liters"),
        )

    def by_period(self, start_date, end_date):
        """Записи за указанный период"""
        start = timezone.make_aware(datetime.combine(start_date, time.min))
        end = timezone.make_aware(
            datetime.combine(end_date + timedelta(days=1), time.min)
        )
        return self.filter(filled_at__gte=start, filled_at__lt=end)

    def find_suspicious_records(self, threshold_liters=400):
        """Поиск подозрительных записей (слишком большие объёмы)"""
        return self.filter(liters__gt=threshold_liters)

    def group_by_car(self):
        """Группировка по автомобилям с агрегацией"""
        return (
            self.values("car__state_number", "car__model")
            .annotate(
                total_liters=Sum("liters"),
                record_count=Count("id"),
                avg_liters=Avg("liters"),
                last_refuel=Max("filled_at"),
            )
            .order_by("-total_liters")
        )

    def group_by_employee(self):
        """Группировка по сотрудникам с агрегацией"""
        return (
            self.values(
                "employee__username",
                "employee__first_name",
                "employee__last_name",
            )
            .annotate(
                total_liters=Sum("liters"),
                record_count=Count("id"),
                avg_liters=Avg("liters"),
            )
            .order_by("-total_liters")
        )

    def group_by_region(self):
        """Группировка по регионам с агрегацией"""
        return (
            self.values("car__region__name")
            .annotate(
                total_liters=Sum("liters"),
                record_count=Count("id"),
                car_count=Count("car", distinct=True),
            )
            .order_by("-total_liters")
        )

    def duplicates_check(self, time_threshold_minutes=30):
        """Поиск потенциальных дубликатов (одинаковая машина + время)"""
        from django.db.models.functions import TruncMinute

        return (
            self.annotate(time_window=TruncMinute("filled_at"))
            .values("car", "time_window")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

    def with_historical_data(self):
        """Оптимизация запросов с подгрузкой исторических данных"""
        return self.select_related(
            "car", "employee", "car__region", "historical_region"
        )

    def by_historical_region(self, region):
        """Записи по историческому региону"""
        if isinstance(region, models.Model):
            return self.filter(historical_region=region)
        return self.filter(historical_region__name=region)

    def by_historical_department(self, department):
        """Записи по историческому подразделению"""
        return self.filter(historical_department__icontains=department)

    def create_fuel_record(self, car, employee, liters, **extra_fields):
        """Создание записи о заправке с сохранением исторических данных"""
        from decimal import Decimal, InvalidOperation

        if not car or not employee:
            raise ValueError("Автомобиль и сотрудник обязательны")

        try:
            liters_decimal = Decimal(str(liters))
            if liters_decimal <= 0 or liters_decimal > 1000:
                raise ValueError(f"Некорректное количество литров: {liters}")
        except (InvalidOperation, ValueError):
            raise ValueError(f"Некорректный формат литров: {liters}")

        # Сохраняем исторические данные
        extra_fields["historical_region"] = car.region
        extra_fields["historical_department"] = car.department

        return self.create(
            car=car, employee=employee, liters=liters_decimal, **extra_fields
        )


class FuelRecord(models.Model):
    """
    Запись о заправке автомобиля.
    Вводится через Telegram-ботом.
    """

    class SourceFuel(models.TextChoices):
        CARD = "CARD", _("Топливная карта")
        TGBOT = "TGBOT", _("Телеграм-бот")
        TRUCK = "TRUCK", _("Топливозаправщик")

    class FuelType(models.TextChoices):
        GASOLINE = "GASOLINE", _("Бензин")
        DIESEL = "DIESEL", _("Дизель")

    car = models.ForeignKey(
        "core.Car",
        on_delete=models.CASCADE,
        related_name="fuel_records",
        verbose_name="Автомобиль",
    )
    employee = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fuel_records",
        verbose_name="Сотрудник (заправщик)",
    )
    liters = models.DecimalField(
        max_digits=8, decimal_places=2, verbose_name="Количество литров"
    )
    fuel_type = models.CharField(
        max_length=20,
        choices=FuelType.choices,
        default=FuelType.GASOLINE,
        verbose_name="Тип топлива",
    )
    filled_at = models.DateTimeField(
        default=timezone.now, verbose_name="Дата заправки"
    )
    source = models.CharField(
        max_length=50,
        choices=SourceFuel.choices,
        default=SourceFuel.TGBOT,
        verbose_name="Способ заправки",
    )
    notes = models.TextField(blank=True, verbose_name="Комментарий")
    historical_region = models.ForeignKey(
        "core.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Регион (на момент заправки)",
    )
    historical_department = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Подразделение (на момент заправки)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Создано"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    # Кастомный менеджер через QuerySet.as_manager()
    objects = FuelRecordQuerySet.as_manager()

    class Meta:
        db_table = "fuel_records"
        verbose_name = "Запись о заправке"
        verbose_name_plural = "Заправки"
        ordering = ["-filled_at"]
        indexes = [
            models.Index(fields=["filled_at"]),
            models.Index(fields=["car", "filled_at"]),
            models.Index(fields=["source", "filled_at"]),
            models.Index(fields=["historical_region", "filled_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(liters__gt=0), name="positive_liters"
            )
        ]

    def __str__(self):
        car_info = f"{self.car.state_number}" if self.car else "N/A"
        return f"{car_info} — {self.liters} л ({self.fuel_type})"

    @property
    def display_info(self):
        """Отображаемая информация о заправке"""
        car_info = (
            f"{self.car.state_number} ({self.car.model})"
            if self.car
            else "N/A"
        )
        employee_info = (
            self.employee.get_full_name() if self.employee else "Неизвестно"
        )
        fuel_type_display = self.get_fuel_type_display()

        return (
            f"{car_info} | {self.liters} л | {fuel_type_display} | "
            f"{employee_info} | {self.filled_at.strftime('%d.%m.%Y %H:%M')}"
        )

    @property
    def is_recent(self):
        """Является ли запись недавней (менее 24 часов)"""
        return (timezone.now() - self.filled_at) < timedelta(hours=24)

    def get_fuel_type_display(self):
        """Получение читаемого значения типа топлива"""
        return dict(self.FuelType.choices).get(self.fuel_type, self.fuel_type)

    def get_source_display(self):
        """Получение читаемого значения способа заправки"""
        return dict(self.SourceFuel.choices).get(self.source, self.source)

    def save(self, *args, **kwargs):
        """Сохраняем исторические данные при создании записи"""
        # Если это новая запись (еще нет id)
        if not self.id:
            # Сохраняем текущие данные из автомобиля
            if self.car:
                self.historical_region = self.car.region
                self.historical_department = self.car.department

        super().save(*args, **kwargs)
