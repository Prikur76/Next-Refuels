import csv
from pathlib import Path
from typing import Any

from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.color import no_style
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils.dateparse import parse_datetime

from core.models import Car, FuelRecord, Region, User


BOOL_TRUE = {"t", "true", "1", "yes", "y"}


class Command(BaseCommand):
    help = "Импорт дампа CSV из refuel_db в таблицы проекта"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--path",
            default="refuel_db",
            help="Путь к директории с CSV (default: refuel_db)",
        )
        parser.add_argument(
            "--truncate",
            action="store_true",
            help="Очистить таблицы перед импортом",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Проверить дамп без записи в БД",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Размер пачки для bulk_create (default: 1000)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        base_path = Path(options["path"]).resolve()
        truncate = bool(options["truncate"])
        dry_run = bool(options["dry_run"])
        batch_size = max(1, int(options["batch_size"]))

        self._validate_files_exist(base_path)

        regions_rows = self._read_csv(base_path / "regions.csv")
        users_rows = self._read_csv(base_path / "users.csv")
        cars_rows = self._read_csv(base_path / "cars.csv")
        fuel_rows = self._read_csv(base_path / "fuel_records.csv")
        content_types_rows = self._read_csv_optional(
            base_path / "django_content_type.csv"
        )
        permissions_rows = self._read_csv_optional(base_path / "auth_permission.csv")
        groups_rows = self._read_csv_optional(base_path / "auth_group.csv")
        groups_permissions_rows = self._read_csv_optional(
            base_path / "auth_group_permissions.csv"
        )
        users_groups_rows = self._read_csv_optional(base_path / "users_groups.csv")
        users_permissions_rows = self._read_csv_optional(
            base_path / "users_user_permissions.csv"
        )

        self.stdout.write(self.style.NOTICE("Найдены CSV-файлы:"))
        self.stdout.write(f"- regions: {len(regions_rows)}")
        self.stdout.write(f"- users: {len(users_rows)}")
        self.stdout.write(f"- cars: {len(cars_rows)}")
        self.stdout.write(f"- fuel_records: {len(fuel_rows)}")
        self.stdout.write(f"- django_content_type: {len(content_types_rows)}")
        self.stdout.write(f"- auth_permission: {len(permissions_rows)}")
        self.stdout.write(f"- auth_group: {len(groups_rows)}")
        self.stdout.write(
            f"- auth_group_permissions: {len(groups_permissions_rows)}"
        )
        self.stdout.write(f"- users_groups: {len(users_groups_rows)}")
        self.stdout.write(f"- users_user_permissions: {len(users_permissions_rows)}")

        self._validate_csv_relations(
            regions_rows=regions_rows,
            users_rows=users_rows,
            cars_rows=cars_rows,
            fuel_rows=fuel_rows,
            content_types_rows=content_types_rows,
            permissions_rows=permissions_rows,
            groups_rows=groups_rows,
            groups_permissions_rows=groups_permissions_rows,
            users_groups_rows=users_groups_rows,
            users_permissions_rows=users_permissions_rows,
        )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    "Dry-run успешно завершён. Данные консистентны."
                )
            )
            return

        with transaction.atomic():
            if truncate:
                self.stdout.write("Очистка таблиц...")
                User.user_permissions.through.objects.all().delete()
                User.groups.through.objects.all().delete()
                Group.permissions.through.objects.all().delete()
                FuelRecord.objects.all().delete()
                Car.objects.all().delete()
                User.objects.all().delete()
                Group.objects.all().delete()
                Permission.objects.all().delete()
                ContentType.objects.all().delete()
                Region.objects.all().delete()
            else:
                self._assert_tables_empty()

            self._import_regions(regions_rows, batch_size=batch_size)
            self._import_users(users_rows, batch_size=batch_size)
            self._import_content_types(content_types_rows, batch_size=batch_size)
            self._import_permissions(permissions_rows, batch_size=batch_size)
            self._import_groups(groups_rows, batch_size=batch_size)
            self._import_group_permissions(
                groups_permissions_rows,
                batch_size=batch_size,
            )
            self._import_user_groups(users_groups_rows, batch_size=batch_size)
            self._import_user_permissions(
                users_permissions_rows,
                batch_size=batch_size,
            )
            self._sync_superusers_with_admin_group()
            self._import_cars(cars_rows, batch_size=batch_size)
            self._import_fuel_records(fuel_rows, batch_size=batch_size)

            self._reset_sequences()

        self.stdout.write(self.style.SUCCESS("Импорт успешно завершён."))

    def _validate_files_exist(self, base_path: Path) -> None:
        if not base_path.exists() or not base_path.is_dir():
            raise CommandError(f"Директория не найдена: {base_path}")

        expected = [
            "regions.csv",
            "users.csv",
            "cars.csv",
            "fuel_records.csv",
        ]
        missing = [name for name in expected if not (base_path / name).exists()]
        if missing:
            raise CommandError(
                "Не найдены обязательные файлы: " + ", ".join(missing)
            )

    @staticmethod
    def _read_csv_optional(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []
        return Command._read_csv(path)

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                clean_row: dict[str, str] = {}
                for key, value in raw_row.items():
                    clean_key = (key or "").strip()
                    clean_value = (value or "").strip()
                    clean_row[clean_key] = clean_value
                rows.append(clean_row)
        return rows

    @staticmethod
    def _parse_bool(raw: str, default: bool = False) -> bool:
        if raw == "":
            return default
        return raw.strip().lower() in BOOL_TRUE

    @staticmethod
    def _parse_int_nullable(raw: str) -> int | None:
        return int(raw) if raw else None

    @staticmethod
    def _parse_datetime_nullable(raw: str):
        if not raw:
            return None
        parsed = parse_datetime(raw)
        if parsed is None:
            raise CommandError(f"Некорректный datetime: {raw}")
        return parsed

    def _assert_tables_empty(self) -> None:
        non_empty = []
        if Region.objects.exists():
            non_empty.append("regions")
        if User.objects.exists():
            non_empty.append("users")
        if Car.objects.exists():
            non_empty.append("cars")
        if FuelRecord.objects.exists():
            non_empty.append("fuel_records")
        if Group.objects.exists():
            non_empty.append("auth_group")
        if Permission.objects.exists():
            non_empty.append("auth_permission")
        if ContentType.objects.exists():
            non_empty.append("django_content_type")
        if User.groups.through.objects.exists():
            non_empty.append("users_groups")
        if User.user_permissions.through.objects.exists():
            non_empty.append("users_user_permissions")
        if non_empty:
            raise CommandError(
                "Таблицы не пустые: "
                + ", ".join(non_empty)
                + ". Используйте --truncate."
            )

    def _validate_csv_relations(
        self,
        *,
        regions_rows: list[dict[str, str]],
        users_rows: list[dict[str, str]],
        cars_rows: list[dict[str, str]],
        fuel_rows: list[dict[str, str]],
        content_types_rows: list[dict[str, str]],
        permissions_rows: list[dict[str, str]],
        groups_rows: list[dict[str, str]],
        groups_permissions_rows: list[dict[str, str]],
        users_groups_rows: list[dict[str, str]],
        users_permissions_rows: list[dict[str, str]],
    ) -> None:
        region_ids = {row["id"] for row in regions_rows}
        user_ids = {row["id"] for row in users_rows}
        car_ids = {row["id"] for row in cars_rows}
        content_type_ids = {row["id"] for row in content_types_rows}
        permission_ids = {row["id"] for row in permissions_rows}
        group_ids = {row["id"] for row in groups_rows}

        def ensure_fk(
            rows: list[dict[str, str]],
            fk_name: str,
            allowed_ids: set[str],
            label: str,
        ) -> None:
            invalid = [
                row["id"]
                for row in rows
                if row.get(fk_name) and row[fk_name] not in allowed_ids
            ]
            if invalid:
                sample = ", ".join(invalid[:5])
                raise CommandError(
                    f"Нарушение FK {label}: {len(invalid)} строк. "
                    f"Примеры id: {sample}"
                )

        ensure_fk(users_rows, "region_id", region_ids, "users.region_id")
        ensure_fk(cars_rows, "region_id", region_ids, "cars.region_id")
        ensure_fk(fuel_rows, "car_id", car_ids, "fuel_records.car_id")
        ensure_fk(
            fuel_rows,
            "employee_id",
            user_ids,
            "fuel_records.employee_id",
        )
        ensure_fk(
            fuel_rows,
            "historical_region_id",
            region_ids,
            "fuel_records.historical_region_id",
        )
        ensure_fk(
            permissions_rows,
            "content_type_id",
            content_type_ids,
            "auth_permission.content_type_id",
        )
        ensure_fk(
            groups_permissions_rows,
            "group_id",
            group_ids,
            "auth_group_permissions.group_id",
        )
        ensure_fk(
            groups_permissions_rows,
            "permission_id",
            permission_ids,
            "auth_group_permissions.permission_id",
        )
        ensure_fk(
            users_groups_rows,
            "user_id",
            user_ids,
            "users_groups.user_id",
        )
        ensure_fk(
            users_groups_rows,
            "group_id",
            group_ids,
            "users_groups.group_id",
        )
        ensure_fk(
            users_permissions_rows,
            "user_id",
            user_ids,
            "users_user_permissions.user_id",
        )
        ensure_fk(
            users_permissions_rows,
            "permission_id",
            permission_ids,
            "users_user_permissions.permission_id",
        )

    def _import_regions(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        objects = [
            Region(
                id=int(row["id"]),
                name=row["name"],
                short_name=row.get("short_name", ""),
                active=self._parse_bool(row.get("active", "t"), default=True),
            )
            for row in rows
        ]
        Region.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(f"Импортировано regions: {len(rows)}"))

    def _import_users(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        objects = []
        for row in rows:
            # zone_id в CSV присутствует, но поле удалено из текущей модели.
            user = User(
                id=int(row["id"]),
                password=row["password"],
                last_login=self._parse_datetime_nullable(row.get("last_login", "")),
                is_superuser=self._parse_bool(
                    row.get("is_superuser", "f"), default=False
                ),
                username=row["username"],
                email=row.get("email", ""),
                is_staff=self._parse_bool(row.get("is_staff", "f"), default=False),
                date_joined=self._parse_datetime_nullable(
                    row.get("date_joined", "")
                ),
                telegram_id=self._parse_int_nullable(row.get("telegram_id", "")),
                first_name=row.get("first_name", "") or None,
                last_name=row.get("last_name", "") or None,
                phone=row.get("phone", "") or None,
                is_active=self._parse_bool(row.get("is_active", "t"), default=True),
                region_id=self._parse_int_nullable(row.get("region_id", "")),
            )
            objects.append(user)

        User.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(f"Импортировано users: {len(rows)}"))

    def _import_cars(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        objects = []
        for row in rows:
            car = Car(
                id=int(row["id"]),
                code=row["code"],
                vin=row.get("vin", ""),
                state_number=row["state_number"],
                model=row["model"],
                manufacture_year=int(row["manufacture_year"]),
                owner_inn=row.get("owner_inn", ""),
                department=row.get("department", "") or None,
                is_active=self._parse_bool(row.get("is_active", "t"), default=True),
                status=row.get("status", ""),
                created_at=self._parse_datetime_nullable(row.get("created_at", "")),
                updated_at=self._parse_datetime_nullable(row.get("updated_at", "")),
                region_id=self._parse_int_nullable(row.get("region_id", "")),
            )
            objects.append(car)

        Car.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(f"Импортировано cars: {len(rows)}"))

    def _import_content_types(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        if not rows:
            return
        objects = [
            ContentType(
                id=int(row["id"]),
                app_label=row["app_label"],
                model=row["model"],
            )
            for row in rows
        ]
        ContentType.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(f"Импортировано django_content_type: {len(rows)}")
        )

    def _import_permissions(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        if not rows:
            return
        objects = [
            Permission(
                id=int(row["id"]),
                name=row["name"],
                content_type_id=int(row["content_type_id"]),
                codename=row["codename"],
            )
            for row in rows
        ]
        Permission.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(f"Импортировано auth_permission: {len(rows)}")
        )

    def _import_groups(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        if not rows:
            return
        objects = [
            Group(
                id=int(row["id"]),
                name=row["name"],
            )
            for row in rows
        ]
        Group.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(f"Импортировано auth_group: {len(rows)}"))

    def _import_group_permissions(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        if not rows:
            return
        through_model = Group.permissions.through
        objects = [
            through_model(
                id=int(row["id"]),
                group_id=int(row["group_id"]),
                permission_id=int(row["permission_id"]),
            )
            for row in rows
        ]
        through_model.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(f"Импортировано auth_group_permissions: {len(rows)}")
        )

    def _import_user_groups(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        if not rows:
            return
        through_model = User.groups.through
        objects = [
            through_model(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                group_id=int(row["group_id"]),
            )
            for row in rows
        ]
        through_model.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(self.style.SUCCESS(f"Импортировано users_groups: {len(rows)}"))

    def _import_user_permissions(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        if not rows:
            return
        through_model = User.user_permissions.through
        objects = [
            through_model(
                id=int(row["id"]),
                user_id=int(row["user_id"]),
                permission_id=int(row["permission_id"]),
            )
            for row in rows
        ]
        through_model.objects.bulk_create(objects, batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                f"Импортировано users_user_permissions: {len(rows)}"
            )
        )

    def _sync_superusers_with_admin_group(self) -> None:
        admin_group, _ = Group.objects.get_or_create(name="Администратор")
        superusers = User.objects.filter(is_superuser=True)
        count = 0
        for user in superusers:
            user.groups.add(admin_group)
            count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Суперпользователей добавлено в группу "
                f"'Администратор': {count}"
            )
        )

    def _import_fuel_records(
        self,
        rows: list[dict[str, str]],
        *,
        batch_size: int,
    ) -> None:
        objects = []
        for row in rows:
            record = FuelRecord(
                id=int(row["id"]),
                liters=row["liters"],
                fuel_type=row["fuel_type"],
                filled_at=self._parse_datetime_nullable(row["filled_at"]),
                source=row["source"],
                notes=row.get("notes", ""),
                historical_department=(
                    row.get("historical_department", "") or None
                ),
                created_at=self._parse_datetime_nullable(row.get("created_at", "")),
                updated_at=self._parse_datetime_nullable(row.get("updated_at", "")),
                car_id=int(row["car_id"]),
                employee_id=self._parse_int_nullable(row.get("employee_id", "")),
                historical_region_id=self._parse_int_nullable(
                    row.get("historical_region_id", "")
                ),
            )
            objects.append(record)

        try:
            FuelRecord.objects.bulk_create(objects, batch_size=batch_size)
        except IntegrityError as exc:
            raise CommandError(f"Ошибка импорта fuel_records: {exc}") from exc
        self.stdout.write(
            self.style.SUCCESS(f"Импортировано fuel_records: {len(rows)}")
        )

    def _reset_sequences(self) -> None:
        self.stdout.write("Синхронизация sequence...")
        statements = connection.ops.sequence_reset_sql(
            style=no_style(),
            model_list=[
                Region,
                ContentType,
                Permission,
                Group,
                User,
                Group.permissions.through,
                User.groups.through,
                User.user_permissions.through,
                Car,
                FuelRecord,
            ],
        )
        with connection.cursor() as cursor:
            for statement in statements:
                if statement:
                    cursor.execute(statement)
