from django.conf import settings
from django.db import models
from django.utils import timezone


class TelegramLinkToken(models.Model):
    """Одноразовый код привязки Telegram аккаунта к пользователю."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_link_tokens",
    )
    code = models.CharField(max_length=32, unique=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "telegram_link_tokens"
        verbose_name = "Код привязки Telegram"
        verbose_name_plural = "Коды привязки Telegram"
        ordering = ["-created_at"]

    @property
    def is_active(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()
