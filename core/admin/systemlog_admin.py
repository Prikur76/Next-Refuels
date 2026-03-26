from django.contrib import admin

from core.models import SystemLog


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "action",
        "ip_address",
        "short_details",
    )
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "details", "ip_address")
    readonly_fields = ("created_at", "user", "action", "details", "ip_address")
    list_per_page = 50
    date_hierarchy = "created_at"

    @admin.display(description="Подробности")
    def short_details(self, obj):
        return (
            (obj.details[:70] + "...")
            if len(obj.details) > 70
            else obj.details
        )

    # Запрещаем создание/редактирование логов через админку
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # Оптимизация запросов
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")
