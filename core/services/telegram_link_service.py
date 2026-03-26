from __future__ import annotations

import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.models import TelegramLinkToken

User = get_user_model()


class TelegramLinkError(ValueError):
    """Бизнес-ошибка при привязке Telegram."""


class TelegramLinkService:
    @staticmethod
    def _generate_code() -> str:
        # URL-safe, короткий и человекочитаемый код.
        return secrets.token_urlsafe(9)

    @staticmethod
    @transaction.atomic
    def create_link_token_for_user(
        *,
        user,
        ttl_minutes: int,
    ) -> TelegramLinkToken:
        if not user or not user.is_authenticated:
            raise TelegramLinkError("Требуется авторизация")
        if not user.is_active:
            raise TelegramLinkError("Пользователь деактивирован")

        TelegramLinkToken.objects.filter(
            user=user,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).update(expires_at=timezone.now())

        token = TelegramLinkToken.objects.create(
            user=user,
            code=TelegramLinkService._generate_code(),
            expires_at=timezone.now() + timedelta(minutes=max(1, ttl_minutes)),
        )
        return token

    @staticmethod
    @transaction.atomic
    def consume_link_token(*, telegram_id: int, code: str):
        normalized = (code or "").strip()
        if not normalized:
            raise TelegramLinkError("Код привязки не указан")

        token = (
            TelegramLinkToken.objects.select_for_update()
            .select_related("user")
            .filter(code=normalized)
            .first()
        )
        if token is None:
            raise TelegramLinkError("Код привязки не найден")
        if token.used_at is not None:
            raise TelegramLinkError("Код уже использован")
        if token.expires_at <= timezone.now():
            raise TelegramLinkError("Срок действия кода истек")

        user = token.user
        if not user.is_active:
            raise TelegramLinkError("Пользователь деактивирован")

        existing = (
            User.objects.filter(telegram_id=telegram_id)
            .exclude(id=user.id)
            .first()
        )
        if existing:
            raise TelegramLinkError(
                "Этот Telegram уже привязан к другому аккаунту"
            )

        user.telegram_id = telegram_id
        user.save(update_fields=["telegram_id"])

        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
        return user
