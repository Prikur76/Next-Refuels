import io
from datetime import datetime
from typing import Dict, List, Union

import polars as pl
from django.db.models import QuerySet
from django.http import HttpResponse

from core.models import Car, FuelRecord


class ExportService:
    FUEL_TYPE_LABELS = {
        FuelRecord.FuelType.GASOLINE: "Бензин",
        FuelRecord.FuelType.DIESEL: "Дизель",
    }
    SOURCE_LABELS = {
        FuelRecord.SourceFuel.CARD: "Топливная карта",
        FuelRecord.SourceFuel.TGBOT: "Телеграм-бот",
        FuelRecord.SourceFuel.TRUCK: "Топливозаправщик",
    }

    """Сервис для экспорта данных в различные форматы"""

    @staticmethod
    def _convert_to_dataframe(
        data: Union[QuerySet, List[Dict]],
    ) -> pl.DataFrame:
        """
        Конвертирует Django QuerySet или список словарей в Polars DataFrame

        Args:
            data: Django QuerySet или список словарей

        Returns:
            Polars DataFrame
        """
        # Если это QuerySet, конвертируем в список словарей
        if hasattr(data, "values"):
            data = list(data.values())

        if not data:
            # Создаем пустой DataFrame
            return pl.DataFrame()

        # Обрабатываем данные для избежания проблем с типами
        processed_data = []
        for item in data:
            processed_item = {}
            for key, value in item.items():
                # Обрабатываем None значения
                if value is None:
                    processed_item[key] = ""
                # Обрабатываем datetime
                elif isinstance(value, datetime):
                    if value.tzinfo is not None:
                        processed_item[key] = value.replace(tzinfo=None)
                    else:
                        processed_item[key] = value
                # Обрабатываем булевы значения
                elif isinstance(value, bool):
                    processed_item[key] = str(value)
                # Обрабатываем числа
                elif isinstance(value, (int, float)):
                    processed_item[key] = value
                # Все остальное преобразуем в строку
                else:
                    processed_item[key] = (
                        str(value) if value is not None else ""
                    )
            processed_data.append(processed_item)

        # Создаем DataFrame с явным указанием типов
        try:
            df = pl.DataFrame(processed_data)
            return df
        except Exception as e:
            # Если возникла ошибка, пробуем создать DataFrame с явной схемой
            print(f"Error creating DataFrame: {e}")
            # Создаем DataFrame по одному ряду
            if processed_data:
                df = pl.DataFrame([processed_data[0]])
                for row in processed_data[1:]:
                    df = df.vstack(pl.DataFrame([row]))
                return df
            else:
                return pl.DataFrame()

    @staticmethod
    def _safe_dataframe_export(df: pl.DataFrame, format_type: str) -> bytes:
        """
        Безопасный экспорт DataFrame в указанный формат

        Args:
            df: Polars DataFrame
            format_type: 'csv' или 'excel'

        Returns:
            bytes данных
        """
        if df.is_empty():
            # Создаем пустой DataFrame с минимальной структурой
            df = pl.DataFrame({"message": ["No data available"]})

        try:
            if format_type == "csv":
                return df.write_csv().encode("utf-8")
            elif format_type == "excel":
                buffer = io.BytesIO()
                df.write_excel(buffer, worksheet="data")
                return buffer.getvalue()
            else:
                raise ValueError(f"Unsupported format: {format_type}")
        except Exception as e:
            # Резервный метод для проблемных данных
            print(f"Export error: {e}")
            # Конвертируем все в строки
            df_str = df.cast(pl.Utf8)
            if format_type == "csv":
                return df_str.write_csv().encode("utf-8")
            elif format_type == "excel":
                buffer = io.BytesIO()
                df_str.write_excel(buffer, worksheet="data")
                return buffer.getvalue()

    @staticmethod
    def export_generic_data(
        queryset, format_type: str = "xlsx"
    ) -> HttpResponse:
        """
        Универсальный экспорт любого QuerySet

        Args:
            queryset: Django QuerySet для экспорта
            format_type: Формат экспорта

        Returns:
            HttpResponse с файлом
        """
        model_name = queryset.model._meta.model_name
        filename = f"{model_name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"

        if format_type == "csv":
            return ExportService.export_to_csv(queryset, filename)
        elif format_type == "xlsx":
            return ExportService.export_to_excel(queryset, filename)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    @staticmethod
    def export_to_csv(
        data: Union[QuerySet, List[Dict]], filename: str
    ) -> HttpResponse:
        """
        Экспорт данных в CSV

        Args:
            data: Django QuerySet или список словарей для экспорта
            filename: Имя файла для скачивания

        Returns:
            HttpResponse с файлом CSV
        """
        df = ExportService._convert_to_dataframe(data)

        # Экспортируем данные
        csv_data = ExportService._safe_dataframe_export(df, "csv")

        # Создаем ответ
        response = HttpResponse(
            csv_data, content_type="text/csv; charset=utf-8"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = len(csv_data)

        return response

    @staticmethod
    def export_to_excel(
        data: Union[QuerySet, List[Dict]], filename: str
    ) -> HttpResponse:
        """
        Экспорт данных в Excel

        Args:
            data: Django QuerySet или список словарей для экспорта
            filename: Имя файла для скачивания

        Returns:
            HttpResponse с файлом Excel
        """
        df = ExportService._convert_to_dataframe(data)

        # Экспортируем данные
        excel_data = ExportService._safe_dataframe_export(df, "excel")

        # Создаем ответ
        response = HttpResponse(
            excel_data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Content-Length"] = len(excel_data)

        return response

    @staticmethod
    def export_fuel_records_data(format_type: str = "csv") -> HttpResponse:
        """Экспорт данных о заправках с читаемыми значениями"""

        # Получаем данные с оптимизацией
        queryset = FuelRecord.objects.select_related(
            "car", "employee", "car__region", "historical_region"
        ).all()

        # Подготавливаем данные для экспорта с читаемыми значениями
        fuel_data = []
        for record in queryset.iterator(chunk_size=1000):
            fuel_data.append(
                {
                    "дата заправки": record.filled_at.strftime(
                        "%d.%m.%Y %H:%M"
                    )
                    if record.filled_at
                    else "",
                    "модель авто": record.car.model if record.car else "",
                    "госномер": record.car.state_number if record.car else "",
                    "кол-во, л": float(record.liters)
                    if record.liters
                    else 0.0,
                    "тип топлива": ExportService.FUEL_TYPE_LABELS.get(
                        record.fuel_type, record.fuel_type or ""
                    ),
                    "способ заправки": ExportService.SOURCE_LABELS.get(
                        record.source, record.source or ""
                    ),
                    "сотрудник": record.employee.get_full_name()
                    if record.employee
                    else "",
                    "подразделение авто": record.historical_department or "",
                    "регион": record.historical_region.name
                    if record.historical_region
                    else "",
                    "комментарий": record.notes or "",
                }
            )

        filename = f"fuel_records_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"

        if format_type == "csv":
            return ExportService.export_to_csv(fuel_data, filename)
        elif format_type == "xlsx":
            return ExportService.export_to_excel(fuel_data, filename)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    @staticmethod
    def export_selected_fuel_records(
        selected_ids: List[int], format_type: str = "csv"
    ) -> HttpResponse:
        """Экспорт выбранных заправок с читаемыми значениями"""

        # Получаем выбранные заправки с оптимизацией
        queryset = FuelRecord.objects.filter(
            id__in=selected_ids
        ).select_related("car", "employee", "car__region", "historical_region")

        # Подготавливаем данные для экспорта с читаемыми значениями
        fuel_data = []
        for record in queryset.iterator(chunk_size=1000):
            fuel_data.append(
                {
                    "дата заправки": record.filled_at.strftime(
                        "%d.%m.%Y %H:%M"
                    )
                    if record.filled_at
                    else "",
                    "модель авто": record.car.model if record.car else "",
                    "госномер": record.car.state_number if record.car else "",
                    "кол-во, л": float(record.liters)
                    if record.liters
                    else 0.0,
                    "тип топлива": ExportService.FUEL_TYPE_LABELS.get(
                        record.fuel_type, record.fuel_type or ""
                    ),
                    "способ заправки": ExportService.SOURCE_LABELS.get(
                        record.source, record.source or ""
                    ),
                    "сотрудник": record.employee.get_full_name()
                    if record.employee
                    else "",
                    "подразделение авто": record.historical_department or "",
                    "регион": record.historical_region.name
                    if record.historical_region
                    else "",
                    "комментарий": record.notes or "",
                }
            )

        filename = f"selected_fuel_records_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"

        if format_type == "csv":
            return ExportService.export_to_csv(fuel_data, filename)
        elif format_type == "xlsx":
            return ExportService.export_to_excel(fuel_data, filename)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    @staticmethod
    def export_cars_data(format_type: str = "csv") -> HttpResponse:
        """Экспорт данных об автомобилях"""
        # Получаем выбранные автомобили с оптимизацией
        queryset = Car.objects.select_related("region")

        cars_data = []
        for record in queryset.iterator(chunk_size=1000):
            cars_data.append(
                {
                    "код (Элемент)": record.code if record.code else "",
                    "модель авто": record.model if record.model else "",
                    "госномер": record.state_number
                    if record.state_number
                    else "",
                    "VIN": record.vin if record.vin else "",
                    "год выпуска": record.manufacture_year
                    if record.manufacture_year
                    else "",
                    "ИНН владельца": record.owner_inn
                    if record.owner_inn
                    else "",
                    "подразделение": record.department
                    if record.department
                    else "",
                    "регион": record.region.name if record.region else "",
                    "активно": "Да" if record.is_active else "Нет",
                    "статус": record.status if record.status else "",
                }
            )

        filename = f"cars_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"

        if format_type == "csv":
            return ExportService.export_to_csv(cars_data, filename)
        elif format_type == "xlsx":
            return ExportService.export_to_excel(cars_data, filename)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    @staticmethod
    def export_selected_cars(
        selected_ids: List[int], format_type: str = "csv"
    ) -> HttpResponse:
        """Экспорт выбранных автомобилей с читаемыми значениями"""
        # Получаем выбранные автомобили с оптимизацией
        queryset = Car.objects.filter(id__in=selected_ids).select_related(
            "region"
        )

        cars_data = []
        for record in queryset.iterator(chunk_size=1000):
            cars_data.append(
                {
                    "код (Элемент)": record.code if record.code else "",
                    "модель авто": record.model if record.model else "",
                    "госномер": record.state_number
                    if record.state_number
                    else "",
                    "VIN": record.vin if record.vin else "",
                    "год выпуска": record.manufacture_year
                    if record.manufacture_year
                    else "",
                    "ИНН владельца": record.owner_inn
                    if record.owner_inn
                    else "",
                    "подразделение": record.department
                    if record.department
                    else "",
                    "регион": record.region.name if record.region else "",
                    "активно": "Да" if record.is_active else "Нет",
                    "статус": record.status if record.status else "",
                }
            )

        filename = f"selected_cars_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"

        if format_type == "csv":
            return ExportService.export_to_csv(cars_data, filename)
        elif format_type == "xlsx":
            return ExportService.export_to_excel(cars_data, filename)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

        return ExportService.export_to_excel(cars_data, filename)
