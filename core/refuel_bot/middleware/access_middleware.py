# core/bot/middleware/access_middleware.py
import logging
import re
from typing import Any, Dict

from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.utils import timezone as dj_tz
from telegram import Update
from telegram.ext import ContextTypes

from core.models import User
from core.services.telegram_link_service import (
    TelegramLinkError,
    TelegramLinkService,
)
from core.utils.logging import log_action

logger = logging.getLogger(__name__)

# Ключ кэша: bot_user:<telegram_id>
CACHE_KEY_PREFIX = "bot_user:"
# Время жизни кэша — 15 минут
CACHE_TTL = 60 * 15  # 15 минут


def _fetch_user_data_sync(telegram_id: int) -> Dict[str, Any] | None:
    """
    Синхронная функция: загружает данные пользователя.
    Перед запросом убеждается, что соединение с БД активно.
    """
    from django import db

    try:
        # Убедимся, что соединение живое
        db.close_old_connections()

        user = (
            User.objects.select_related("region")
            .prefetch_related("groups")
            .filter(telegram_id=telegram_id, is_active=True)
            .only(
                "id",
                "username",
                "first_name",
                "last_name",
                "telegram_id",
                "is_active",
                "region__id",
                "region__name",
            )
            .first()
        )
        if not user:
            return None

        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "is_active": user.is_active,
            "region_id": user.region.id if user.region else None,
            "region_name": user.region.name if user.region else None,
            "group_names": list(user.groups.values_list("name", flat=True)),
            "fetched_at": dj_tz.now().isoformat(),
        }
    except Exception:
        logger.exception(
            "Ошибка при загрузке пользователя telegram_id=%s", telegram_id
        )
        return None


async def access_middleware(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Подставляет в context.user упрощённый объект с данными пользователя.
    Использует кэш для оптимизации.
    """
    # Инициализация
    context.user = None
    context.user_data.pop("user_id", None)
    context.user_data.pop("telegram_id", None)
    context.user_data.pop("group_names", None)

    tg_user = getattr(update, "effective_user", None)
    if not tg_user:
        return

    telegram_id = tg_user.id
    cache_key = f"{CACHE_KEY_PREFIX}{telegram_id}"

    # Получаем из кэша
    try:
        user_data = cache.get(cache_key)
    except Exception as e:
        logger.warning("Cache GET failed for %s: %s", telegram_id, e)
        user_data = None

    # Если нет — загружаем из БД
    if user_data is None:
        # Позволяем привязку только по явной команде /start <code> или /link <code>
        message_text = ""
        if update.effective_message and update.effective_message.text:
            message_text = update.effective_message.text.strip()

        link_code = ""
        # Поддерживаем оба формата:
        # /start <code> и /start@BotUsername <code> (аналогично для /link).
        command_match = re.match(
            r"^/(?:start|link)(?:@[A-Za-z0-9_]+)?\s+(.+)$",
            message_text,
        )
        if command_match:
            link_code = command_match.group(1).strip()

        if link_code:
            try:
                await sync_to_async(
                    TelegramLinkService.consume_link_token,
                    thread_sensitive=True,
                )(
                    telegram_id=telegram_id,
                    code=link_code,
                )
                await sync_to_async(log_action, thread_sensitive=True)(
                    user=None,
                    action="telegram_link_success",
                    details=(
                        "Telegram привязан через одноразовый код "
                        f"для telegram_id={telegram_id}"
                    ),
                )
                try:
                    if update.effective_message:
                        await update.effective_message.reply_text(
                            "Аккаунт успешно привязан. Повторите команду /start."
                        )
                except Exception:
                    logger.warning("Не удалось отправить сообщение о привязке")
            except TelegramLinkError as exc:
                logger.warning(
                    "Ошибка привязки Telegram %s: %s",
                    telegram_id,
                    exc,
                )
                await sync_to_async(log_action, thread_sensitive=True)(
                    user=None,
                    action="telegram_link_failed",
                    details=(
                        "Ошибка привязки Telegram "
                        f"telegram_id={telegram_id}: {exc}"
                    ),
                )
                try:
                    if update.effective_message:
                        await update.effective_message.reply_text(
                            "Не удалось привязать аккаунт. Проверьте код и попробуйте снова."
                        )
                except Exception:
                    logger.warning(
                        "Не удалось отправить сообщение об ошибке привязки"
                    )

        user_data = await sync_to_async(
            _fetch_user_data_sync, thread_sensitive=True
        )(telegram_id)
        if user_data is None:
            logger.warning(
                "Пользователь не найден или неактивен: telegram_id=%s",
                telegram_id,
            )
            return

        # Сохраняем в кэш (если возможно)
        try:
            cache.set(cache_key, user_data, timeout=CACHE_TTL)
        except Exception as e:
            logger.warning("Cache SET failed for %s: %s", telegram_id, e)

    # Сохраняем ID и группу в контекст
    context.user_data["telegram_id"] = telegram_id
    context.user_data["user_id"] = user_data["id"]
    context.user_data["group_names"] = user_data["group_names"]

    # Создаём лёгкий объект пользователя
    class SimpleUser:
        def __init__(self, data):
            self.id = data["id"]
            self.telegram_id = data["telegram_id"]
            self.username = data["username"]
            self.first_name = data["first_name"]
            self.last_name = data["last_name"]
            self.group_names = set(data["group_names"])
            self.is_superuser = "Администратор" in self.group_names
            self.is_manager = "Менеджер" in self.group_names
            self.is_fueler = "Заправщик" in self.group_names

        def get_full_name(self) -> str:
            full_name = (
                f"{self.first_name or ''} {self.last_name or ''}".strip()
            )
            return full_name or self.username or f"User{self.telegram_id}"

        def has_group(self, name: str) -> bool:
            return name in self.group_names

    # Привязываем к context.user
    try:
        context.user = SimpleUser(user_data)
    except Exception:
        logger.exception(
            "Не удалось создать SimpleUser для telegram_id=%s", telegram_id
        )
        context.user = None
