from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from core.models import FuelRecord, Region
from core.admin.actions import export_action
from core.services.export_service import ExportService


# Кастомные фильтры для FuelRecord
class FuelRecordRegionFilter(admin.SimpleListFilter):
    title = "Регион"
    parameter_name = "region"

    def lookups(self, request, model_admin):
        regions = Region.objects.all().values_list("id", "name")
        return regions

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(car__region_id=self.value())
        return queryset


@admin.register(FuelRecord)
class FuelRecordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "filled_at_formatted",
        "car_display",
        "fuel_type_display",
        "liters",
        "source_display",
        "reporting_status_display",
        "historical_department_display",
        "historical_region_display",
        "notes",
        "employee_display",
    )
    list_filter = (
        "fuel_type",
        "source",
        "reporting_status",
        "filled_at",
        "created_at",
        FuelRecordRegionFilter,
    )
    search_fields = (
        "car__code",
        "car__state_number",
        "car__model",
        "employee__username",
        "employee__first_name",
        "employee__last_name",
        "notes",
        "historical_department",
        "historical_region__name",
    )
    date_hierarchy = "filled_at"
    autocomplete_fields = ("car", "employee")
    readonly_fields = ("created_at", "updated_at", "display_info")
    list_display_links = ("id", "filled_at_formatted")
    list_per_page = 30

    actions = ["export_selected_fuel_records"]

    # Настройка отображения детальной формы
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "car",
                    "employee",
                    ("liters", "fuel_type"),
                    "source",
                    "reporting_status",
                    "filled_at",
                    "notes",
                    "display_info",
                    ("historical_department", "historical_region"),
                )
            },
        ),
        (
            "Системная информация",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    # Оптимизация запросов
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "car", "employee", "car__region", "historical_region"
            )
        )

    # Кастомные методы отображения
    @admin.display(description="Автомобиль", ordering="car__state_number")
    def car_display(self, obj):
        if obj.car:
            return format_html(
                '<a href="{}?id__exact={}">{}</a>',
                "/admin/core/car/",
                obj.car.id,
                f"{obj.car.state_number} ({obj.car.model})",
            )
        return "-"

    @admin.display(description="Сотрудник", ordering="employee__last_name")
    def employee_display(self, obj):
        if obj.employee:
            return format_html(
                '<a href="{}?id__exact={}">{}</a>',
                "/admin/core/user/",
                obj.employee.id,
                obj.employee.get_full_name() or obj.employee.username,
            )
        return "-"

    @admin.display(description="Тип топлива")
    def fuel_type_display(self, obj):
        color = "green" if obj.fuel_type == "GASOLINE" else "orange"
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_fuel_type_display(),
        )

    @admin.display(description="Способ")
    def source_display(self, obj):
        icons = {"CARD": "💳", "TGBOT": "🤖", "TRUCK": "🚛"}
        return format_html(
            "{} {}", icons.get(obj.source, "❓"), obj.get_source_display()
        )

    @admin.display(description="Статус учёта", ordering="reporting_status")
    def reporting_status_display(self, obj):
        if obj.reporting_status == FuelRecord.ReportingStatus.EXCLUDED_DELETION:
            return format_html(
                '<span style="color: #b91c1c; font-weight: 600;">{}</span>',
                obj.get_reporting_status_display(),
            )
        return format_html(
            '<span style="color: #047857; font-weight: 600;">{}</span>',
            obj.get_reporting_status_display(),
        )

    @admin.display(description="Дата заправки", ordering="filled_at")
    def filled_at_formatted(self, obj):
        if obj.filled_at:
            # переводим UTC в локальный часовой пояс (TIME_ZONE)
            local_dt = timezone.localtime(obj.filled_at)
            # форматируем с отображением TZ
            return local_dt.strftime("%d.%m.%Y %H:%M (%Z)")
        return "-"

    @admin.display(description="Регион", ordering="historical_region__name")
    def historical_region_display(self, obj):
        if obj.historical_region:
            return obj.historical_region.name
        elif obj.car and obj.car.region:
            return obj.car.region.name
        return "-"

    @admin.display(
        description="Подразделение", ordering="historical_department"
    )
    def historical_department_display(self, obj):
        if obj.historical_department:
            return obj.historical_department
        elif obj.car and obj.car.department:
            return obj.car.department
        return "-"

    # Кастомные действия
    @export_action(
        export_method="export_selected_fuel_records",
        filename_prefix="selected_fuel_records",
        description="📥 Экспорт (Excel)",
    )
    def export_selected_fuel_records(self, request, queryset):
        """Экспорт выбранных заправок"""
        pass

    # Кастомные views для URL
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "export-fuel-report/",
                self.admin_site.admin_view(self.export_fuel_report_view),
                name="export_fuel_report",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context=extra_context)

    def fuel_statistics_view(self, request):
        """Расширенная статистика по заправкам"""

        # Базовая статистика (как в отчётах — только учитываемые записи)
        base = FuelRecord.objects.active_for_reports()
        total_stats = base.fuel_statistics()

        # Статистика по источникам
        card_stats = base.by_source("CARD").fuel_statistics()
        bot_stats = base.by_source("TGBOT").fuel_statistics()
        truck_stats = base.by_source("TRUCK").fuel_statistics()

        # Статистика за последние 30 дней
        recent_stats = base.recent(30).fuel_statistics()

        message = format_html(
            """
            <strong>📊 Общая статистика заправок:</strong><br>
            • Всего записей: {}<br>
            • Всего литров: {}<br>
            • Средний объём: {}<br>
            • Максимальная заправка: {}<br>
            • Минимальная заправка: {}<br>
            <br>
            <strong>📈 По источникам:</strong><br>
            • Топливные карты: {} запр., {}<br>
            • Telegram-бот: {} запр., {}<br>
            • Топливозаправщики: {} запр., {}<br>
            <br>
            <strong>📅 За последние 30 дней:</strong><br>
            • Заправок: {}<br>
            • Литров: {}<br>
            <br>            
            """,
            total_stats["total_records"],
            f"{total_stats['total_liters'] or 0:.1f} л",
            f"{total_stats['avg_liters'] or 0:.1f} л",
            f"{total_stats['max_liters'] or 0:.1f} л",
            f"{total_stats['min_liters'] or 0:.1f} л",
            card_stats["total_records"],
            f"{card_stats['total_liters'] or 0:.1f} л",
            bot_stats["total_records"],
            f"{bot_stats['total_liters'] or 0:.1f} л",
            truck_stats["total_records"],
            f"{truck_stats['total_liters'] or 0:.1f} л",
            recent_stats["total_records"],
            f"{recent_stats['total_liters'] or 0:.1f} л",
        )

        messages.info(request, message)
        return HttpResponseRedirect("../")

    def suspicious_records_view(self, request):
        """Поиск подозрительных записей"""
        suspicious = FuelRecord.objects.find_suspicious_records(
            threshold_liters=200
        )

        if suspicious.exists():
            suspicious_list = []
            for record in suspicious[:15]:  # Ограничиваем вывод
                suspicious_list.append(
                    f"• {record.car.state_number if record.car else 'N/A'}: "
                    f"{record.liters} л ({record.filled_at.strftime('%d.%m.%Y')}) - "
                    f"{record.employee.get_full_name() if record.employee else 'Неизвестно'}"
                )

            message = format_html(
                "<strong>🚨 Подозрительные записи (более 200 л):</strong><br>{}",
                "<br>".join(suspicious_list),
            )
            messages.warning(request, message)
        else:
            messages.info(request, "✅ Подозрительных записей не найдено")

        return HttpResponseRedirect("../")

    # @export_action(
    #     export_method='export_fuel_records_data',
    #     filename_prefix='fuel_report',
    #     description='📊 Экспорт отчета о заправках'
    # )
    def export_fuel_report_view(self, request):
        """Экспорт отчета по заправкам"""
        response = ExportService.export_fuel_records_data("xlsx")

        # Добавляем информацию об экспорте
        stats = FuelRecord.objects.active_for_reports().fuel_statistics()
        messages.success(
            request,
            f"✅ Успешно экспортировано {stats['total_records']} записей о заправках",
            messages.SUCCESS,
        )

        return response

    # get_actions override removed: we keep actions minimal and explicit.
