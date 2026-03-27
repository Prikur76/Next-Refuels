from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone

from core.models import FuelRecord, TelegramLinkToken, User
from core.tests.tests_utils import (
    create_car,
    create_region,
    create_user,
    login_client,
    post_json,
)


class HealthAndAuthScenariosTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.region = create_region(name="Тестовый регион", short_name="TR")

        self.fueler = create_user(
            username="fueler",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region,
        )
        self.manager = create_user(
            username="manager",
            password="pass12345",
            groups=("Менеджер",),
            region=self.region,
        )
        self.admin = create_user(
            username="admin",
            password="pass12345",
            groups=("Администратор",),
            region=self.region,
        )

    def test_healthcheck(self):
        resp = self.client.get("/health/")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["status"], "healthy")

    def test_auth_csrf_anonymous(self):
        resp = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["ok"], True)

    def test_auth_me_requires_auth(self):
        resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_auth_me_returns_groups(self):
        login_client(
            self.client, username=self.manager.username, password="pass12345"
        )
        resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("Менеджер", payload["groups"])
        self.assertEqual(payload["must_change_password"], False)
        self.assertEqual(payload["telegram_linked"], False)

    def test_auth_me_returns_telegram_linked_when_user_has_telegram_id(self):
        self.manager.telegram_id = 123456789
        self.manager.save(update_fields=["telegram_id"])
        login_client(
            self.client, username=self.manager.username, password="pass12345"
        )
        resp = self.client.get("/api/v1/auth/me")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["telegram_linked"], True)

    def test_auth_telegram_link_code_requires_input_role(self):
        self.client.logout()
        login_client(
            self.client,
            username=self.admin.username,
            password="pass12345",
        )
        resp = post_json(
            self.client,
            "/api/v1/auth/telegram/link-code",
            {},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["code"])
        self.assertIn("/start", payload["share_message"])
        self.assertTrue(TelegramLinkToken.objects.filter(user=self.admin).exists())

        another_user = create_user(
            username="outsider",
            password="pass12345",
            groups=(),
            region=self.region,
        )
        login_client(
            self.client,
            username=another_user.username,
            password="pass12345",
        )
        resp = post_json(
            self.client,
            "/api/v1/auth/telegram/link-code",
            {},
        )
        self.assertEqual(resp.status_code, 403)

    def test_auth_password_setup_rejects_when_not_required(self):
        login_client(
            self.client,
            username=self.fueler.username,
            password="pass12345",
        )
        self.fueler.must_change_password = False
        self.fueler.save(update_fields=["must_change_password"])

        resp = post_json(
            self.client,
            "/api/v1/auth/password/setup",
            {"password": "MyFinalPass123", "generate": False},
        )
        self.assertEqual(resp.status_code, 400)

    def test_auth_password_setup_set_valid_password(self):
        self.fueler.must_change_password = True
        self.fueler.save(update_fields=["must_change_password"])

        login_client(
            self.client,
            username=self.fueler.username,
            password="pass12345",
        )
        resp = post_json(
            self.client,
            "/api/v1/auth/password/setup",
            {"password": "MyFinalPass123", "generate": False},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["must_change_password"], False)
        self.assertIsNone(payload["generated_password"])

        refreshed = User.objects.get(id=self.fueler.id)
        self.assertFalse(refreshed.must_change_password)
        self.assertTrue(refreshed.check_password("MyFinalPass123"))

    def test_auth_password_setup_rejects_short_password(self):
        self.fueler.must_change_password = True
        self.fueler.save(update_fields=["must_change_password"])
        login_client(
            self.client,
            username=self.fueler.username,
            password="pass12345",
        )
        resp = post_json(
            self.client,
            "/api/v1/auth/password/setup",
            {"password": "short", "generate": False},
        )
        self.assertEqual(resp.status_code, 400)

    def test_auth_password_setup_generate_temporary_password(self):
        self.fueler.must_change_password = True
        self.fueler.save(update_fields=["must_change_password"])
        login_client(
            self.client,
            username=self.fueler.username,
            password="pass12345",
        )
        resp = post_json(
            self.client,
            "/api/v1/auth/password/setup",
            {"generate": True},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["must_change_password"], False)
        self.assertTrue(payload["generated_password"])


class CarsAndFuelRecordScenariosTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.region = create_region(name="Регион A", short_name="A")
        self.other_region = create_region(name="Регион B", short_name="B")

        self.fueler = create_user(
            username="fueler",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region,
        )
        self.manager = create_user(
            username="manager",
            password="pass12345",
            groups=("Менеджер",),
            region=self.region,
        )

        self.car_active = create_car(
            code="C-001",
            state_number="A123BC77",
            model="Test Car",
            region=self.region,
            department="Dep A",
            is_active=True,
            status="АКТИВЕН",
        )
        self.car_inactive = create_car(
            code="C-002",
            state_number="B222BB77",
            model="Inactive Car",
            region=self.region,
            department="Dep A",
            is_active=False,
            status="АРХИВ",
        )
        self.car_no_region = create_car(
            code="C-003",
            state_number="C333CC77",
            model="No Region Car",
            region=None,
            department="Dep A",
            is_active=True,
            status="АКТИВЕН",
        )
        self.car_other_region = create_car(
            code="C-004",
            state_number="D444DD77",
            model="Other Region Car",
            region=self.other_region,
            department="Dep B",
            is_active=True,
            status="АКТИВЕН",
        )

        login_client(
            self.client, username=self.fueler.username, password="pass12345"
        )

    def test_cars_requires_auth_and_input_role(self):
        client2 = Client()
        resp = client2.get("/api/v1/cars")
        self.assertEqual(resp.status_code, 401)

        outsider = create_user(
            username="outsider",
            password="pass12345",
            groups=(),
            region=self.region,
        )
        login_client(
            client2,
            username=outsider.username,
            password="pass12345",
        )
        resp = client2.get("/api/v1/cars")
        self.assertEqual(resp.status_code, 403)

    def test_cars_search_and_limit(self):
        resp = self.client.get("/api/v1/cars?query=A123&limit=5")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["state_number"], "A123BC77")

        resp2 = self.client.get("/api/v1/cars?limit=1000")
        self.assertEqual(resp2.status_code, 200)
        payload2 = resp2.json()
        state_numbers = {c["state_number"] for c in payload2}
        self.assertIn("A123BC77", state_numbers)
        self.assertIn("D444DD77", state_numbers)
        self.assertNotIn("B222BB77", state_numbers)
        self.assertNotIn("C333CC77", state_numbers)

    def test_cars_limit_is_clamped(self):
        create_car(
            code="C-005",
            state_number="E555EE77",
            model="Car 2",
            region=self.region,
            department="Dep A",
        )
        create_car(
            code="C-006",
            state_number="F666FF77",
            model="Car 3",
            region=self.region,
            department="Dep A",
        )
        resp = self.client.get("/api/v1/cars?limit=1")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(len(payload), 1)

    def test_create_fuel_record_invalid_liters(self):
        resp = post_json(
            self.client,
            "/api/v1/fuel-records",
            {
                "car_id": self.car_active.id,
                "liters": "-1",
                "fuel_type": "GASOLINE",
                "source": "TGBOT",
                "notes": "bad liters",
            },
        )
        self.assertEqual(resp.status_code, 400)

        resp = post_json(
            self.client,
            "/api/v1/fuel-records",
            {
                "car_id": self.car_active.id,
                "liters": "not-a-number",
                "fuel_type": "GASOLINE",
                "source": "TGBOT",
                "notes": "bad liters format",
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_fuel_record_requires_auth(self):
        client2 = Client()
        resp = post_json(
            client2,
            "/api/v1/fuel-records",
            {
                "car_id": self.car_active.id,
                "liters": "10.5",
                "fuel_type": "GASOLINE",
                "source": "TGBOT",
                "notes": "unauth",
            },
        )
        self.assertEqual(resp.status_code, 401)

    def test_create_fuel_record_invalid_fuel_type(self):
        resp = post_json(
            self.client,
            "/api/v1/fuel-records",
            {
                "car_id": self.car_active.id,
                "liters": "10.5",
                "fuel_type": "OIL",
                "source": "TGBOT",
                "notes": "bad fuel_type",
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_fuel_record_invalid_source(self):
        resp = post_json(
            self.client,
            "/api/v1/fuel-records",
            {
                "car_id": self.car_active.id,
                "liters": "10.5",
                "fuel_type": "GASOLINE",
                "source": "UNKNOWN",
                "notes": "bad source",
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_create_fuel_record_car_must_be_active(self):
        resp = post_json(
            self.client,
            "/api/v1/fuel-records",
            {
                "car_id": self.car_inactive.id,
                "liters": "10.5",
                "fuel_type": "GASOLINE",
                "source": "TGBOT",
                "notes": "inactive car",
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_recent_requires_input_role(self):
        client2 = Client()
        outsider = create_user(
            username="outsider2",
            password="pass12345",
            groups=(),
            region=self.region,
        )
        login_client(
            client2,
            username=outsider.username,
            password="pass12345",
        )
        resp = client2.get("/api/v1/fuel-records/recent?limit=1")
        self.assertEqual(resp.status_code, 403)

    def test_create_fuel_record_success(self):
        resp = post_json(
            self.client,
            "/api/v1/fuel-records",
            {
                "car_id": self.car_active.id,
                "liters": "45.50",
                "fuel_type": "GASOLINE",
                "source": "TGBOT",
                "notes": "api test",
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["car_id"], self.car_active.id)
        self.assertEqual(payload["source"], "TGBOT")
        self.assertEqual(payload["fuel_type"], "GASOLINE")
        self.assertAlmostEqual(float(payload["liters"]), 45.5, places=2)
        self.assertTrue(FuelRecord.objects.exists())

    def test_recent_fuel_records_limit_and_order(self):
        older = timezone.now() - timedelta(days=2)
        newer = timezone.now() - timedelta(hours=2)
        FuelRecord.objects.create_fuel_record(
            car=self.car_active,
            employee=self.fueler,
            liters=Decimal("10.00"),
            fuel_type="GASOLINE",
            source="TGBOT",
            notes="old",
            filled_at=older,
        )
        FuelRecord.objects.create_fuel_record(
            car=self.car_active,
            employee=self.fueler,
            liters=Decimal("20.00"),
            fuel_type="DIESEL",
            source="CARD",
            notes="new",
            filled_at=newer,
        )

        resp = self.client.get("/api/v1/fuel-records/recent?limit=1")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(len(payload), 1)
        self.assertAlmostEqual(float(payload[0]["liters"]), 20.0, places=2)
        self.assertEqual(payload[0]["fuel_type"], "DIESEL")

        resp2 = self.client.get("/api/v1/fuel-records/recent?limit=1000")
        self.assertEqual(resp2.status_code, 200)
        self.assertLessEqual(len(resp2.json()), 100)


class ReportsAccessAndAnalyticsScenariosTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.region = create_region(name="Регион A", short_name="A")
        self.other_region = create_region(name="Регион B", short_name="B")

        self.fueler = create_user(
            username="fueler",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region,
        )
        self.manager = create_user(
            username="manager",
            password="pass12345",
            groups=("Менеджер",),
            region=self.region,
        )
        self.admin = create_user(
            username="admin",
            password="pass12345",
            groups=("Администратор",),
            region=self.other_region,
        )

        self.car_a = create_car(
            code="CA-1",
            state_number="A111AA77",
            model="Car A",
            region=self.region,
            department="Dep A",
        )
        self.car_b = create_car(
            code="CB-1",
            state_number="B222BB77",
            model="Car B",
            region=self.other_region,
            department="Dep B",
        )

        self.employee1 = create_user(
            username="emp1",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region,
            first_name="Иван",
            last_name="Иванов",
            phone="+79000000001",
        )
        self.employee2 = create_user(
            username="emp2",
            password="pass12345",
            groups=("Заправщик",),
            region=self.region,
            first_name="Петр",
            last_name="Петров",
            phone="+79000000002",
        )

        today = timezone.now().date()
        d1 = today - timedelta(days=10)
        d2 = today - timedelta(days=5)

        FuelRecord.objects.create_fuel_record(
            car=self.car_a,
            employee=self.employee1,
            liters=Decimal("10.00"),
            fuel_type="GASOLINE",
            source="TGBOT",
            notes="r1",
            filled_at=timezone.make_aware(datetime.combine(d1, datetime.min.time())),
        )
        FuelRecord.objects.create_fuel_record(
            car=self.car_a,
            employee=self.employee2,
            liters=Decimal("40.00"),
            fuel_type="DIESEL",
            source="CARD",
            notes="r2",
            filled_at=timezone.make_aware(datetime.combine(d2, datetime.min.time())),
        )
        FuelRecord.objects.create_fuel_record(
            car=self.car_b,
            employee=self.employee2,
            liters=Decimal("5.00"),
            fuel_type="GASOLINE",
            source="TRUCK",
            notes="r3",
            filled_at=timezone.make_aware(datetime.combine(d2, datetime.min.time())),
        )

        from core.models import SystemLog

        SystemLog.objects.create(
            user=self.manager,
            action="access_user_create",
            details="test",
            ip_address="127.0.0.1",
        )
        SystemLog.objects.create(
            user=self.fueler,
            action="access_scope_change",
            details="test",
            ip_address="127.0.0.1",
        )

    def _login_as_manager(self):
        login_client(
            self.client, username=self.manager.username, password="pass12345"
        )

    def _login_as_admin(self):
        login_client(
            self.client, username=self.admin.username, password="pass12345"
        )

    def _login_as_fueler(self):
        login_client(
            self.client, username=self.fueler.username, password="pass12345"
        )

    def test_reports_summary_requires_reports_group(self):
        self._login_as_fueler()
        resp = self.client.get("/api/v1/reports/summary")
        self.assertEqual(resp.status_code, 403)

    def test_reports_filters_requires_reports_group(self):
        self._login_as_fueler()
        resp = self.client.get("/api/v1/reports/filters")
        self.assertEqual(resp.status_code, 403)

    def test_reports_records_requires_reports_group(self):
        self._login_as_fueler()
        resp = self.client.get("/api/v1/reports/records?limit=1")
        self.assertEqual(resp.status_code, 403)

    def test_reports_access_events_requires_reports_group(self):
        self._login_as_fueler()
        resp = self.client.get("/api/v1/reports/access-events?limit=10")
        self.assertEqual(resp.status_code, 403)

    def test_reports_summary_aggregates_for_manager(self):
        self._login_as_manager()
        resp = self.client.get("/api/v1/reports/summary")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertGreaterEqual(payload["total_records"], 2)
        self.assertGreater(payload["total_liters"], 0)
        self.assertGreater(payload["avg_liters"], 0)

    def test_reports_records_requires_cursor_and_filters(self):
        self._login_as_manager()
        resp = self.client.get("/api/v1/reports/records?limit=2")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("items", payload)
        self.assertIn("has_next", payload)

        if payload["has_next"]:
            next_cursor = payload["next_cursor"]
            self.assertTrue(next_cursor)
            resp2 = self.client.get(
                f"/api/v1/reports/records?limit=2&cursor={next_cursor}"
            )
            self.assertEqual(resp2.status_code, 200)
            payload2 = resp2.json()
            self.assertIn("items", payload2)

        bad_cursor = "not-base64"
        resp3 = self.client.get(
            f"/api/v1/reports/records?limit=2&cursor={bad_cursor}"
        )
        self.assertEqual(resp3.status_code, 400)

    def test_reports_filters_returns_distinct_employees_and_regions(self):
        self._login_as_manager()
        resp = self.client.get("/api/v1/reports/filters")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("Иван Иванов", payload["employees"])
        self.assertTrue(len(payload["regions"]) >= 1)

    def test_reports_access_events_scope_and_admin(self):
        self._login_as_manager()
        resp = self.client.get("/api/v1/reports/access-events?limit=10")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        actions = {item["action"] for item in payload}
        self.assertIn("access_user_create", actions)
        self.assertNotIn("access_scope_change", actions)

        self._login_as_admin()
        resp2 = self.client.get("/api/v1/reports/access-events?limit=10")
        self.assertEqual(resp2.status_code, 200)
        payload2 = resp2.json()
        actions2 = {item["action"] for item in payload2}
        self.assertIn("access_scope_change", actions2)

    def test_analytics_stats_requires_reports_group(self):
        self._login_as_fueler()
        resp = self.client.get("/api/v1/analytics/stats")
        self.assertEqual(resp.status_code, 403)

    def test_analytics_export_requires_reports_group(self):
        self._login_as_fueler()
        resp = self.client.get("/api/v1/analytics/export")
        self.assertEqual(resp.status_code, 403)

    def test_analytics_stats_returns_sections(self):
        self._login_as_manager()
        start_date = (timezone.now().date() - timedelta(days=30)).isoformat()
        end_date = timezone.now().date().isoformat()
        resp = self.client.get(
            f"/api/v1/analytics/stats?start_date={start_date}&end_date={end_date}"
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("by_day", payload)
        self.assertIn("refuel_sources", payload)
        self.assertIn("refuel_channels", payload)
        self.assertIn("recent_records", payload)
        self.assertIn("by_car_fuel_tankers", payload)

    def test_analytics_export_returns_xlsx(self):
        self._login_as_manager()
        start_d = (timezone.now().date() - timedelta(days=30)).isoformat()
        end_d = timezone.now().date().isoformat()
        resp = self.client.get(
            f"/api/v1/analytics/export?start_date={start_d}&end_date={end_d}"
        )
        self.assertEqual(resp.status_code, 200)
        content_type = resp["Content-Type"]
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            content_type,
        )
        self.assertGreater(len(resp.content), 1000)

