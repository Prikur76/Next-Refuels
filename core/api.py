from __future__ import annotations

import base64
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce, Concat, TruncDay
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from ninja import Body, Field, NinjaAPI, Path, Query, Schema
from ninja.errors import HttpError

from core.models import Car, FuelRecord, Region, SystemLog, User
from core.schemas import (
    AnalyticsByDayPointOut,
    AnalyticsByDayRegionPointOut,
    AnalyticsCarBreakdownOut,
    AnalyticsDataOut,
    AnalyticsEmployeeBreakdownOut,
    AnalyticsRecentRecordOut,
    AnalyticsRefuelChannelSliceOut,
    AnalyticsRefuelSourceSliceOut,
)
from core.services.access_service import (
    AccessCreatePayload,
    AccessUpdatePayload,
    UserAccessService,
)
from core.services.fuel_service import (
    FuelCreatePayload,
    FuelPatchPayload,
    FuelService,
)
from core.services.telegram_link_service import TelegramLinkService
from core.utils.logging import log_access_event, log_action

_API_DESCRIPTION = """
REST API веб-клиента Next-Refuels (django-ninja, OpenAPI 3).

**Авторизация:** cookie-сессия Django. Перед мутациями из браузера вызовите
`GET /api/v1/auth/csrf`, затем передавайте CSRF-токен (заголовок или форма, см.
настройки Django).

**Часовой пояс:** заголовок `X-Client-Timezone` (IANA, например
`Europe/Moscow`) учитывается в операциях заправщика; пустое значение —
часовой пояс сервера (`TIME_ZONE`).
""".strip()

_OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": (
            "CSRF, профиль, привязка Telegram, первичная смена пароля"
        ),
    },
    {
        "name": "fuel",
        "description": "Поиск автомобилей и записи заправок",
    },
    {
        "name": "reports",
        "description": "Сводки, журнал, фильтры, журнал событий доступа",
    },
    {
        "name": "access",
        "description": "Управление пользователями, ролями и scope (RBAC)",
    },
    {
        "name": "analytics",
        "description": "Дашборд аналитики и выгрузка в Excel",
    },
]


def _user_groups_with_superuser(user) -> list[str]:
    groups = list(user.groups.values_list("name", flat=True))
    if (
        bool(getattr(user, "is_superuser", False))
        and "Администратор" not in groups
    ):
        groups.append("Администратор")
    return groups


class CsrfOkOut(Schema):
    """Ответ endpoint выставления CSRF-cookie."""

    ok: bool = Field(..., description="Всегда true при успешном ответе")


class UserMeOut(Schema):
    """Профиль текущего пользователя (SPA / бот-навигация)."""

    id: int = Field(..., description="ID пользователя")
    username: str = Field(..., description="Логин")
    full_name: str = Field(..., description="ФИО или username")
    groups: list[str] = Field(..., description="Имена групп Django (роли)")
    auth_provider: str = Field(
        ..., description="Провайдер входа (например local)"
    )
    mfa_policy_enabled: bool = Field(..., description="Политика MFA включена")
    must_change_password: bool = Field(
        ...,
        description="Требуется смена пароля при первом входе",
    )
    telegram_linked: bool = Field(
        ...,
        description="True, если к учётной записи привязан Telegram",
    )
    has_my_editable_fuel_records: bool = Field(
        False,
        description=(
            "Есть ли у пользователя с правом ввода заправок свои записи в "
            "окне 24ч (локальное время клиента)"
        ),
    )
    region_id: Optional[int] = Field(None, description="Регион пользователя")
    app_timezone: str = Field(
        ...,
        description="IANA-пояс приложения (настройка сервера)",
    )


class TelegramLinkCodeOut(Schema):
    """Одноразовый код и подсказки для привязки Telegram."""

    code: str = Field(..., description="Токен для /start в боте")
    expires_at: str = Field(..., description="Срок действия (ISO 8601)")
    ttl_minutes: int = Field(..., description="TTL кода в минутах")
    bot_link_with_start: str = Field(
        ...,
        description="Ссылка t.me с deep-link",
    )
    share_message: str = Field(
        ..., description="Текст инструкции для пользователя"
    )


class CarOut(Schema):
    """Активный автомобиль для выбора при заправке."""

    id: int
    state_number: str = Field(..., description="Госномер")
    model: str = Field(..., description="Модель")
    code: str = Field(..., description="Внутренний код из 1С")
    region_name: Optional[str] = Field(None, description="Регион ТС")


class FuelRecordIn(Schema):
    """Тело создания записи заправки."""

    car_id: int = Field(..., description="ID автомобиля")
    liters: Decimal = Field(..., description="Объём в литрах")
    fuel_type: str = Field(
        ...,
        description="GASOLINE — бензин, DIESEL — дизель",
        pattern="^(GASOLINE|DIESEL)$",
    )
    source: str = Field(
        ...,
        description="CARD — карта, TGBOT — бот, TRUCK — топливозаправщик",
        pattern="^(CARD|TGBOT|TRUCK)$",
    )
    notes: str = Field("", description="Комментарий")


class FuelRecordOut(Schema):
    """Запись заправки в ответах API."""

    id: int
    car_id: int
    car_state_number: str
    car_is_fuel_tanker: bool = Field(
        False,
        description="Признак топливозаправщика у ТС",
    )
    liters: Decimal
    fuel_type: str
    source: str
    filled_at: str = Field(..., description="Дата-время заправки (ISO 8601)")
    employee_name: str
    region_name: Optional[str] = Field(
        None,
        description="Исторический регион записи",
    )
    historical_department: str = Field(
        "",
        description="Подразделение (на момент заправки)",
    )
    reporting_status: str = Field(
        "ACTIVE",
        description="ACTIVE или EXCLUDED_DELETION",
    )
    notes: str = ""
    created_at: str = Field(..., description="Создано (ISO 8601)")
    updated_at: str = Field(..., description="Обновлено (ISO 8601)")


class FuelRecordPatchIn(Schema):
    """Частичное обновление заправки; передайте только изменяемые поля."""

    car_id: Optional[int] = Field(None, description="ID автомобиля")
    liters: Optional[Decimal] = Field(None, description="Объём, л")
    fuel_type: Optional[str] = Field(None, description="GASOLINE или DIESEL")
    source: Optional[str] = Field(None, description="CARD, TGBOT или TRUCK")
    notes: Optional[str] = Field(None, description="Комментарий")
    filled_at: Optional[datetime] = Field(
        None,
        description="Дата-время заправки",
    )
    reporting_status: Optional[str] = Field(
        None,
        description="ACTIVE или EXCLUDED_DELETION",
    )


class SummaryOut(Schema):
    """Сводка по отфильтрованным записям."""

    total_records: int = Field(..., description="Количество записей")
    total_liters: float = Field(..., description="Сумма литров")
    avg_liters: float = Field(..., description="Средний объём на запись")


class ReportsFiltersOut(Schema):
    """Значения для выпадающих фильтров отчёта."""

    employees: list[str] = Field(
        ..., description="Сотрудники (отображаемые имена)"
    )
    regions: list[str] = Field(..., description="Названия регионов")


class RecordsPageOut(Schema):
    """Страница журнала заправок."""

    items: list[FuelRecordOut] = Field(..., description="Строки страницы")
    total: int = Field(
        ...,
        description="Всего записей (при пагинации без cursor)",
    )
    has_next: bool = Field(False, description="Есть следующая страница")
    next_cursor: Optional[str] = Field(
        None,
        description="Курсор для следующего запроса (base64)",
    )


class AccessUserOut(Schema):
    """Пользователь в разделе управления доступом."""

    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    phone: str
    is_active: bool
    region_id: Optional[int]
    region_name: Optional[str]
    groups: list[str] = Field(..., description="Текущие роли")


class AccessUserCreateIn(Schema):
    """Создание пользователя с ролью заправщика."""

    email: str = Field(..., min_length=1, description="Email (база логина)")
    first_name: str = Field("", description="Имя")
    last_name: str = Field("", description="Фамилия")
    phone: str = Field("", description="Телефон")
    password: Optional[str] = Field(
        None,
        description="Пароль; иначе будет сгенерирован",
    )
    region_id: Optional[int] = Field(None, description="Регион (scope)")
    activate: bool = Field(True, description="Сразу активен")


class AccessStatusPatchIn(Schema):
    """Включение или отключение учётной записи."""

    is_active: bool = Field(..., description="Активен ли пользователь")


class AccessPasswordOut(Schema):
    """Результат сброса или смены пароля."""

    id: int
    username: str
    temporary_password: Optional[str] = Field(
        None,
        description="Временный пароль (если генерировался)",
    )


class AccessUserCreateOut(Schema):
    """Результат создания пользователя."""

    id: int
    username: str
    temporary_password: Optional[str] = Field(
        None,
        description="Если пароль был сгенерирован",
    )


class AccessPasswordPatchIn(Schema):
    """Установка пароля вручную или генерация временного."""

    password: Optional[str] = Field(None, description="Новый пароль")
    generate_temporary: bool = Field(
        False,
        description="Сгенерировать временный пароль",
    )


class PasswordSetupIn(Schema):
    """Первая смена пароля после входа с флагом must_change_password."""

    password: Optional[str] = Field(
        None, description="Новый пароль (≥8 символов)"
    )
    generate: bool = Field(
        False,
        description="Сгенерировать пароль вместо ввода",
    )


class PasswordSetupOut(Schema):
    """Состояние после первичной смены пароля."""

    must_change_password: bool
    generated_password: Optional[str] = Field(
        None,
        description="Если запрошена генерация",
    )


class AccessLogOut(Schema):
    """Запись журнала событий доступа."""

    id: int
    actor_username: str
    action: str = Field(..., description="Код события (префикс access_)")
    details: str
    created_at: str = Field(..., description="Время события (ISO 8601)")


class AccessRolePatchIn(Schema):
    """Назначение одной из ролей доступа."""

    role: str = Field(
        ...,
        description="Заправщик, Менеджер или Администратор",
        pattern="^(Заправщик|Менеджер|Администратор)$",
    )


class AccessScopePatchIn(Schema):
    """Изменение регионального scope пользователя."""

    region_id: Optional[int] = Field(
        None,
        description="ID региона; null — по правилам сервиса",
    )


class AccessUserProfilePatchIn(Schema):
    """Частичное обновление профиля сотрудника."""

    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    region_id: Optional[int] = None


class RegionOut(Schema):
    """Регион для форм управления доступом."""

    id: int
    name: str


api = NinjaAPI(
    title="Next-Refuels API",
    version="1.0.0",
    urls_namespace="api",
    description=_API_DESCRIPTION,
    openapi_extra={"tags": _OPENAPI_TAGS},
)


def _ensure_auth(request: HttpRequest):
    if not request.user.is_authenticated:
        raise HttpError(401, "Требуется авторизация")


def _client_timezone_from_request(request: HttpRequest):
    raw = request.META.get("HTTP_X_CLIENT_TIMEZONE")
    try:
        return FuelService.parse_client_timezone(raw)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc


def _record_to_schema(record: FuelRecord) -> FuelRecordOut:
    car_state_number = record.car.state_number if record.car else ""
    car_is_fuel_tanker = bool(record.car and record.car.is_fuel_tanker)
    employee_name = (
        record.employee.get_full_name() if record.employee else "Неизвестно"
    )
    region_name = None
    if record.historical_region:
        region_name = record.historical_region.name
    elif record.car and record.car.region:
        region_name = record.car.region.name
    department = (record.historical_department or "").strip()
    if not department and record.car:
        department = (record.car.department or "").strip()
    return FuelRecordOut(
        id=record.id,
        car_id=record.car_id,
        car_state_number=car_state_number,
        car_is_fuel_tanker=car_is_fuel_tanker,
        liters=record.liters,
        fuel_type=record.fuel_type,
        source=record.source,
        filled_at=record.filled_at.isoformat(),
        employee_name=employee_name,
        region_name=region_name,
        historical_department=department,
        reporting_status=str(record.reporting_status),
        notes=record.notes or "",
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


def _apply_filled_at_date_range(
    qs,
    from_date: Optional[date],
    to_date: Optional[date],
):
    """Применяет диапазонный фильтр по filled_at без __date."""
    if from_date:
        from_dt = timezone.make_aware(datetime.combine(from_date, time.min))
        qs = qs.filter(filled_at__gte=from_dt)
    if to_date:
        to_dt = timezone.make_aware(
            datetime.combine(to_date + timedelta(days=1), time.min)
        )
        qs = qs.filter(filled_at__lt=to_dt)
    return qs


def _apply_reports_filters(
    qs,
    *,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    region_id: Optional[int] = None,
    region: Optional[str] = None,
    employee: Optional[str] = None,
    car_id: Optional[int] = None,
    car_state_number: Optional[str] = None,
    source: Optional[str] = None,
):
    """Применяет единый набор фильтров для отчетов."""
    qs = _apply_filled_at_date_range(qs, from_date, to_date)
    if region_id:
        qs = qs.filter(historical_region_id=region_id)
    if region:
        qs = qs.filter(historical_region__name__icontains=region.strip())
    if employee:
        employee_value = employee.strip()
        qs = qs.annotate(
            employee_full_name=Concat(
                Coalesce("employee__first_name", Value("")),
                Value(" "),
                Coalesce("employee__last_name", Value("")),
            ),
        ).filter(
            Q(employee__username__icontains=employee_value)
            | Q(employee__first_name__icontains=employee_value)
            | Q(employee__last_name__icontains=employee_value)
            | Q(employee_full_name__icontains=employee_value)
        )
    if car_id:
        qs = qs.filter(car_id=car_id)
    if car_state_number:
        car_state_number_value = car_state_number.strip()
        if car_state_number_value:
            qs = qs.filter(car__state_number__icontains=car_state_number_value)
    if source:
        qs = qs.filter(source=source)
    return qs


def _encode_records_cursor(filled_at: datetime, record_id: int) -> str:
    raw_value = f"{filled_at.isoformat()}|{record_id}"
    return base64.urlsafe_b64encode(raw_value.encode("utf-8")).decode("ascii")


def _decode_records_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        raw_value = base64.urlsafe_b64decode(cursor.encode("ascii")).decode(
            "utf-8"
        )
        filled_at_raw, record_id_raw = raw_value.split("|", maxsplit=1)
        return datetime.fromisoformat(filled_at_raw), int(record_id_raw)
    except Exception as exc:
        raise HttpError(400, "Некорректный cursor") from exc


def _access_user_to_schema(user) -> AccessUserOut:
    return AccessUserOut(
        id=user.id,
        username=user.username,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        email=user.email or "",
        phone=str(user.phone or ""),
        is_active=user.is_active,
        region_id=user.region_id,
        region_name=user.region.name if user.region else None,
        groups=_user_groups_with_superuser(user),
    )


@api.get(
    "/auth/csrf",
    response=CsrfOkOut,
    tags=["auth"],
    summary="Получить CSRF-cookie",
    description=(
        "Выставляет cookie для защиты от CSRF. Вызовите перед первым "
        "изменяющим запросом из SPA."
    ),
)
@ensure_csrf_cookie
def auth_csrf(request: HttpRequest):
    return JsonResponse({"ok": True})


@api.get(
    "/auth/me",
    response=UserMeOut,
    tags=["auth"],
    summary="Текущий пользователь",
    description="Профиль, роли, флаги MFA и привязки Telegram.",
)
def auth_me(
    request: HttpRequest,
    client_tz: Optional[str] = Query(
        None,
        description=(
            "Часовой пояс клиента (IANA) для расчёта "
            "has_my_editable_fuel_records; некорректное значение игнорируется"
        ),
    ),
):
    _ensure_auth(request)
    groups = _user_groups_with_superuser(request.user)
    try:
        tz_val = FuelService.parse_client_timezone(client_tz)
    except ValueError:
        tz_val = timezone.get_current_timezone()
    has_mine = FuelService.user_has_my_editable_fuel_records(
        request.user,
        tz_val,
    )
    return UserMeOut(
        id=request.user.id,
        username=request.user.username,
        full_name=request.user.get_full_name() or request.user.username,
        groups=groups,
        auth_provider=settings.AUTH_PROVIDER,
        mfa_policy_enabled=settings.MFA_POLICY_ENABLED,
        must_change_password=request.user.must_change_password,
        telegram_linked=bool(request.user.telegram_id),
        has_my_editable_fuel_records=has_mine,
        region_id=request.user.region_id,
        app_timezone=settings.TIME_ZONE,
    )


@api.post(
    "/auth/telegram/link-code",
    response=TelegramLinkCodeOut,
    tags=["auth"],
    summary="Код привязки Telegram",
    description=(
        "Одноразовый токен для команды /start в боте. "
        "Нужны права ввода заправок."
    ),
)
def create_telegram_link_code(request: HttpRequest):
    _ensure_auth(request)
    FuelService.ensure_input_access(request.user)

    ttl_minutes = settings.TELEGRAM.get("LINK_CODE_TTL_MINUTES", 10)
    token = TelegramLinkService.create_link_token_for_user(
        user=request.user,
        ttl_minutes=ttl_minutes,
    )
    log_action(
        user=request.user,
        action="telegram_link_code_issued",
        details="Сгенерирован одноразовый код привязки Telegram",
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    bot_username = settings.TELEGRAM.get("BOT_USERNAME", "").strip()
    bot_link = (
        f"https://t.me/{bot_username}?start={token.code}"
        if bot_username
        else ""
    )
    command_text = f"/start {token.code}"
    share_message_lines = [
        "Инструкция по подключению Telegram-бота Next-Refuels:",
        f"1) Откройте бот: https://t.me/{bot_username}"
        if bot_username
        else "1) Откройте наш Telegram-бот Next-Refuels.",
        (
            f"2) Нажмите ссылку автозапуска: {bot_link}"
            if bot_link
            else f"2) Отправьте команду: {command_text}"
        ),
        f"3) Если нужно, отправьте вручную: {command_text}",
        f"Код действует до: {token.expires_at.isoformat()}",
    ]
    share_message = "\n".join(share_message_lines)

    return TelegramLinkCodeOut(
        code=token.code,
        expires_at=token.expires_at.isoformat(),
        ttl_minutes=ttl_minutes,
        bot_link_with_start=bot_link,
        share_message=share_message,
    )


@api.post(
    "/auth/password/setup",
    response=PasswordSetupOut,
    tags=["auth"],
    summary="Первичная смена пароля",
    description=(
        "Доступно только при must_change_password=true у пользователя."
    ),
)
def auth_password_setup(request: HttpRequest, payload: PasswordSetupIn):
    _ensure_auth(request)
    if not request.user.must_change_password:
        raise HttpError(
            400,
            "Смена пароля при первом входе не требуется",
        )

    password_value = (payload.password or "").strip()
    if payload.generate:
        next_password = secrets.token_urlsafe(12)
        generated_password = next_password
    else:
        if len(password_value) < 8:
            raise HttpError(
                400,
                "Пароль должен содержать минимум 8 символов",
            )
        next_password = password_value
        generated_password = None

    request.user.set_password(next_password)
    request.user.must_change_password = False
    request.user.save(update_fields=["password", "must_change_password"])
    update_session_auth_hash(request, request.user)
    return PasswordSetupOut(
        must_change_password=False,
        generated_password=generated_password,
    )


@api.get(
    "/cars",
    response=list[CarOut],
    tags=["fuel"],
    summary="Поиск автомобилей",
    description="Активные ТС, доступные для заправки.",
)
def list_cars(
    request: HttpRequest,
    query: str = Query("", description="Подстрока госномера"),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Максимум записей в ответе",
    ),
):
    _ensure_auth(request)
    FuelService.ensure_input_access(request.user)
    safe_limit = max(1, min(limit, 100))
    qs = Car.objects.available_for_refuel().order_by("state_number")
    if query:
        qs = qs.search_by_state_number(query)
    return [
        CarOut(
            id=car.id,
            state_number=car.state_number,
            model=car.model,
            code=car.code,
            region_name=car.region.name if car.region else None,
        )
        for car in qs[:safe_limit]
    ]


@api.post(
    "/fuel-records",
    response=FuelRecordOut,
    tags=["fuel"],
    summary="Создать заправку",
    description="Новая запись от текущего пользователя.",
)
def create_fuel_record(request: HttpRequest, payload: FuelRecordIn):
    _ensure_auth(request)
    FuelService.ensure_input_access(request.user)
    try:
        liters = FuelService.normalize_liters(payload.liters)
    except ValueError as exc:
        # По требованиям тестов:
        # - некорректный формат литров -> 422
        # - значения вне диапазона -> 400
        msg = str(exc)
        status = 422 if "Некорректный формат литров" in msg else 400
        raise HttpError(status, msg) from exc
    try:
        record = FuelService.create_fuel_record(
            FuelCreatePayload(
                car_id=payload.car_id,
                user_id=request.user.id,
                liters=liters,
                fuel_type=payload.fuel_type,
                source=payload.source,
                notes=payload.notes,
            )
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    return _record_to_schema(record)


@api.get(
    "/fuel-records/recent",
    response=list[FuelRecordOut],
    tags=["fuel"],
    summary="Последние заправки",
    description="Глобальная лента последних записей (права ввода).",
)
def recent_fuel_records(
    request: HttpRequest,
    limit: int = Query(30, ge=1, le=500, description="Число записей"),
):
    _ensure_auth(request)
    FuelService.ensure_input_access(request.user)
    records = FuelService.get_recent_records(limit=limit)
    return [_record_to_schema(record) for record in records]


@api.get(
    "/fuel-records/mine",
    response=list[FuelRecordOut],
    tags=["fuel"],
    summary="Мои заправки (редактируемое окно)",
    description=(
        "Свои записи в скользящем 24-часовом окне (локальное время клиента). "
        "Доступно ролям с правом ввода заправок. Нужен заголовок "
        "X-Client-Timezone (см. описание API)."
    ),
)
def my_fuel_records(request: HttpRequest):
    _ensure_auth(request)
    try:
        FuelService.ensure_input_access(request.user)
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc
    client_tz = _client_timezone_from_request(request)
    qs = FuelService.query_my_active_fuel_records(request.user, client_tz)
    return [_record_to_schema(rec) for rec in qs]


@api.patch(
    "/fuel-records/{record_id}",
    response=FuelRecordOut,
    tags=["fuel"],
    summary="Обновить заправку",
    description=(
        "Частичное обновление; нужен заголовок X-Client-Timezone "
        "для правил заправщика."
    ),
)
def patch_fuel_record(
    request: HttpRequest,
    record_id: int = Path(..., description="ID записи заправки"),
    payload: FuelRecordPatchIn = Body(...),
):
    _ensure_auth(request)
    FuelService.ensure_input_access(request.user)
    dumped = payload.model_dump(exclude_unset=True)
    if not dumped:
        raise HttpError(400, "Нет полей для обновления")
    client_tz = _client_timezone_from_request(request)
    try:
        record = FuelRecord.objects.select_related(
            "car", "employee", "car__region", "historical_region"
        ).get(pk=record_id)
    except FuelRecord.DoesNotExist:
        raise HttpError(404, "Запись не найдена") from None
    patch = FuelPatchPayload(
        car_id=dumped["car_id"] if "car_id" in dumped else None,
        liters=dumped["liters"] if "liters" in dumped else None,
        fuel_type=dumped["fuel_type"] if "fuel_type" in dumped else None,
        source=dumped["source"] if "source" in dumped else None,
        notes=dumped["notes"] if "notes" in dumped else None,
        filled_at=dumped["filled_at"] if "filled_at" in dumped else None,
        reporting_status=(
            dumped["reporting_status"]
            if "reporting_status" in dumped
            else None
        ),
    )
    try:
        FuelService.apply_fuel_record_patch(
            request.user,
            record,
            patch,
            client_tz=client_tz,
        )
        record.refresh_from_db()
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc
    except ValueError as exc:
        msg = str(exc)
        status = 422 if "Некорректный формат литров" in msg else 400
        raise HttpError(status, msg) from exc
    return _record_to_schema(record)


@api.get(
    "/reports/summary",
    response=SummaryOut,
    tags=["reports"],
    summary="Сводка по заправкам",
    description=(
        "Агрегаты по отфильтрованным записям. Для менеджеров region_id "
        "ограничивается scope."
    ),
)
def reports_summary(
    request: HttpRequest,
    from_date: Optional[date] = Query(
        None,
        description="Начало периода (дата заправки, включительно)",
    ),
    to_date: Optional[date] = Query(
        None,
        description="Конец периода (дата заправки, включительно)",
    ),
    region_id: Optional[int] = Query(
        None,
        description="Исторический регион (ID)",
    ),
    region: Optional[str] = Query(
        None,
        description="Подстрока в названии региона",
    ),
    employee: Optional[str] = Query(
        None,
        description="Подстрока ФИО или логина сотрудника",
    ),
    car_id: Optional[int] = Query(None, description="ID автомобиля"),
    car_state_number: Optional[str] = Query(
        None,
        description="Подстрока госномера",
    ),
    source: Optional[str] = Query(
        None,
        description="Способ: CARD, TGBOT или TRUCK",
    ),
    include_excluded: bool = Query(
        False,
        description=(
            "Включать записи со статусом EXCLUDED_DELETION (на удаление). "
            "По умолчанию false."
        ),
    ),
):
    _ensure_auth(request)
    FuelService.ensure_reports_access(request.user)
    rid = FuelService.normalized_reports_region_id(
        request.user,
        region_id,
    )
    qs = FuelRecord.objects.with_related_data()
    if not include_excluded:
        qs = qs.active_for_reports()
    qs = _apply_reports_filters(
        qs,
        from_date=from_date,
        to_date=to_date,
        region_id=rid,
        region=region,
        employee=employee,
        car_id=car_id,
        car_state_number=car_state_number,
        source=source,
    )
    stats = qs.fuel_statistics()
    return SummaryOut(
        total_records=stats["total_records"] or 0,
        total_liters=float(stats["total_liters"] or 0),
        avg_liters=float(stats["avg_liters"] or 0),
    )


@api.get(
    "/reports/filters",
    response=ReportsFiltersOut,
    tags=["reports"],
    summary="Значения для фильтров отчёта",
    description="Списки сотрудников и регионов в рамках выборки.",
)
def reports_filters(
    request: HttpRequest,
    from_date: Optional[date] = Query(
        None,
        description="Начало периода (дата заправки)",
    ),
    to_date: Optional[date] = Query(
        None,
        description="Конец периода (дата заправки)",
    ),
    source: Optional[str] = Query(
        None,
        description="Ограничить выборку способом заправки",
    ),
    include_excluded: bool = Query(
        False,
        description=(
            "Включать записи со статусом EXCLUDED_DELETION (на удаление). "
            "По умолчанию false."
        ),
    ),
):
    _ensure_auth(request)
    FuelService.ensure_reports_access(request.user)

    qs = FuelRecord.objects.all()
    if not include_excluded:
        qs = qs.active_for_reports()
    qs = _apply_filled_at_date_range(qs, from_date, to_date)
    if source:
        qs = qs.filter(source=source)

    employees_set: set[str] = set()
    employee_ids = list(
        qs.filter(employee_id__isnull=False)
        .values_list("employee_id", flat=True)
        .distinct()
    )
    if employee_ids:
        for first_name, last_name, username in User.objects.filter(
            pk__in=employee_ids,
        ).values_list("first_name", "last_name", "username"):
            full_name = " ".join(
                part.strip()
                for part in [first_name or "", last_name or ""]
                if part and part.strip()
            ).strip()
            if full_name:
                employees_set.add(full_name)
            elif username:
                employees_set.add(username)

    historical_region_ids = list(
        qs.exclude(historical_region_id__isnull=True)
        .values_list("historical_region_id", flat=True)
        .distinct()
    )
    car_region_ids = list(
        qs.filter(car__region_id__isnull=False)
        .values_list("car__region_id", flat=True)
        .distinct()
    )
    region_pk_set = set(historical_region_ids) | set(car_region_ids)
    regions_set: set[str] = set()
    if region_pk_set:
        for name in Region.objects.filter(pk__in=region_pk_set).values_list(
            "name",
            flat=True,
        ):
            cleaned = (name or "").strip()
            if cleaned:
                regions_set.add(cleaned)

    return ReportsFiltersOut(
        employees=sorted(employees_set),
        regions=sorted(regions_set),
    )


@api.get(
    "/reports/records",
    response=RecordsPageOut,
    tags=["reports"],
    summary="Журнал заправок",
    description=(
        "Пагинация: либо offset/limit (total заполнен), либо cursor "
        "(ключевой набор после курсора; total может быть 0)."
    ),
)
def reports_records(
    request: HttpRequest,
    from_date: Optional[date] = Query(
        None,
        description="Начало периода (дата заправки)",
    ),
    to_date: Optional[date] = Query(
        None,
        description="Конец периода (дата заправки)",
    ),
    region_id: Optional[int] = Query(None, description="Исторический регион"),
    region: Optional[str] = Query(None, description="Подстрока региона"),
    employee: Optional[str] = Query(None, description="Сотрудник"),
    car_id: Optional[int] = Query(None, description="ID автомобиля"),
    car_state_number: Optional[str] = Query(
        None,
        description="Подстрока госномера",
    ),
    source: Optional[str] = Query(None, description="CARD, TGBOT или TRUCK"),
    cursor: Optional[str] = Query(
        None,
        description="Курсор из предыдущего ответа (next_cursor)",
    ),
    offset: int = Query(0, ge=0, description="Смещение (без cursor)"),
    limit: int = Query(50, ge=1, le=200, description="Размер страницы"),
    include_excluded: bool = Query(
        False,
        description=(
            "Включать записи со статусом EXCLUDED_DELETION (на удаление). "
            "По умолчанию false."
        ),
    ),
):
    _ensure_auth(request)
    FuelService.ensure_reports_access(request.user)

    rid = FuelService.normalized_reports_region_id(
        request.user,
        region_id,
    )
    qs = FuelRecord.objects.with_related_data()
    if not include_excluded:
        qs = qs.active_for_reports()
    qs = qs.order_by("-filled_at", "-id")
    qs = _apply_reports_filters(
        qs,
        from_date=from_date,
        to_date=to_date,
        region_id=rid,
        region=region,
        employee=employee,
        car_id=car_id,
        car_state_number=car_state_number,
        source=source,
    )

    safe_limit = max(1, min(limit, 200))
    if cursor:
        cursor_filled_at, cursor_id = _decode_records_cursor(cursor)
        qs = qs.filter(
            Q(filled_at__lt=cursor_filled_at)
            | Q(filled_at=cursor_filled_at, id__lt=cursor_id)
        )
        chunk = list(qs[: safe_limit + 1])
        has_next = len(chunk) > safe_limit
        page_records = chunk[:safe_limit]
        next_cursor = None
        if has_next and page_records:
            last = page_records[-1]
            next_cursor = _encode_records_cursor(last.filled_at, last.id)
        items = [_record_to_schema(item) for item in page_records]
        return RecordsPageOut(
            items=items,
            total=0,
            has_next=has_next,
            next_cursor=next_cursor,
        )

    total = qs.count()
    safe_offset = max(0, offset)
    chunk = list(qs[safe_offset : safe_offset + safe_limit + 1])
    has_next = len(chunk) > safe_limit
    page_records = chunk[:safe_limit]
    next_cursor = None
    if has_next and page_records:
        last = page_records[-1]
        next_cursor = _encode_records_cursor(last.filled_at, last.id)
    items = [_record_to_schema(item) for item in page_records]
    return RecordsPageOut(
        items=items,
        total=total,
        has_next=has_next,
        next_cursor=next_cursor,
    )


@api.get(
    "/access/users",
    response=list[AccessUserOut],
    tags=["access"],
    summary="Список пользователей доступа",
    description="Учитывается scoped RBAC актора.",
)
def access_users(
    request: HttpRequest,
    show_all: bool = Query(
        False,
        description="Показать в том числе неактивных",
    ),
):
    _ensure_auth(request)
    users = UserAccessService.list_users_for_actor(
        request.user,
        active_only=not show_all,
    )
    return [_access_user_to_schema(user) for user in users]


@api.post(
    "/access/users",
    response=AccessUserCreateOut,
    tags=["access"],
    summary="Создать заправщика",
    description=(
        "Создаёт пользователя с ролью Заправщик в рамках scope актора."
    ),
)
def access_users_create(
    request: HttpRequest,
    payload: AccessUserCreateIn = Body(...),
):
    _ensure_auth(request)
    try:
        user, temp_password = UserAccessService.create_fueler(
            request.user,
            AccessCreatePayload(
                email=payload.email,
                first_name=payload.first_name,
                last_name=payload.last_name,
                phone=payload.phone,
                password=payload.password,
                region_id=payload.region_id,
                activate=payload.activate,
            ),
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc
    log_access_event(
        actor=request.user,
        action="access_user_create",
        target_user=user,
        details="Создан пользователь доступа",
        before="-",
        after="Заправщик",
        scope=UserAccessService.get_scope_label(user),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return AccessUserCreateOut(
        id=user.id,
        username=user.username,
        temporary_password=temp_password,
    )


@api.patch(
    "/access/users/{user_id}",
    response=AccessUserOut,
    tags=["access"],
    summary="Активировать или деактивировать пользователя",
)
def access_users_patch(
    request: HttpRequest,
    user_id: int = Path(..., description="ID пользователя"),
    payload: AccessStatusPatchIn = Body(...),
):
    _ensure_auth(request)
    try:
        target = UserAccessService.set_active(
            request.user,
            target_id=user_id,
            is_active=payload.is_active,
        )
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc

    action = (
        "access_user_activate"
        if payload.is_active
        else "access_user_deactivate"
    )
    log_access_event(
        actor=request.user,
        action=action,
        target_user=target,
        details="Изменен статус активности пользователя",
        before=f"is_active={not payload.is_active}",
        after=f"is_active={payload.is_active}",
        scope=UserAccessService.get_scope_label(target),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return _access_user_to_schema(target)


@api.patch(
    "/access/users/{user_id}/role",
    response=AccessUserOut,
    tags=["access"],
    summary="Назначить роль",
    description="Заправщик, Менеджер или Администратор.",
)
def access_users_role_patch(
    request: HttpRequest,
    user_id: int = Path(..., description="ID пользователя"),
    payload: AccessRolePatchIn = Body(...),
):
    _ensure_auth(request)
    try:
        target_before = (
            UserAccessService.list_users_for_actor(request.user)
            .filter(id=user_id)
            .first()
        )
        target = UserAccessService.assign_role(
            request.user,
            target_id=user_id,
            role=payload.role,
        )
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc
    before_roles = []
    if target_before:
        before_roles = list(
            target_before.groups.values_list("name", flat=True)
        )
    after_roles = list(target.groups.values_list("name", flat=True))
    log_access_event(
        actor=request.user,
        action="access_role_assign",
        target_user=target,
        details="Изменена роль доступа",
        before=",".join(before_roles) if before_roles else "-",
        after=",".join(after_roles),
        scope=UserAccessService.get_scope_label(target),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return _access_user_to_schema(target)


@api.post(
    "/access/users/{user_id}/reset-password",
    response=AccessPasswordOut,
    tags=["access"],
    summary="Сбросить пароль",
    description="Генерируется временный пароль для выдачи пользователю.",
)
def access_users_reset_password(
    request: HttpRequest,
    user_id: int = Path(..., description="ID пользователя"),
):
    _ensure_auth(request)
    try:
        target, temp_password = UserAccessService.reset_password(
            request.user,
            target_id=user_id,
        )
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc
    log_access_event(
        actor=request.user,
        action="access_password_reset",
        target_user=target,
        details="Сброшен пароль пользователя",
        scope=UserAccessService.get_scope_label(target),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return AccessPasswordOut(
        id=target.id,
        username=target.username,
        temporary_password=temp_password,
    )


@api.patch(
    "/access/users/{user_id}/password",
    response=AccessPasswordOut,
    tags=["access"],
    summary="Установить пароль",
    description="Вручную или с генерацией временного.",
)
def access_users_password_patch(
    request: HttpRequest,
    user_id: int = Path(..., description="ID пользователя"),
    payload: AccessPasswordPatchIn = Body(...),
):
    _ensure_auth(request)
    if not payload.generate_temporary and not (payload.password or "").strip():
        raise HttpError(
            400,
            "Укажите пароль или включите генерацию временного пароля",
        )
    try:
        target, temporary_password = UserAccessService.set_password(
            request.user,
            target_id=user_id,
            password=payload.password,
            generate_temporary=payload.generate_temporary,
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc
    log_access_event(
        actor=request.user,
        action="access_password_reset",
        target_user=target,
        details="Пароль пользователя изменен",
        scope=UserAccessService.get_scope_label(target),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return AccessPasswordOut(
        id=target.id,
        username=target.username,
        temporary_password=temporary_password,
    )


@api.patch(
    "/access/users/{user_id}/scope",
    response=AccessUserOut,
    tags=["access"],
    summary="Изменить региональный scope",
)
def access_users_scope_patch(
    request: HttpRequest,
    user_id: int = Path(..., description="ID пользователя"),
    payload: AccessScopePatchIn = Body(...),
):
    _ensure_auth(request)
    target_before = (
        UserAccessService.list_users_for_actor(request.user)
        .filter(id=user_id)
        .first()
    )
    try:
        target = UserAccessService.set_scope(
            request.user,
            target_id=user_id,
            region_id=payload.region_id,
        )
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc
    before_scope = (
        UserAccessService.get_scope_label(target_before)
        if target_before
        else "-"
    )
    log_access_event(
        actor=request.user,
        action="access_scope_change",
        target_user=target,
        details="Изменен scope пользователя",
        before=before_scope,
        after=UserAccessService.get_scope_label(target),
        scope=UserAccessService.get_scope_label(target),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return _access_user_to_schema(target)


@api.patch(
    "/access/users/{user_id}/profile",
    response=AccessUserOut,
    tags=["access"],
    summary="Обновить профиль сотрудника",
    description="Частичное обновление полей; передайте только изменяемые.",
)
def access_users_profile_patch(
    request: HttpRequest,
    user_id: int = Path(..., description="ID пользователя"),
    payload: AccessUserProfilePatchIn = Body(...),
):
    _ensure_auth(request)
    target_before = (
        UserAccessService.list_users_for_actor(
            request.user,
            active_only=False,
        )
        .filter(id=user_id)
        .first()
    )
    try:
        target = UserAccessService.update_profile(
            request.user,
            target_id=user_id,
            payload=AccessUpdatePayload(
                email=payload.email,
                first_name=payload.first_name,
                last_name=payload.last_name,
                phone=payload.phone,
                region_id=payload.region_id,
            ),
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    except PermissionDenied as exc:
        raise HttpError(403, str(exc)) from exc
    before_email = target_before.email if target_before else "-"
    before_name = target_before.get_full_name() if target_before else "-"
    after_name = target.get_full_name()
    log_access_event(
        actor=request.user,
        action="access_user_profile_update",
        target_user=target,
        details="Обновлен профиль сотрудника",
        before=f"email={before_email};name={before_name}",
        after=f"email={target.email};name={after_name}",
        scope=UserAccessService.get_scope_label(target),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return _access_user_to_schema(target)


@api.get(
    "/access/regions",
    response=list[RegionOut],
    tags=["access"],
    summary="Справочник регионов",
    description="Для форм: админ — все регионы; менеджер — свой регион.",
)
def access_regions(request: HttpRequest):
    _ensure_auth(request)
    UserAccessService._ensure_manager_or_admin(request.user)
    regions_qs = Region.objects.filter(active=True).order_by("name")
    if (
        bool(getattr(request.user, "is_superuser", False))
        or request.user.groups.filter(name="Администратор").exists()
    ):
        return [
            RegionOut(id=region.id, name=region.name) for region in regions_qs
        ]

    if request.user.region_id:
        regions_qs = regions_qs.filter(id=request.user.region_id)
    else:
        regions_qs = regions_qs.none()
    return [RegionOut(id=region.id, name=region.name) for region in regions_qs]


@api.get(
    "/reports/access-events",
    response=list[AccessLogOut],
    tags=["reports"],
    summary="Журнал событий доступа",
    description=(
        "События с префиксом access_. Не-админы видят только записи, "
        "где актор — они сами."
    ),
)
def reports_access_events(
    request: HttpRequest,
    limit: int = Query(100, ge=1, le=200, description="Максимум строк"),
):
    _ensure_auth(request)
    FuelService.ensure_reports_access(request.user)
    safe_limit = max(1, min(limit, 200))
    logs = SystemLog.objects.filter(action__startswith="access_")
    is_admin = (
        bool(getattr(request.user, "is_superuser", False))
        or request.user.groups.filter(name="Администратор").exists()
    )
    if not is_admin:
        logs = logs.filter(user_id=request.user.id)
    logs = logs.select_related("user").order_by("-created_at")[:safe_limit]
    return [
        AccessLogOut(
            id=item.id,
            actor_username=item.user.username if item.user else "SYSTEM",
            action=item.action,
            details=item.details,
            created_at=item.created_at.isoformat(),
        )
        for item in logs
    ]


RECENT_RECORDS_LIMIT = 20
ANALYTICS_TOP_EMPLOYEES = 10
ANALYTICS_TOP_CARS = 10


def _format_analytics_employee_name(
    employee_id: Optional[int],
    first_name: Optional[str],
    last_name: Optional[str],
) -> str:
    if employee_id is None:
        return "Неизвестно"
    parts = [first_name or "", last_name or ""]
    composed = " ".join(part for part in parts if part).strip()
    if composed:
        return composed
    return f"ID {employee_id}"


def _format_analytics_car_label(
    state_number: Optional[str],
    model: Optional[str],
) -> str:
    sn = (state_number or "").strip()
    md = (model or "").strip()
    if sn and md:
        return f"{sn} · {md}"
    return sn or md or "—"


def _analytics_car_breakdown_rows(
    cars_qs,
) -> list[AnalyticsCarBreakdownOut]:
    """Строки топа авто из агрегирующего QuerySet по FuelRecord."""
    rows: list[AnalyticsCarBreakdownOut] = []
    for row in cars_qs:
        car_pk = row.get("car_id")
        if car_pk is None:
            continue
        sn = row.get("car__state_number") or ""
        md = row.get("car__model") or ""
        rows.append(
            AnalyticsCarBreakdownOut(
                car_id=int(car_pk),
                label=_format_analytics_car_label(sn, md),
                state_number=str(sn),
                model=str(md),
                liters=float(row.get("total_liters") or 0),
                records_count=int(row.get("records_count") or 0),
            )
        )
    return rows


def _normalize_analytics_date_range(
    start_date: Optional[date],
    end_date: Optional[date],
) -> tuple[date, date]:
    actual_end = end_date or timezone.now().date()
    actual_start = start_date or (actual_end - timedelta(days=30))

    if actual_start > actual_end:
        raise HttpError(400, "start_date не может быть позже end_date")

    return actual_start, actual_end


def _refuel_source_label(source: str) -> str:
    code = source or ""
    mapping = dict(FuelRecord.SourceFuel.choices)
    label = mapping.get(code, code or "Не указано")
    return str(label)


def _sum_liters(qs) -> float:
    row = qs.aggregate(total=Sum("liters"))
    v = row.get("total")
    return float(v or 0)


def _analytics_dashboard_channel_records_qs(qs):
    """
    Записи для графика «Карта / бот / ТЗ» и согласованного топа сотрудников.

    CARD и TGBOT — только если получатель не топливозаправщик. TRUCK — все
    записи способом «Топливозаправщик», в том числе выдача на ТЗ.
    """
    card_tgbot = Q(
        source__in=[
            FuelRecord.SourceFuel.CARD,
            FuelRecord.SourceFuel.TGBOT,
        ],
        car__is_fuel_tanker=False,
    )
    truck_all = Q(source=FuelRecord.SourceFuel.TRUCK)
    return qs.filter(card_tgbot | truck_all)


def _refuel_sources_card_tgbot_only(
    qs,
) -> list[AnalyticsRefuelSourceSliceOut]:
    """
    «Распределение по источникам» — только CARD и TGBOT по способу записи.

    Топливозаправщики (is_fuel_tanker) здесь как обычные машины: их заправки
    картой и ботом входят в эти срезы. Записи TRUCK (выдача на другие машины
    с бензовоза) в этот график не включаются — см. refuel_channels.
    """
    return [
        AnalyticsRefuelSourceSliceOut(
            source=FuelRecord.SourceFuel.CARD,
            label=_refuel_source_label(FuelRecord.SourceFuel.CARD),
            liters=_sum_liters(qs.filter(source=FuelRecord.SourceFuel.CARD)),
        ),
        AnalyticsRefuelSourceSliceOut(
            source=FuelRecord.SourceFuel.TGBOT,
            label=_refuel_source_label(FuelRecord.SourceFuel.TGBOT),
            liters=_sum_liters(qs.filter(source=FuelRecord.SourceFuel.TGBOT)),
        ),
    ]


def _apply_analytics_filters(
    qs,
    *,
    start_date: Optional[date],
    end_date: Optional[date],
    region_id: Optional[int],
):
    normalized_start, normalized_end = _normalize_analytics_date_range(
        start_date, end_date
    )
    qs = _apply_filled_at_date_range(qs, normalized_start, normalized_end)
    if region_id is not None:
        qs = qs.filter(historical_region_id=region_id)
    return qs


@api.get(
    "/analytics/stats",
    response=AnalyticsDataOut,
    tags=["analytics"],
    summary="Данные дашборда аналитики",
    description=(
        "KPI, графики и топы; срезы согласованы с бизнес-правилами "
        "(см. docs/ARCHITECTURE.md)."
    ),
)
def analytics_stats(
    request: HttpRequest,
    start_date: Optional[date] = Query(
        None,
        description="Начало периода; по умолчанию ~30 дней до end_date",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Конец периода; по умолчанию сегодня",
    ),
    region_id: Optional[int] = Query(
        None,
        description="Исторический регион; учитывается scope менеджера",
    ),
) -> AnalyticsDataOut:
    _ensure_auth(request)
    FuelService.ensure_reports_access(request.user)

    rid = FuelService.normalized_reports_region_id(
        request.user,
        region_id,
    )
    qs = (
        FuelRecord.objects.active_for_reports()
        .with_historical_data()
        .select_related("car", "employee", "historical_region")
        .all()
    )
    qs = _apply_analytics_filters(
        qs,
        start_date=start_date,
        end_date=end_date,
        region_id=rid,
    )

    qs_channels_scope = _analytics_dashboard_channel_records_qs(qs)

    by_day_qs = (
        qs_channels_scope.annotate(day=TruncDay("filled_at"))
        .values("day")
        .annotate(
            total_liters=Sum("liters"),
            records_count=Count("id"),
        )
        .order_by("day")
    )
    by_day: list[AnalyticsByDayPointOut] = []
    for row in by_day_qs:
        day_dt = row.get("day")
        if day_dt is None:
            continue
        by_day.append(
            AnalyticsByDayPointOut(
                date=day_dt.date().isoformat(),
                liters=float(row.get("total_liters") or 0),
            )
        )

    by_day_region_qs = (
        qs_channels_scope.annotate(day=TruncDay("filled_at"))
        .values("day", "historical_region__name")
        .annotate(total_liters=Sum("liters"))
        .order_by("day", "historical_region__name")
    )
    by_day_region: list[AnalyticsByDayRegionPointOut] = []
    for row in by_day_region_qs:
        day_dt = row.get("day")
        if day_dt is None:
            continue
        by_day_region.append(
            AnalyticsByDayRegionPointOut(
                date=day_dt.date().isoformat(),
                region_name=str(
                    row.get("historical_region__name") or "Без региона"
                ),
                liters=float(row.get("total_liters") or 0),
            )
        )

    refuel_sources = _refuel_sources_card_tgbot_only(qs)

    refuel_channels: list[AnalyticsRefuelChannelSliceOut] = []
    for code in (
        FuelRecord.SourceFuel.CARD,
        FuelRecord.SourceFuel.TGBOT,
        FuelRecord.SourceFuel.TRUCK,
    ):
        agg = qs_channels_scope.filter(source=code).aggregate(
            total_liters=Sum("liters"),
            records_count=Count("id"),
        )
        refuel_channels.append(
            AnalyticsRefuelChannelSliceOut(
                channel=str(code),
                label=_refuel_source_label(str(code)),
                liters=float(agg.get("total_liters") or 0),
                records_count=int(agg.get("records_count") or 0),
            )
        )

    recent_qs = qs.order_by("-filled_at").select_related(
        "car", "employee", "historical_region"
    )[:RECENT_RECORDS_LIMIT]
    recent_records: list[AnalyticsRecentRecordOut] = []
    for record in recent_qs:
        employee_name = (
            record.employee.get_full_name()
            if record.employee
            else "Неизвестно"
        )
        car_label = record.car.state_number if record.car else ""
        region_name = (
            record.historical_region.name if record.historical_region else None
        )
        fuel_type_code = record.fuel_type
        fuel_type_label_value = str(record.get_fuel_type_display())
        recent_records.append(
            AnalyticsRecentRecordOut(
                id=record.id,
                filled_at=record.filled_at.isoformat(),
                employee_name=employee_name,
                car=car_label,
                car_id=record.car_id,
                car_is_fuel_tanker=bool(
                    record.car and record.car.is_fuel_tanker
                ),
                region_name=region_name,
                fuel_type=fuel_type_code,
                fuel_type_label=fuel_type_label_value,
                source=str(record.source),
                liters=float(record.liters),
                notes=record.notes or "",
            )
        )

    employees_qs = (
        qs_channels_scope.values(
            "employee_id",
            "employee__first_name",
            "employee__last_name",
        )
        .annotate(
            total_liters=Sum("liters"),
            records_count=Count("id"),
        )
        .order_by("-total_liters")[:ANALYTICS_TOP_EMPLOYEES]
    )
    by_employee: list[AnalyticsEmployeeBreakdownOut] = []
    for row in employees_qs:
        emp_id = row.get("employee_id")
        by_employee.append(
            AnalyticsEmployeeBreakdownOut(
                employee_id=emp_id,
                name=_format_analytics_employee_name(
                    emp_id,
                    row.get("employee__first_name"),
                    row.get("employee__last_name"),
                ),
                liters=float(row.get("total_liters") or 0),
                records_count=int(row.get("records_count") or 0),
            )
        )

    cars_agg_qs = (
        qs.exclude(car__is_fuel_tanker=True)
        .values(
            "car_id",
            "car__state_number",
            "car__model",
        )
        .annotate(
            total_liters=Sum("liters"),
            records_count=Count("id"),
        )
        .order_by("-total_liters")[:ANALYTICS_TOP_CARS]
    )
    by_car = _analytics_car_breakdown_rows(cars_agg_qs)

    tankers_agg_qs = (
        qs.filter(car__is_fuel_tanker=True)
        .values(
            "car_id",
            "car__state_number",
            "car__model",
        )
        .annotate(
            total_liters=Sum("liters"),
            records_count=Count("id"),
        )
        .order_by("-total_liters")[:ANALYTICS_TOP_CARS]
    )
    by_car_fuel_tankers = _analytics_car_breakdown_rows(tankers_agg_qs)

    return AnalyticsDataOut(
        by_day=by_day,
        by_day_region=by_day_region,
        refuel_sources=refuel_sources,
        refuel_channels=refuel_channels,
        recent_records=recent_records,
        by_employee=by_employee,
        by_car=by_car,
        by_car_fuel_tankers=by_car_fuel_tankers,
    )


@api.get(
    "/analytics/export",
    tags=["analytics"],
    summary="Выгрузка аналитики в Excel",
    description=(
        "Файл .xlsx с колонками дата, сотрудник, авто, регион, тип топлива, "
        "объём. Параметры периода и региона — как у GET /analytics/stats."
    ),
    openapi_extra={
        "responses": {
            200: {
                "description": "Двоичный файл Excel (Open XML)",
                "content": {
                    (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ): {
                        "schema": {"type": "string", "format": "binary"},
                    },
                },
            },
        },
    },
)
def analytics_export(
    request: HttpRequest,
    start_date: Optional[date] = Query(
        None,
        description="Начало периода",
    ),
    end_date: Optional[date] = Query(None, description="Конец периода"),
    region_id: Optional[int] = Query(None, description="Исторический регион"),
) -> HttpResponse:
    _ensure_auth(request)
    FuelService.ensure_reports_access(request.user)

    start_dt, end_dt = _normalize_analytics_date_range(start_date, end_date)

    rid = FuelService.normalized_reports_region_id(
        request.user,
        region_id,
    )
    qs = (
        FuelRecord.objects.active_for_reports()
        .with_historical_data()
        .select_related("car", "employee", "historical_region")
        .all()
    )
    qs = _apply_analytics_filters(
        qs,
        start_date=start_dt,
        end_date=end_dt,
        region_id=rid,
    ).order_by("filled_at")

    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Analytics"

    headers = [
        "Дата",
        "Сотрудник",
        "Автомобиль",
        "Регион",
        "Тип топлива",
        "Объем",
    ]
    ws.append(headers)

    for record in qs.iterator(chunk_size=1000):
        employee_name = (
            record.employee.get_full_name()
            if record.employee
            else "Неизвестно"
        )
        car_label = record.car.state_number if record.car else ""
        region_name = (
            record.historical_region.name if record.historical_region else ""
        )
        fuel_type_label_value = str(record.get_fuel_type_display())

        ws.append(
            [
                record.filled_at.strftime("%d.%m.%Y %H:%M"),
                employee_name,
                car_label,
                region_name,
                fuel_type_label_value,
                float(record.liters),
            ]
        )

    filename_region = "all" if region_id is None else str(region_id)
    filename = (
        f"fuel_analytics_{start_dt.isoformat()}_"
        f"{end_dt.isoformat()}_{filename_region}.xlsx"
    )

    output = BytesIO()
    wb.save(output)
    excel_bytes = output.getvalue()

    excel_content_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response = HttpResponse(
        excel_bytes,
        content_type=excel_content_type,
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Content-Length"] = str(len(excel_bytes))
    return response
