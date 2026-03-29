from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.db.models import Q
from django.views.decorators.http import require_GET

from core.models import FuelRecord
from core.services.export_service import ExportService
from core.services.fuel_service import FuelService


@login_required
@require_GET
def export_reports_csv(request: HttpRequest) -> HttpResponse:
    FuelService.ensure_reports_access(request.user)
    queryset = _build_filtered_queryset(request)
    filename = "fuel_reports.csv"
    return ExportService.export_to_csv(_to_export_rows(queryset), filename)


@login_required
@require_GET
def export_reports_xlsx(request: HttpRequest) -> HttpResponse:
    FuelService.ensure_reports_access(request.user)
    queryset = _build_filtered_queryset(request)
    filename = "fuel_reports.xlsx"
    return ExportService.export_to_excel(_to_export_rows(queryset), filename)


def _build_filtered_queryset(request: HttpRequest):
    qs = (
        FuelRecord.objects.active_for_reports()
        .with_related_data()
        .order_by("-filled_at", "-id")
    )
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    region_id_raw = request.GET.get("region_id")
    region = request.GET.get("region")
    employee = request.GET.get("employee")
    car_id = request.GET.get("car_id")
    car_state_number = request.GET.get("car_state_number")
    source = request.GET.get("source")

    if from_date:
        qs = qs.filter(filled_at__date__gte=date.fromisoformat(from_date))
    if to_date:
        qs = qs.filter(filled_at__date__lte=date.fromisoformat(to_date))
    parsed_rid = int(region_id_raw) if region_id_raw else None
    rid = FuelService.normalized_reports_region_id(
        request.user,
        parsed_rid,
    )
    if rid is not None:
        qs = qs.filter(historical_region_id=rid)
    if region:
        region_value = region.strip()
        if region_value:
            qs = qs.filter(
                Q(historical_region__name__icontains=region_value)
                | Q(car__region__name__icontains=region_value)
            )
    if employee:
        employee_value = employee.strip()
        if employee_value:
            qs = qs.filter(
                Q(employee__username__icontains=employee_value)
                | Q(employee__first_name__icontains=employee_value)
                | Q(employee__last_name__icontains=employee_value)
            )
    if car_id:
        qs = qs.filter(car_id=int(car_id))
    if car_state_number:
        car_state_number_value = car_state_number.strip()
        if car_state_number_value:
            qs = qs.filter(car__state_number__icontains=car_state_number_value)
    if source:
        qs = qs.filter(source=source)
    return qs


def _to_export_rows(queryset):
    rows = []
    for record in queryset:
        rows.append(
            {
                "дата заправки": record.filled_at.strftime("%d.%m.%Y %H:%M"),
                "госномер": record.car.state_number if record.car else "",
                "модель авто": record.car.model if record.car else "",
                "литры": float(record.liters),
                "тип топлива": record.get_fuel_type_display(),
                "источник": record.get_source_display(),
                "сотрудник": (
                    record.employee.get_full_name() if record.employee else ""
                ),
                "регион": (
                    record.historical_region.name
                    if record.historical_region
                    else ""
                ),
                "подразделение": record.historical_department or "",
                "комментарий": record.notes or "",
            }
        )
    return rows
