# mypy: ignore-errors
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from core.models import Car, FuelRecord, Region

User = get_user_model()


class ApiFuelFlowTests(TestCase):
    def setUp(self):
        self.group, _ = Group.objects.get_or_create(name="Заправщик")
        self.user = User.objects.create_user(
            username="fueler",
            password="testpass123",
        )
        self.user.groups.add(self.group)
        self.region = Region.objects.create(name="Тестовый регион")
        self.car = Car.objects.create(
            code="C-001",
            state_number="A123BC77",
            model="Test Car",
            manufacture_year=2020,
            region=self.region,
            is_active=True,
            status="АКТИВЕН",
        )
        self.client = Client()
        self.client.login(username="fueler", password="testpass123")

    def test_create_fuel_record_via_api(self):
        response = self.client.post(
            "/api/v1/fuel-records",
            data={
                "car_id": self.car.id,
                "liters": "45.5",
                "fuel_type": "GASOLINE",
                "source": "TGBOT",
                "notes": "api test",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FuelRecord.objects.count(), 1)
        record = FuelRecord.objects.first()
        self.assertEqual(float(record.liters), 45.5)
        self.assertEqual(record.source, "TGBOT")

    def test_cars_search_endpoint(self):
        response = self.client.get("/api/v1/cars?query=A123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["state_number"], "A123BC77")

