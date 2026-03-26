from django.conf import settings
from django.db import models


class SystemLog(models.Model):
    ACTION_CHOICES = [
        ("login", "Вход в систему"),
        ("logout", "Выход из системы"),
        ("add_refuel", "Добавление заправки"),
        ("view_report", "Просмотр отчёта"),
        ("access_denied", "Отказ в доступе"),
        ("access_user_create", "Создание пользователя доступа"),
        ("access_user_activate", "Активация пользователя доступа"),
        ("access_user_deactivate", "Деактивация пользователя доступа"),
        ("access_role_assign", "Назначение роли доступа"),
        ("access_role_revoke", "Снятие роли доступа"),
        ("access_scope_change", "Изменение scope пользователя"),
        ("access_password_reset", "Сброс пароля доступа"),
        ("access_user_profile_update", "Обновление профиля сотрудника"),
        ("telegram_link_code_issued", "Выдан код привязки Telegram"),
        ("telegram_link_success", "Telegram успешно привязан"),
        ("telegram_link_failed", "Ошибка привязки Telegram"),
        ("error", "Ошибка"),
        ("info", "Информация"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Пользователь",
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name="Действие",
    )
    details = models.TextField(blank=True, verbose_name="Подробности")
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP-адрес",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата и время",
    )

    class Meta:
        verbose_name = "Системный лог"
        verbose_name_plural = "Системные логи"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self):
        if self.user:
            return (
                f"[{self.created_at:%d.%m %H:%M}] "
                f"{self.user.username} — {self.get_action_display()}"
            )
        return f"[{self.created_at:%d.%m %H:%M}] {self.get_action_display()}"
