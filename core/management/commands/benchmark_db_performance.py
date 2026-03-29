import statistics
from datetime import timedelta
from time import perf_counter

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import FuelRecord, Region, SystemLog, User


class Command(BaseCommand):
    help = "Бенчмарк ключевых DB-запросов API отчетов"

    def add_arguments(self, parser):
        parser.add_argument(
            "--iterations",
            type=int,
            default=5,
            help="Количество прогонов на сценарий (default: 5)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Глубина периода в днях (default: 30)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Размер страницы для records (default: 50)",
        )

    def handle(self, *args, **options):
        iterations = max(1, options["iterations"])
        days = max(1, options["days"])
        page_limit = max(1, min(options["limit"], 200))

        now = timezone.now()
        from_dt = now - timedelta(days=days)
        to_dt = now

        self.stdout.write("DB performance benchmark")
        self.stdout.write("=" * 60)
        self.stdout.write(
            f"Params: iterations={iterations}, days={days}, limit={page_limit}"
        )
        self.stdout.write("")

        base_qs = FuelRecord.objects.active_for_reports().with_related_data().filter(
            filled_at__gte=from_dt,
            filled_at__lt=to_dt,
        )
        base_qs_filters_only = FuelRecord.objects.active_for_reports().filter(
            filled_at__gte=from_dt,
            filled_at__lt=to_dt,
        )
        total_records = base_qs.count()
        deep_offset = max(0, total_records - page_limit)

        scenarios = [
            (
                "reports.summary (aggregate)",
                lambda: base_qs.fuel_statistics(),
            ),
            (
                "reports.filters (emp/region ids + User/Region)",
                lambda: Command._bench_reports_filters_like_api(
                    base_qs_filters_only,
                ),
            ),
            (
                "reports.records first page (offset=0)",
                lambda: list(
                    base_qs.order_by("-filled_at", "-id")[:page_limit]
                ),
            ),
            (
                f"reports.records deep page (offset={deep_offset})",
                lambda: list(
                    base_qs.order_by("-filled_at", "-id")[
                        deep_offset : deep_offset + page_limit
                    ]
                ),
            ),
            (
                "reports.records cursor-like next page",
                lambda: self._cursor_like_page(base_qs, page_limit),
            ),
            (
                "reports.access-events",
                lambda: list(
                    SystemLog.objects.filter(action__startswith="access_")
                    .select_related("user")
                    .order_by("-created_at")[:page_limit]
                ),
            ),
        ]

        for name, fn in scenarios:
            stats = self._measure(fn, iterations)
            self.stdout.write(
                f"{name:<45} "
                f"avg={stats['avg_ms']:>8.2f} ms  "
                f"p95={stats['p95_ms']:>8.2f} ms  "
                f"min={stats['min_ms']:>8.2f} ms  "
                f"max={stats['max_ms']:>8.2f} ms"
            )

        self.stdout.write("")
        self.stdout.write(
            "Hint: compare this report before/after changes and "
            "on a production-like data snapshot."
        )
        self.stdout.write(
            "Note: deep offset scales poorly; prefer cursor pagination "
            "for large journals."
        )

    @staticmethod
    def _bench_reports_filters_like_api(qs):
        """Как /api/v1/reports/filters: DISTINCT по id, затем User/Region."""
        employee_ids = list(
            qs.filter(employee_id__isnull=False)
            .values_list("employee_id", flat=True)
            .distinct()
        )
        if employee_ids:
            list(
                User.objects.filter(pk__in=employee_ids).values_list(
                    "first_name",
                    "last_name",
                    "username",
                ),
            )
        hist_ids = list(
            qs.exclude(historical_region_id__isnull=True)
            .values_list("historical_region_id", flat=True)
            .distinct()
        )
        car_reg_ids = list(
            qs.filter(car__region_id__isnull=False)
            .values_list("car__region_id", flat=True)
            .distinct()
        )
        region_pks = set(hist_ids) | set(car_reg_ids)
        if region_pks:
            list(Region.objects.filter(pk__in=region_pks).values_list("name", flat=True))

    @staticmethod
    def _measure(fn, iterations: int) -> dict:
        samples = []
        for _ in range(iterations):
            started = perf_counter()
            fn()
            elapsed_ms = (perf_counter() - started) * 1000
            samples.append(elapsed_ms)

        avg_ms = statistics.fmean(samples)
        p95_ms = (
            max(samples)
            if len(samples) < 2
            else sorted(samples)[int(0.95 * (len(samples) - 1))]
        )
        return {
            "avg_ms": avg_ms,
            "p95_ms": p95_ms,
            "min_ms": min(samples),
            "max_ms": max(samples),
        }

    @staticmethod
    def _cursor_like_page(base_qs, page_limit: int):
        first_page = list(base_qs.order_by("-filled_at", "-id")[:page_limit])
        if not first_page:
            return []

        last = first_page[-1]
        return list(
            base_qs.filter(
                Q(filled_at__lt=last.filled_at)
                | Q(filled_at=last.filled_at, id__lt=last.id)
            ).order_by("-filled_at", "-id")[:page_limit]
        )
