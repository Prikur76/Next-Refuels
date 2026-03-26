from django.db import models
from django.db.models import Count, Q


class RegionQuerySet(models.QuerySet):
    """Кастомный QuerySet для модели Region"""

    def active(self):
        """Активные регионы"""
        return self.filter(active=True)

    def archived(self):
        """Архивные регионы"""
        return self.filter(active=False)

    def with_cars_count(self):
        """Регионы с количеством автомобилей"""
        return self.annotate(
            total_cars=Count("cars"),
            active_cars=Count("cars", filter=Q(cars__is_active=True)),
        )

    def without_active_cars(self):
        """Регионы без активных автомобилей"""
        return self.with_cars_count().filter(active_cars=0)

    def with_active_cars(self):
        """Регионы с активными автомобилями"""
        return self.with_cars_count().filter(active_cars__gt=0)

    def can_be_archived(self):
        """Регионы, которые можно архивировать (без активных автомобилей)"""
        return self.active().without_active_cars()

    def archive_empty_regions(self):
        """Архивирует все регионы без активных автомобилей"""
        empty_regions = self.can_be_archived()
        count = empty_regions.count()

        if count > 0:
            empty_regions.update(active=False)

        return count


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Регион")
    short_name = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Краткое имя"
    )
    active = models.BooleanField(default=True, verbose_name="Активен")

    objects = RegionQuerySet.as_manager()

    class Meta:
        db_table = "regions"
        verbose_name = "Регион"
        verbose_name_plural = "Регионы"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def cars_count(self):
        """Количество автомобилей в регионе"""
        return self.cars.count()

    @property
    def active_cars_count(self):
        """Количество активных автомобилей в регионе"""
        return self.cars.filter(is_active=True).count()

    @property
    def can_be_archived(self):
        """Можно ли архивировать регион"""
        return self.active and self.active_cars_count == 0

    def archive(self, reason="Нет активных автомобилей"):
        """Архивация региона"""
        if not self.can_be_archived:
            raise ValueError(
                f"Регион {self.name} нельзя архивировать: есть активные автомобили"
            )

        self.active = False
        self.save(update_fields=["active"])

    def restore(self):
        """Восстановление региона из архива"""
        self.active = True
        self.save(update_fields=["active"])

    def get_cars_statistics(self):
        """Статистика по автомобилям региона"""
        return {
            "total": self.cars_count,
            "active": self.active_cars_count,
            "archived": self.cars_count - self.active_cars_count,
        }
