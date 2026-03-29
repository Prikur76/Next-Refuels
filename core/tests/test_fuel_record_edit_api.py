# mypy: ignore-errors
from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone

from core.tests.tests_utils import (
    create_car,
    create_fuel_record,
    create_region,
    create_user,
)


class FuelRecordPatchRbacTests(TestCase):
    def setUp(self):
        self.region_a = create_region(name="Reg A", short_name="A")
        self.region_b = create_region(name="Reg B", short_name="B")
        self.fueler = create_user(
            username="f1",
            password="pw",
            groups=("Заправщик",),
            region=self.region_a,
        )
        self.manager_a = create_user(
            username="m1",
            password="pw",
            groups=("Менеджер",),
            region=self.region_a,
        )
        create_user(
            username="adm",
            password="pw",
            groups=("Администратор",),
        )
        self.car_a = create_car(
            code="1",
            state_number="A111AA77",
            model="M",
            region=self.region_a,
        )

    def test_fueler_patch_own_recent_ok(self):
        rec = create_fuel_record(
            car=self.car_a,
            employee=self.fueler,
            liters=Decimal("10"),
            filled_at=timezone.now(),
        )
        c = Client()
        c.login(username="f1", password="pw")
        resp = c.patch(
            f"/api/v1/fuel-records/{rec.id}",
            data=json.dumps({"notes": "x"}),
            content_type="application/json",
            HTTP_X_CLIENT_TIMEZONE="UTC",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        rec.refresh_from_db()
        self.assertEqual(rec.notes, "x")

    def test_fueler_patch_old_forbidden(self):
        past = timezone.now() - timedelta(hours=30)
        rec = create_fuel_record(
            car=self.car_a,
            employee=self.fueler,
            liters=Decimal("10"),
            filled_at=past,
        )
        c = Client()
        c.login(username="f1", password="pw")
        resp = c.patch(
            f"/api/v1/fuel-records/{rec.id}",
            data=json.dumps({"notes": "x"}),
            content_type="application/json",
            HTTP_X_CLIENT_TIMEZONE="UTC",
        )
        self.assertEqual(resp.status_code, 403)

    def test_manager_patch_same_region(self):
        rec = create_fuel_record(
            car=self.car_a,
            employee=self.fueler,
            liters=Decimal("10"),
            filled_at=timezone.now() - timedelta(days=10),
        )
        c = Client()
        c.login(username="m1", password="pw")
        resp = c.patch(
            f"/api/v1/fuel-records/{rec.id}",
            data=json.dumps({"notes": "mgr"}),
            content_type="application/json",
            HTTP_X_CLIENT_TIMEZONE="UTC",
        )
        self.assertEqual(resp.status_code, 200)
        rec.refresh_from_db()
        self.assertEqual(rec.notes, "mgr")

    def test_manager_patch_other_region_forbidden(self):
        fueler_b = create_user(
            username="f2",
            password="pw",
            groups=("Заправщик",),
            region=self.region_b,
        )
        car_b = create_car(
            code="2",
            state_number="B222BB77",
            model="M",
            region=self.region_b,
        )
        rec = create_fuel_record(
            car=car_b,
            employee=fueler_b,
            liters=Decimal("10"),
        )
        c = Client()
        c.login(username="m1", password="pw")
        resp = c.patch(
            f"/api/v1/fuel-records/{rec.id}",
            data=json.dumps({"notes": "bad"}),
            content_type="application/json",
            HTTP_X_CLIENT_TIMEZONE="UTC",
        )
        self.assertEqual(resp.status_code, 403)

    def test_excluded_not_in_summary(self):
        create_fuel_record(
            car=self.car_a,
            employee=self.fueler,
            liters=Decimal("50"),
        )
        rec = create_fuel_record(
            car=self.car_a,
            employee=self.fueler,
            liters=Decimal("40"),
        )
        c = Client()
        c.login(username="m1", password="pw")
        r1 = c.get("/api/v1/reports/summary")
        self.assertEqual(r1.status_code, 200)
        total_before = r1.json()["total_liters"]
        resp = c.patch(
            f"/api/v1/fuel-records/{rec.id}",
            data=json.dumps({"reporting_status": "EXCLUDED_DUPLICATE"}),
            content_type="application/json",
            HTTP_X_CLIENT_TIMEZONE="UTC",
        )
        self.assertEqual(resp.status_code, 200)
        r2 = c.get("/api/v1/reports/summary")
        total_after = r2.json()["total_liters"]
        self.assertLess(total_after, total_before)
        self.assertAlmostEqual(total_before - total_after, 40.0, places=2)

    def test_manager_reports_forced_own_region(self):
        fueler_b = create_user(
            username="f3",
            password="pw",
            groups=("Заправщик",),
            region=self.region_b,
        )
        car_b = create_car(
            code="3",
            state_number="C333CC77",
            model="M",
            region=self.region_b,
        )
        create_fuel_record(
            car=car_b,
            employee=fueler_b,
            liters=Decimal("99"),
        )
        create_fuel_record(
            car=self.car_a,
            employee=self.fueler,
            liters=Decimal("11"),
        )
        c = Client()
        c.login(username="m1", password="pw")
        resp = c.get(
            "/api/v1/reports/summary",
            {"region_id": str(self.region_b.id)},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_records"], 1)
        self.assertAlmostEqual(data["total_liters"], 11.0)
