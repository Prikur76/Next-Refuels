from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import OuterRef, Subquery

from core.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "get_full_name",
        "phone",
        "telegram_id",
        "region",
        "get_groups",
        "is_active",
        "is_staff",
    )

    list_filter = ("is_active", "region", "groups")
    search_fields = ("username", "telegram_id", "first_name", "last_name")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Персональные данные",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone",
                    "telegram_id",
                    "region",
                )
            },
        ),
        (
            "Права доступа",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )

    list_per_page = 30
    ordering = ("region", "username")

    # -------------------------------
    # АННОТАЦИЯ ДЛЯ СОРТИРОВКИ ГРУПП
    # -------------------------------
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        first_group = (
            User.groups.through.objects.filter(user_id=OuterRef("pk"))
            .order_by("group__name")
            .values("group__name")[:1]
        )

        return qs.annotate(first_group_name=Subquery(first_group))

    # -------------------------------
    # ФИО
    # -------------------------------
    @admin.display(description="ФИО")
    def get_full_name(self, obj):
        if obj.first_name and obj.last_name:
            return f"{obj.last_name} {obj.first_name}"
        return obj.username

    # -------------------------------
    # РОЛЬ / ГРУППЫ + сортировка
    # -------------------------------
    @admin.display(description="Роль", ordering="first_group_name")
    def get_groups(self, obj):
        return ", ".join(obj.groups.values_list("name", flat=True)) or "—"
