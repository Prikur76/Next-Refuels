from __future__ import annotations

from typing import Optional

from ninja import Schema


class AnalyticsByDayPointOut(Schema):
    date: str
    liters: float


class AnalyticsRefuelSourceSliceOut(Schema):
    source: str
    label: str
    liters: float


class AnalyticsRefuelChannelSliceOut(Schema):
    """
    Три канала: CARD, TGBOT, TRUCK — только где car не топливозаправщик.
    """

    channel: str
    label: str
    liters: float
    records_count: int


class AnalyticsRecentRecordOut(Schema):
    filled_at: str
    employee_name: str
    car: str
    region_name: Optional[str] = None
    fuel_type: str
    fuel_type_label: str
    liters: float


class AnalyticsEmployeeBreakdownOut(Schema):
    employee_id: Optional[int] = None
    name: str
    liters: float
    records_count: int


class AnalyticsCarBreakdownOut(Schema):
    car_id: int
    label: str
    state_number: str
    model: str
    liters: float
    records_count: int


class AnalyticsDataOut(Schema):
    by_day: list[AnalyticsByDayPointOut]
    refuel_sources: list[AnalyticsRefuelSourceSliceOut]
    refuel_channels: list[AnalyticsRefuelChannelSliceOut]
    recent_records: list[AnalyticsRecentRecordOut]
    by_employee: list[AnalyticsEmployeeBreakdownOut]
    by_car: list[AnalyticsCarBreakdownOut]
    by_car_fuel_tankers: list[AnalyticsCarBreakdownOut]

