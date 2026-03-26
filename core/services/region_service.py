from typing import Any, Dict, List

from django.db import transaction
from django.db.models import Count, Q

from core.models import Car, Region


class RegionService:
    """Сервис для бизнес-логики работы с регионами"""

    @staticmethod
    def get_regions_statistics():
        """Статистика по регионам"""
        stats = Region.objects.aggregate(
            total_regions=Count("id"),
            active_regions=Count("id", filter=Q(active=True)),
            archived_regions=Count("id", filter=Q(active=False)),
            regions_with_cars=Count("id", filter=Q(cars__isnull=False)),
            regions_with_active_cars=Count(
                "id", filter=Q(cars__is_active=True)
            ),
        )

        # Детальная статистика по автомобилям
        car_stats = Car.objects.aggregate(
            total_cars=Count("id"),
            cars_with_region=Count("id", filter=Q(region__isnull=False)),
            cars_without_region=Count("id", filter=Q(region__isnull=True)),
        )

        return {**stats, **car_stats}

    @staticmethod
    @transaction.atomic
    def archive_empty_regions(dry_run=False) -> Dict[str, Any]:
        """
        Архивация регионов без активных автомобилей

        Args:
            dry_run: Если True, только подсчет без реальной архивации

        Returns:
            Dict с результатами операции
        """
        empty_regions = Region.objects.can_be_archived()
        regions_to_archive = list(
            empty_regions.values("id", "name", "short_name")
        )

        result = {
            "total_found": len(regions_to_archive),
            "archived": 0,
            "regions": regions_to_archive,
            "dry_run": dry_run,
        }

        if dry_run:
            return result

        # Выполняем архивацию
        if regions_to_archive:
            result["archived"] = empty_regions.update(active=False)

        return result

    @staticmethod
    def find_regions_for_archive() -> List[Dict[str, Any]]:
        """Находит регионы, которые можно архивировать"""
        return list(
            Region.objects.can_be_archived()
            .values("id", "name", "short_name")
            .annotate(
                total_cars=Count("cars"),
                active_cars=Count("cars", filter=Q(cars__is_active=True)),
            )
        )

    @staticmethod
    @transaction.atomic
    def bulk_archive_regions(
        region_ids: List[int], reason: str = "Массовая архивация"
    ) -> int:
        """
        Массовая архивация регионов по ID

        Args:
            region_ids: Список ID регионов для архивации
            reason: Причина архивации

        Returns:
            Количество архивированных регионов
        """
        archived_count = 0

        for region_id in region_ids:
            try:
                region = Region.objects.get(id=region_id)
                if region.can_be_archived:
                    region.archive(reason)
                    archived_count += 1
                else:
                    print(
                        f"⚠️ Пропущен регион {region.name}: есть активные автомобили"
                    )
            except Region.DoesNotExist:
                print(f"❌ Регион с ID {region_id} не найден")
            except ValueError as e:
                print(f"❌ Ошибка архивации региона {region_id}: {e}")

        return archived_count

    @staticmethod
    @transaction.atomic
    def bulk_restore_regions(region_ids: List[int]) -> int:
        """
        Массовое восстановление регионов из архива

        Args:
            region_ids: Список ID регионов для восстановления

        Returns:
            Количество восстановленных регионов
        """
        restored_count = 0

        for region_id in region_ids:
            try:
                region = Region.objects.get(id=region_id)
                if not region.active:
                    region.restore()
                    restored_count += 1
            except Region.DoesNotExist:
                print(f"❌ Регион с ID {region_id} не найден")

        return restored_count

    @staticmethod
    def get_region_health_report() -> Dict[str, Any]:
        """Отчет о состоянии регионов"""
        regions = Region.objects.with_cars_count()

        healthy_regions = regions.filter(active=True, active_cars__gt=0)
        empty_active_regions = regions.filter(active=True, active_cars=0)
        archived_regions = regions.filter(active=False)

        return {
            "total_regions": regions.count(),
            "healthy_regions": {
                "count": healthy_regions.count(),
                "examples": list(
                    healthy_regions.values("id", "name", "active_cars")[:5]
                ),
            },
            "empty_active_regions": {
                "count": empty_active_regions.count(),
                "list": list(
                    empty_active_regions.values(
                        "id", "name", "total_cars", "active_cars"
                    )
                ),
            },
            "archived_regions": {
                "count": archived_regions.count(),
                "examples": list(
                    archived_regions.values("id", "name", "total_cars")[:5]
                ),
            },
        }

    @staticmethod
    def archive_empty_regions_simple():
        """Простая архивация пустых регионов без подтверждения"""
        empty_regions = Region.objects.can_be_archived()
        count = empty_regions.count()

        if count > 0:
            empty_regions.update(active=False)
            print(
                f"📦 Автоматически архивировано {count} регионов без активных автомобилей"
            )

        return count
