# mypy: ignore-errors
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.test import Client, TestCase
from phonenumber_field.phonenumber import to_python

from core.models import Region

User = get_user_model()


class AccessApiTests(TestCase):
    def setUp(self):
        self.manager_group, _ = Group.objects.get_or_create(name="Менеджер")
        self.fueler_group, _ = Group.objects.get_or_create(name="Заправщик")
        self.admin_group, _ = Group.objects.get_or_create(
            name="Администратор"
        )

        self.region_a = Region.objects.create(name="Регион A")
        self.region_b = Region.objects.create(name="Регион B")

        self.manager = User.objects.create_user(
            username="manager_a",
            password="pass12345",
            region=self.region_a,
        )
        self.manager.groups.add(self.manager_group)

        self.target_in_scope = User.objects.create_user(
            username="fueler_a",
            password="pass12345",
            region=self.region_a,
        )
        self.target_in_scope.groups.add(self.fueler_group)

        self.target_out_scope = User.objects.create_user(
            username="fueler_b",
            password="pass12345",
            region=self.region_b,
        )
        self.target_out_scope.groups.add(self.fueler_group)

        self.client = Client()
        self.client.login(username="manager_a", password="pass12345")

        self.admin = User.objects.create_user(
            username="admin",
            password="pass12345",
            region=self.region_b,
        )
        self.admin.groups.add(self.admin_group)
        self.admin_client = Client()
        self.admin_client.login(username="admin", password="pass12345")

    def test_manager_sees_only_scoped_users(self):
        response = self.client.get("/api/v1/access/users")
        self.assertEqual(response.status_code, 200)
        usernames = {item["username"] for item in response.json()}
        self.assertIn("manager_a", usernames)
        self.assertIn("fueler_a", usernames)
        self.assertNotIn("fueler_b", usernames)

    def test_manager_cannot_disable_out_of_scope_user(self):
        response = self.client.patch(
            f"/api/v1/access/users/{self.target_out_scope.id}",
            data={"is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_create_fueler_in_own_scope(self):
        response = self.client.post(
            "/api/v1/access/users",
            data={
                "email": "new_fueler@example.com",
                "first_name": "Новый",
                "last_name": "Сотрудник",
                "phone": "+79000000000",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        created = User.objects.get(email="new_fueler@example.com")
        self.assertEqual(created.region_id, self.region_a.id)
        self.assertEqual(created.username, "new_fueler")
        self.assertEqual(created.phone, to_python("+79000000000"))

    def test_manager_can_set_password_on_create(self):
        response = self.client.post(
            "/api/v1/access/users",
            data={
                "email": "new_with_password@example.com",
                "first_name": "Новый",
                "last_name": "Сотрудник",
                "phone": "+79000000001",
                "password": "StrongPass123",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload["temporary_password"])

        created = User.objects.get(email="new_with_password@example.com")
        self.assertTrue(created.check_password("StrongPass123"))
        self.assertTrue(created.must_change_password)

    def test_manager_can_update_user_password(self):
        response = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/password",
            data={
                "password": "UpdatedPass123",
                "generate_temporary": False,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload["temporary_password"])
        self.target_in_scope.refresh_from_db()
        self.assertTrue(self.target_in_scope.check_password("UpdatedPass123"))
        self.assertTrue(self.target_in_scope.must_change_password)

    def test_user_can_complete_first_login_password_setup(self):
        user = User.objects.create_user(
            username="new_user_setup",
            password="tempPass123",
            must_change_password=True,
            region=self.region_a,
        )
        user_client = Client()
        user_client.login(username="new_user_setup", password="tempPass123")

        response = user_client.post(
            "/api/v1/auth/password/setup",
            data={"password": "MyFinalPass123", "generate": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.must_change_password)
        self.assertTrue(user.check_password("MyFinalPass123"))

    def test_manager_cannot_create_without_email(self):
        response = self.client.post(
            "/api/v1/access/users",
            data={
                "email": "",
                "first_name": "Новый",
                "last_name": "Сотрудник",
            },
            content_type="application/json",
        )
        self.assertIn(response.status_code, (400, 422))

    def test_manager_cannot_create_without_email_field(self):
        response = self.client.post(
            "/api/v1/access/users",
            data={
                "first_name": "Новый",
                "last_name": "Сотрудник",
            },
            content_type="application/json",
        )
        self.assertIn(response.status_code, (400, 422))

    def test_manager_cannot_assign_manager_role(self):
        response = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/role",
            data={"role": "Менеджер"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_promote_to_manager(self):
        response = self.admin_client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/role",
            data={"role": "Менеджер"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.target_in_scope.refresh_from_db()
        roles = set(self.target_in_scope.groups.values_list("name", flat=True))
        self.assertIn("Менеджер", roles)
        self.assertNotIn("Заправщик", roles)

    def test_manager_cannot_change_out_scope_role(self):
        response = self.client.patch(
            f"/api/v1/access/users/{self.target_out_scope.id}/role",
            data={"role": "Заправщик"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_disable_admin(self):
        self.admin.region = self.region_a
        self.admin.save(update_fields=["region"])

        response = self.client.patch(
            f"/api/v1/access/users/{self.admin.id}",
            data={"is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_change_admin_role(self):
        self.admin.region = self.region_a
        self.admin.save(update_fields=["region"])

        response = self.client.patch(
            f"/api/v1/access/users/{self.admin.id}/role",
            data={"role": "Заправщик"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_access_users_returns_only_active_by_default(self):
        self.target_in_scope.is_active = False
        self.target_in_scope.save(update_fields=["is_active"])

        response = self.client.get("/api/v1/access/users")
        self.assertEqual(response.status_code, 200)
        usernames = {item["username"] for item in response.json()}
        self.assertNotIn("fueler_a", usernames)

    def test_access_users_returns_all_with_show_all(self):
        self.target_in_scope.is_active = False
        self.target_in_scope.save(update_fields=["is_active"])

        response = self.client.get("/api/v1/access/users?show_all=true")
        self.assertEqual(response.status_code, 200)
        usernames = {item["username"] for item in response.json()}
        self.assertIn("fueler_a", usernames)

    def test_manager_can_update_profile_in_scope(self):
        response = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}/profile",
            data={
                "first_name": "Обновленный",
                "phone": "+79001112233",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.target_in_scope.refresh_from_db()
        self.assertEqual(self.target_in_scope.first_name, "Обновленный")
        self.assertEqual(
            self.target_in_scope.phone,
            to_python("+79001112233"),
        )

    def test_set_active_invalidates_bot_cache(self):
        self.target_in_scope.telegram_id = 555123777
        self.target_in_scope.save(update_fields=["telegram_id"])
        cache_key = f"bot_user:{self.target_in_scope.telegram_id}"
        cache.set(cache_key, {"id": self.target_in_scope.id}, timeout=600)
        self.assertIsNotNone(cache.get(cache_key))

        response = self.client.patch(
            f"/api/v1/access/users/{self.target_in_scope.id}",
            data={"is_active": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(cache.get(cache_key))

