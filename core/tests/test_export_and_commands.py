from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

from django.core.management import call_command
from django.http import HttpResponse
from django.test import Client, TestCase
from django.utils import timezone

from core.management.commands import runbot
from core.management.commands import sync_cars_with_element
from core.models import Car, FuelRecord, Region, SystemLog, User
from core.tests.tests_utils import (
    create_car,
    create_fuel_record,
    create_region,
    create_user,
    login_client,
    patch_json,
    post_json,
)


class ExportViewsScenariosTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.region = create_region(name="Регион A", short_name="A")
        self.manager = create_user(
            username="manager",
            password="pass12345",
            groups=("Менеджер",),
            region=self.region,
        )
        self.fueler = create_user(
            username="fueler",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region,
        )

        self.car = create_car(
            code="CA-EXPORT-1",
            state_number="A111AA77",
            model="Car Export",
            region=self.region,
            department="Dep A",
            is_active=True,
            status="АКТИВЕН",
        )
        self.employee = create_user(
            username="emp1",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region,
            first_name="Иван",
            last_name="Иванов",
            phone="+79000000001",
        )

        create_fuel_record(
            car=self.car,
            employee=self.employee,
            liters=Decimal("12.34"),
            fuel_type="GASOLINE",
            source="TGBOT",
            notes="note",
            filled_at=timezone.now() - timedelta(days=1),
        )

    def test_export_reports_csv_requires_login(self):
        resp = self.client.get("/api/v1/reports/export/csv/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])

    def test_export_reports_csv_denied_for_fueler(self):
        login_client(
            self.client, username=self.fueler.username, password="pass12345"
        )
        resp = self.client.get("/api/v1/reports/export/csv/")
        self.assertEqual(resp.status_code, 403)

    def test_export_reports_csv_ok_for_manager(self):
        login_client(
            self.client,
            username=self.manager.username,
            password="pass12345",
        )
        resp = self.client.get("/api/v1/reports/export/csv/?limit=1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertGreater(len(resp.content), 10)

    def test_export_reports_xlsx_ok_for_manager(self):
        login_client(
            self.client,
            username=self.manager.username,
            password="pass12345",
        )
        resp = self.client.get("/api/v1/reports/export/xlsx/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resp["Content-Type"],
        )
        self.assertGreater(len(resp.content), 1000)


class AccessManagementAndAdditionalApiScenariosTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.region_a = create_region(name="Регион A", short_name="A")
        self.region_b = create_region(name="Регион B", short_name="B")

        self.manager = create_user(
            username="manager_a",
            password="pass12345",
            groups=("Менеджер",),
            region=self.region_a,
        )
        self.admin = create_user(
            username="admin",
            password="pass12345",
            groups=("Администратор",),
            region=self.region_b,
        )
        self.fueler = create_user(
            username="fueler_a",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region_a,
        )

        self.target_in_scope = create_user(
            username="fueler_in",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region_a,
        )
        self.target_out_scope = create_user(
            username="fueler_out",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region_b,
        )

    def _login_manager(self):
        login_client(
            self.client, username=self.manager.username, password="pass12345"
        )

    def _login_admin(self):
        login_client(
            self.client, username=self.admin.username, password="pass12345"
        )

    def test_access_regions_for_fueler_denied(self):
        login_client(
            self.client, username=self.fueler.username, password="pass12345"
        )
        resp = self.client.get("/api/v1/access/regions")
        self.assertEqual(resp.status_code, 403)

    def test_access_regions_for_manager_scope(self):
        self._login_manager()
        resp = self.client.get("/api/v1/access/regions")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["name"], self.region_a.name)

    def test_access_regions_for_admin_global(self):
        self._login_admin()
        resp = self.client.get("/api/v1/access/regions")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertGreaterEqual(len(payload), 2)

    def test_manager_can_reset_password_in_scope(self):
        self._login_manager()
        resp = self.client.post(
            f"/api/v1/access/users/{self.target_in_scope.id}/reset-password"
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["id"], self.target_in_scope.id)
        self.assertTrue(payload["temporary_password"])
        refreshed = User.objects.get(id=self.target_in_scope.id)
        self.assertTrue(refreshed.must_change_password)

    def test_manager_cannot_reset_password_out_of_scope(self):
        self._login_manager()
        resp = self.client.post(
            f"/api/v1/access/users/{self.target_out_scope.id}/reset-password"
        )
        self.assertEqual(resp.status_code, 403)

    def test_password_patch_generate_temporary(self):
        self._login_manager()
        resp = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/password",
            data=json.dumps({"generate_temporary": True}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["temporary_password"])

        refreshed = User.objects.get(id=self.target_in_scope.id)
        self.assertTrue(refreshed.must_change_password)

    def test_password_patch_requires_password_or_generate_flag(self):
        self._login_manager()
        resp = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/password",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_password_patch_rejects_too_short_password(self):
        self._login_manager()
        resp = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/password",
            data=json.dumps(
                {"password": "short", "generate_temporary": False}
            ),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_access_scope_patch_allowed_only_for_admin(self):
        self._login_manager()
        resp = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/scope",
            data=json.dumps({"region_id": self.region_b.id}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

        self._login_admin()
        resp2 = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/scope",
            data=json.dumps({"region_id": self.region_b.id}),
            content_type="application/json",
        )
        self.assertEqual(resp2.status_code, 200)
        payload2 = resp2.json()
        self.assertEqual(payload2["region_id"], self.region_b.id)

    def test_access_role_patch_invalid_payload(self):
        self._login_manager()
        resp = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/role",
            data=json.dumps({"role": "МенеджерX"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 422)

    def test_profile_region_id_change_denied_for_manager(self):
        self._login_manager()
        resp = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/profile",
            data=json.dumps({"region_id": self.region_b.id}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_profile_region_id_change_allowed_for_admin(self):
        self._login_admin()
        resp = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/profile",
            data=json.dumps({"region_id": self.region_b.id}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["region_id"], self.region_b.id)


class ManagementCommandsUnitScenariosTests(TestCase):
    def test_sync_cars_with_element_check_only(self):
        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            async def get_sample_data(self, limit: int):
                return [
                    {
                        "Code": "X1",
                        "Number": "A111AA77",
                        "Model": "M1",
                        "INN": "123",
                        "Department": "Dep",
                        "Region": "Регион A",
                        "YearCar": 2020,
                        "Activity": True,
                        "Status": "АКТИВЕН",
                    }
                ][:limit]

            def _map_external_to_internal(self, data: dict):
                return {
                    "code": data["Code"],
                    "state_number": data["Number"],
                    "model": data["Model"],
                    "vin": "",
                    "owner_inn": data["INN"],
                    "department": data["Department"],
                    "region_name": data["Region"],
                    "manufacture_year": 2020,
                    "is_active": data["Activity"],
                    "status": data["Status"],
                }

        with patch(
            "core.management.commands.sync_cars_with_element.ElementCarClient",
            return_value=FakeClient(),
        ):
            call_command("sync_cars_with_element", "--check-only")

    def test_sync_cars_with_element_normal_flow(self):
        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            async def check_availability(self) -> bool:
                return True

            async def sync_with_database(self) -> dict[str, object]:
                return {
                    "created": 1,
                    "updated": 0,
                    "archived": 0,
                    "errors": 0,
                    "regions_created": 0,
                    "regions_updated": 0,
                    "total_processed": 1,
                    "archived_skipped": 0,
                    "restored": 0,
                    "finished_at": "now",
                }

        log_success = AsyncMock()
        log_failure = AsyncMock()
        with patch(
            "core.management.commands.sync_cars_with_element.ElementCarClient",
            return_value=FakeClient(),
        ), patch(
            "core.management.commands.sync_cars_with_element.log_sync_success",
            new=log_success,
        ), patch(
            "core.management.commands.sync_cars_with_element.log_sync_failure",
            new=log_failure,
        ):
            call_command("sync_cars_with_element")

        log_success.assert_awaited()
        log_failure.assert_not_awaited()

    def test_sync_cars_with_element_unavailable_api(self):
        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            async def check_availability(self) -> bool:
                return False

        log_success = AsyncMock()
        log_failure = AsyncMock()
        with patch(
            "core.management.commands.sync_cars_with_element.ElementCarClient",
            return_value=FakeClient(),
        ), patch(
            "core.management.commands.sync_cars_with_element.log_sync_success",
            new=log_success,
        ), patch(
            "core.management.commands.sync_cars_with_element.log_sync_failure",
            new=log_failure,
        ):
            call_command("sync_cars_with_element", "--force")

        log_failure.assert_awaited()
        log_success.assert_not_awaited()

    def test_runbot_calls_run_bot(self):
        with patch(
            "core.management.commands.runbot.run_bot",
            new=Mock(),
        ) as run_bot_mock:
            call_command("runbot")
            run_bot_mock.assert_called_once()

    def test_export_data_writes_files_from_exportservice(self):
        fake_cars = HttpResponse(b"csvdata")
        fake_cars["Content-Disposition"] = 'attachment; filename="cars.csv"'
        fake_fuel = HttpResponse(b"xlsxdata")
        fake_fuel["Content-Disposition"] = 'attachment; filename="fuel.xlsx"'

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "core.management.commands.export_data.ExportService.export_cars_data",
                return_value=fake_cars,
            ), patch(
                "core.management.commands.export_data.ExportService.export_fuel_records_data",
                return_value=fake_fuel,
            ):
                call_command(
                    "export_data",
                    "--model",
                    "cars",
                    "--format",
                    "csv",
                    "--output-dir",
                    tmpdir,
                )

            expected_path = os.path.join(tmpdir, "cars.csv")
            with open(expected_path, "rb") as f:
                content = f.read()
            self.assertEqual(content, b"csvdata")


