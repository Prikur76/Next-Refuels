# mypy: ignore-missing-imports
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.utils import timezone

from core.models import Car, FuelRecord
from core.services.access_service import ROLE_ADMIN, ROLE_FUELER, ROLE_MANAGER

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


@dataclass(frozen=True)
class FuelPatchPayload:
    car_id: int | None = None
    liters: Any | None = None
    fuel_type: str | None = None
    source: str | None = None
    notes: str | None = None
    filled_at: datetime | None = None
    reporting_status: str | None = None


class FuelService:
    """Единая бизнес-логика ввода и выборок по заправкам."""

    @staticmethod
    def filled_at_from_api_value(fa: datetime) -> datetime:
        """Переводит filled_at из API в aware-UTC для ORM.

        Наивная дата/время — календарные в settings.TIME_ZONE. Значение со
        смещением или Z — абсолютный момент (обратная совместимость).
        """
        if timezone.is_naive(fa):
            return timezone.make_aware(fa, ZoneInfo(settings.TIME_ZONE))
        return fa

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
    def _is_admin(user: Any) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if bool(getattr(user, "is_superuser", False)):
            return True
        return user.groups.filter(name=ROLE_ADMIN).exists()

    @staticmethod
    def _is_manager(user: Any) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return user.groups.filter(name=ROLE_MANAGER).exists()

    @staticmethod
    def _is_fueler(user: Any) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return user.groups.filter(name=ROLE_FUELER).exists()

    @staticmethod
    def parse_client_timezone(raw: str | None) -> Any:
        text = (raw or "").strip()
        if not text:
            return timezone.get_current_timezone()
        try:
            return ZoneInfo(text)
        except Exception as exc:
            raise ValueError(
                "Некорректный часовой пояс. Укажите IANA, например "
                "Europe/Moscow"
            ) from exc

    @staticmethod
    def fueler_local_cutoff_utc(client_tz: Any) -> datetime:
        now_local = timezone.now().astimezone(client_tz)
        cutoff_local = now_local - timedelta(hours=24)
        return cutoff_local.astimezone(dt_timezone.utc)

    @staticmethod
    def is_within_fueler_edit_window(
        record: FuelRecord, client_tz: Any
    ) -> bool:
        filled = record.filled_at
        if timezone.is_naive(filled):
            filled = timezone.make_aware(
                filled, timezone.get_current_timezone()
            )
        filled_local = filled.astimezone(client_tz)
        now_local = timezone.now().astimezone(client_tz)
        cutoff_local = now_local - timedelta(hours=24)
        return (
            filled_local >= cutoff_local
            and filled_local <= now_local
        )

    @staticmethod
    def query_my_active_fuel_records(
        user: Any,
        client_tz: Any,
    ) -> QuerySet[FuelRecord]:
        cutoff = FuelService.fueler_local_cutoff_utc(client_tz)
        now_utc = timezone.now()
        return (
            FuelRecord.objects.active_for_reports()
            .filter(
                employee_id=user.id,
                filled_at__gte=cutoff,
                filled_at__lte=now_utc,
            )
            .select_related(
                "car", "employee", "car__region", "historical_region"
            )
            .order_by("-filled_at", "-id")
        )

    @staticmethod
    def user_has_my_editable_fuel_records(user: Any, client_tz: Any) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if not FuelService.user_has_any_group(user, ALLOWED_INPUT_GROUPS):
            return False
        return FuelService.query_my_active_fuel_records(
            user,
            client_tz,
        ).exists()

    @staticmethod
    def normalized_reports_region_id(
        user: Any,
        region_id: int | None,
    ) -> int | None:
        """Регион отчётов: для менеджера — свой; для админа — из запроса."""
        if FuelService._is_admin(user):
            return region_id
        if FuelService._is_manager(user):
            return user.region_id
        return region_id

    @staticmethod
    def ensure_actor_can_patch_fuel_record(
        actor: Any,
        record: FuelRecord,
        *,
        client_tz: Any,
        patch: FuelPatchPayload,
    ) -> None:
        if FuelService._is_admin(actor):
            return
        if FuelService._is_manager(actor):
            rid = getattr(actor, "region_id", None)
            if not rid:
                raise PermissionDenied(
                    "У менеджера не задан регион для операций с заправками"
                )
            if record.historical_region_id != rid:
                raise PermissionDenied(
                    "Менеджер может править только заправки своего региона"
                )
            return
        if FuelService._is_fueler(actor):
            if record.employee_id != actor.id:
                raise PermissionDenied("Можно править только свои заправки")
            if (
                patch.reporting_status is not None
                and patch.reporting_status
                == FuelRecord.ReportingStatus.ACTIVE
            ):
                raise PermissionDenied("Недостаточно прав")
            if record.reporting_status != FuelRecord.ReportingStatus.ACTIVE:
                raise PermissionDenied("Запись недоступна для правок")
            if not FuelService.is_within_fueler_edit_window(
                record,
                client_tz,
            ):
                raise PermissionDenied(
                    "Правка доступна только в течение 24 часов с момента "
                    "заправки (локальное время)"
                )
            return
        raise PermissionDenied("Недостаточно прав для изменения заправки")

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

        if payload.filled_at is None:
            filled_at = timezone.now()
        else:
            filled_at = FuelService.filled_at_from_api_value(
                payload.filled_at,
            )
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
    def apply_fuel_record_patch(
        actor: Any,
        record: FuelRecord,
        patch: FuelPatchPayload,
        *,
        client_tz: Any,
    ) -> FuelRecord:
        FuelService.ensure_actor_can_patch_fuel_record(
            actor,
            record,
            client_tz=client_tz,
            patch=patch,
        )
        if patch.car_id is not None:
            try:
                car = Car.objects.get(id=patch.car_id, is_active=True)
            except Car.DoesNotExist as exc:
                raise ValueError(
                    "Автомобиль не найден или не активен"
                ) from exc
            record.car = car
            record.historical_region = car.region
            record.historical_department = car.department
        if patch.liters is not None:
            record.liters = FuelService.normalize_liters(patch.liters)
        if patch.fuel_type is not None:
            if patch.fuel_type not in dict(FuelRecord.FuelType.choices):
                raise ValueError("Некорректный тип топлива")
            record.fuel_type = patch.fuel_type
        if patch.source is not None:
            if patch.source not in dict(FuelRecord.SourceFuel.choices):
                raise ValueError("Некорректный способ заправки")
            record.source = patch.source
        if patch.notes is not None:
            record.notes = patch.notes
        if patch.filled_at is not None:
            record.filled_at = FuelService.filled_at_from_api_value(
                patch.filled_at,
            )
        if patch.reporting_status is not None:
            valid = {c for c, _ in FuelRecord.ReportingStatus.choices}
            if patch.reporting_status not in valid:
                raise ValueError("Некорректный статус учёта")
            record.reporting_status = patch.reporting_status
        record.save()
        return record

    @staticmethod
    def get_recent_records(limit: int = 30) -> QuerySet[FuelRecord]:
        safe_limit = max(1, min(limit, 100))
        queryset = FuelRecord.objects.active_for_reports().with_related_data()
        queryset = queryset.order_by("-filled_at", "-id")
        return queryset[:safe_limit]
