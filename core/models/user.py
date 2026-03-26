from django.contrib.auth.models import (
    AbstractUser,
    Group,
    Permission,
)
from django.contrib.auth.models import (
    UserManager as DjangoUserManager,
)
from django.db import models, transaction
from phonenumber_field.modelfields import PhoneNumberField


# -----------------------
# Кастомный QuerySet
# -----------------------
class UserQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def by_region(self, region_id):
        return self.filter(region_id=region_id)

    def fuelmans(self):
        return self.filter(groups__name="Заправщик")

    def managers(self):
        return self.filter(groups__name="Менеджер")

    def admins(self):
        return self.filter(groups__name="Администратор")


# -----------------------
# Кастомный менеджер
# -----------------------
class CustomUserManager(DjangoUserManager.from_queryset(UserQuerySet)):
    """Менеджер пользователей с автоматическим созданием группы 'Администратор'."""

    @transaction.atomic
    def create_superuser(
        self, username, email=None, password=None, **extra_fields
    ):
        # Флаги безопасности
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if not extra_fields.get("is_staff"):
            raise ValueError("Суперпользователь должен иметь is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError(
                "Суперпользователь должен иметь is_superuser=True."
            )

        # Создаём суперпользователя через базовый метод
        user = self.create_user(username, email, password, **extra_fields)

        # Назначаем (или создаём) группу "Администратор"
        try:
            group, created = Group.objects.get_or_create(name="Администратор")

            # Если группа только что создана, добавим все доступные права
            if created:
                all_permissions = Permission.objects.all()
                group.permissions.set(all_permissions)
                group.save()

            # Добавляем пользователя в группу
            user.groups.add(group)

        except Exception as e:
            # Безопасный fallback: не прерываем создание суперпользователя
            print(f"⚠️ Не удалось присвоить группу 'Администратор': {e}")

        return user


# -----------------------
# Модель User
# -----------------------
class User(AbstractUser):
    telegram_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        verbose_name="Telegram ID",
        null=True,
        blank=True,
    )
    first_name = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Имя"
    )
    last_name = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Фамилия"
    )
    phone = PhoneNumberField(blank=True, null=True, verbose_name="Телефон")
    region = models.ForeignKey(
        "core.Region",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Регион",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    must_change_password = models.BooleanField(
        default=False, verbose_name="Требуется смена пароля при входе"
    )

    objects = CustomUserManager()

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        indexes = [
            models.Index(fields=["telegram_id"]),
        ]

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.get_full_name()} ({self.telegram_id})"
        return f"{self.username} ({self.telegram_id})"

    def get_full_name(self) -> str:
        name = super().get_full_name()
        return name if name.strip() else self.username
