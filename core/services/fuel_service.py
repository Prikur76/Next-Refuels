# mypy: ignore-missing-imports
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.utils import timezone

from core.models import Car, FuelRecord

User = get_user_model()


ALLOWED_INPUT_GROUPS = {"Заправщик", "Менеджер", "Администратор"}
ALLOWED_REPORT_GROUPS = {"Менеджер", "Администратор"}


@dataclass(frozen=True)
class FuelCreatePayload:
    car_id: int
    user_id: int
    liters: Decimal
    fuel_type: str
    source: str
    filled_at: datetime | None = None
    notes: str = ""


class FuelService:
    """Единая бизнес-логика ввода и выборок по заправкам."""

    @staticmethod
    def user_has_any_group(user: Any, groups: set[str]) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if bool(getattr(user, "is_superuser", False)):
            return True
        return user.groups.filter(name__in=groups).exists()

    @staticmethod
    def ensure_input_access(user: Any) -> None:
        if not FuelService.user_has_any_group(user, ALLOWED_INPUT_GROUPS):
            raise PermissionDenied("У вас нет прав для добавления заправок")

    @staticmethod
    def ensure_reports_access(user: Any) -> None:
        if not FuelService.user_has_any_group(user, ALLOWED_REPORT_GROUPS):
            raise PermissionDenied("У вас нет прав для просмотра отчётов")

    @staticmethod
    def normalize_liters(raw_liters: Any) -> Decimal:
        text = str(raw_liters).replace(",", ".").strip()
        try:
            value = Decimal(text)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Некорректный формат литров") from exc
        if value <= 0 or value > Decimal("1000"):
            raise ValueError(
                "Количество литров должно быть в диапазоне 0.01-1000"
            )
        return value

    @staticmethod
    def create_fuel_record(payload: FuelCreatePayload) -> FuelRecord:
        try:
            car = Car.objects.get(id=payload.car_id, is_active=True)
        except Car.DoesNotExist as exc:
            raise ValueError("Автомобиль не найден или не активен") from exc

        try:
            user = User.objects.get(id=payload.user_id, is_active=True)
        except User.DoesNotExist as exc:
            raise ValueError("Пользователь не найден или не активен") from exc

        filled_at = payload.filled_at or timezone.now()
        return FuelRecord.objects.create_fuel_record(
            car=car,
            employee=user,
            liters=payload.liters,
            fuel_type=payload.fuel_type,
            source=payload.source,
            filled_at=filled_at,
            notes=payload.notes,
        )

    @staticmethod
    def get_recent_records(limit: int = 30) -> QuerySet[FuelRecord]:
        safe_limit = max(1, min(limit, 100))
        queryset = FuelRecord.objects.with_related_data()
        queryset = queryset.order_by("-filled_at")
        return queryset[:safe_limit]
