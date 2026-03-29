from __future__ import annotations

from typing import Optional

from ninja import Field, Schema


class AnalyticsByDayPointOut(Schema):
    """Точка графика «объём по дням»."""

    date: str = Field(..., description="Дата (ISO 8601, календарный день)")
    liters: float = Field(..., description="Сумма литров за день")


class AnalyticsByDayRegionPointOut(Schema):
    """Объём по дню и историческому региону."""

    date: str = Field(..., description="Дата (ISO)")
    region_name: str = Field(..., description="Название региона")
    liters: float = Field(..., description="Литры за день в регионе")


class AnalyticsRefuelSourceSliceOut(Schema):
    """Срез «источник» только для карты и бота (CARD/TGBOT)."""

    source: str = Field(..., description="Код способа")
    label: str = Field(..., description="Подпись для UI")
    liters: float = Field(..., description="Литры")


class AnalyticsRefuelChannelSliceOut(Schema):
    """
    Канал CARD, TGBOT или TRUCK для блока «карта / бот / топливозаправщик».

    CARD и TGBOT — без получателей-топливозаправщиков; TRUCK — все выдачи
    топливозаправщиком.
    """

    channel: str = Field(..., description="CARD, TGBOT или TRUCK")
    label: str = Field(..., description="Подпись для UI")
    liters: float = Field(..., description="Литры в срезе")
    records_count: int = Field(..., description="Число записей")


class AnalyticsRecentRecordOut(Schema):
    """Строка блока последних заправок на дашборде."""

    id: int
    filled_at: str = Field(..., description="Дата-время заправки (ISO)")
    employee_name: str
    car: str = Field(..., description="Госномер или метка ТС")
    car_id: int
    car_is_fuel_tanker: bool = Field(
        False,
        description="ТС — топливозаправщик",
    )
    region_name: Optional[str] = Field(None, description="Исторический регион")
    fuel_type: str = Field(..., description="Код типа топлива")
    fuel_type_label: str = Field(..., description="Локализованная подпись")
    source: str = Field(..., description="Способ заправки")
    liters: float
    notes: str = ""


class AnalyticsEmployeeBreakdownOut(Schema):
    """Строка топа сотрудников по объёму."""

    employee_id: Optional[int] = Field(None, description="ID сотрудника")
    name: str = Field(..., description="Отображаемое имя")
    liters: float
    records_count: int


class AnalyticsCarBreakdownOut(Schema):
    """Строка топа автомобилей по объёму."""

    car_id: int
    label: str = Field(..., description="Госномер · модель")
    state_number: str
    model: str
    liters: float
    records_count: int


class AnalyticsDataOut(Schema):
    """
    Полный ответ дашборда аналитики.

    Поля by_day и by_day_region строятся по тому же срезу, что
    refuel_channels (см. ARCHITECTURE.md).
    """

    by_day: list[AnalyticsByDayPointOut] = Field(
        ...,
        description="Сумма литров по календарным дням",
    )
    by_day_region: list[AnalyticsByDayRegionPointOut] = Field(
        ...,
        description="Литры по дням с разбивкой по регионам",
    )
    refuel_sources: list[AnalyticsRefuelSourceSliceOut] = Field(
        ...,
        description="Только карта и бот (без канала TRUCK)",
    )
    refuel_channels: list[AnalyticsRefuelChannelSliceOut] = Field(
        ...,
        description="Три канала: карта, бот, топливозаправщик",
    )
    recent_records: list[AnalyticsRecentRecordOut] = Field(
        ...,
        description="Последние записи за период",
    )
    by_employee: list[AnalyticsEmployeeBreakdownOut] = Field(
        ...,
        description="Топ сотрудников по объёму (срез дашборда)",
    )
    by_car: list[AnalyticsCarBreakdownOut] = Field(
        ...,
        description="Топ авто (без топливозаправщиков как получателей)",
    )
    by_car_fuel_tankers: list[AnalyticsCarBreakdownOut] = Field(
        ...,
        description="Топ машин с признаком топливозаправщик",
    )
