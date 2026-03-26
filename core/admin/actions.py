from django.contrib import messages
from django.shortcuts import redirect

from core.services.export_service import ExportService


def export_model_data(
    modeladmin,
    request,
    queryset,
    export_method: str = None,
    filename_prefix: str = None,
):
    """
    Универсальное действие для экспорта данных моделей

    Args:
        modeladmin: Экземпляр ModelAdmin
        request: HTTP запрос
        queryset: Выбранные объекты
        export_method: Название метода в ExportService
        filename_prefix: Префикс для имени файла
    """
    try:
        model = modeladmin.model
        model_name = model._meta.verbose_name_plural

        # Если не указан метод экспорта, используем стандартный
        if not export_method:
            export_method = f"export_{model._meta.model_name}_data"

        # Если не указан префикс файла, используем название модели
        if not filename_prefix:
            filename_prefix = model._meta.model_name

        # Получаем метод из ExportService
        export_func = getattr(ExportService, export_method, None)

        if not export_func:
            raise AttributeError(
                f"Export method {export_method} not found in ExportService"
            )

        # Если не выбраны конкретные записи, экспортируем все
        if not queryset:
            queryset = model.objects.all()

        # Определяем формат экспорта из параметров запроса
        format_type = request.GET.get("format", "xlsx")

        # Если метод поддерживает выбранные записи, передаем их
        if "selected" in export_method.lower():
            selected_ids = list(queryset.values_list("id", flat=True))
            return export_func(selected_ids, format_type)
        else:
            # Иначе используем общий экспорт
            return export_func(format_type)

    except Exception as e:
        messages.error(request, f"Ошибка при экспорте {model_name}: {str(e)}")
        return redirect("..")


def export_action(export_method=None, filename_prefix=None, description=None):
    """Декоратор для создания действий экспорта"""

    def decorator(func):
        def wrapper(modeladmin, request, queryset):
            return export_model_data(
                modeladmin,
                request,
                queryset,
                export_method=export_method,
                filename_prefix=filename_prefix,
            )

        wrapper.short_description = description
        return wrapper

    return decorator
