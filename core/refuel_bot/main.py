# core/bot/main.py
import logging

from django.conf import settings
from telegram import Update
from telegram.ext import ApplicationBuilder, TypeHandler
from telegram.request import HTTPXRequest

from core.refuel_bot.handlers.fuel_input import (
    fuel_command_handler,
    fuel_conv_handler,
)
from core.refuel_bot.handlers.start import (
    help_handler,
    help_message_handler,
    start_handler,
)
from core.refuel_bot.middleware.access_middleware import access_middleware

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context):
    logger.exception("Unhandled exception in handler", exc_info=context.error)


def build_app():
    token = settings.TELEGRAM.get("TOKEN", None)
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in settings")

    # Читаем прокси из настроек (если нужно)
    proxy_url = settings.TELEGRAM.get("PROXY_URL", None)

    request_kwargs = {
        "connect_timeout": 20.0,
        "read_timeout": 40.0,
        "write_timeout": 30.0,
        "pool_timeout": 10.0,
    }
    if proxy_url:
        logger.info(f"Using proxy: {proxy_url}")
        request_kwargs["proxy"] = proxy_url

    # Явно задаем таймауты HTTP-клиента даже без прокси:
    # это снижает риск таймаута на первом getMe во время bootstrap.
    request = HTTPXRequest(**request_kwargs)
    app = ApplicationBuilder().token(token).request(request).get_me_request_timeout(30).build()
    app.add_handler(TypeHandler(Update, access_middleware), group=-1)

    # Команды/кнопки
    app.add_handler(start_handler)
    app.add_handler(help_handler)
    app.add_handler(help_message_handler)

    # Бот-функционал
    app.add_handler(fuel_command_handler)
    app.add_handler(fuel_conv_handler)

    app.add_error_handler(error_handler)

    logger.info("Telegram application built")
    return app


def run_bot():
    app = build_app()
    allowed_updates = settings.TELEGRAM.get("ALLOWED_UPDATES", [])
    app.run_polling(
        drop_pending_updates=settings.TELEGRAM.get(
            "DROP_PENDING_UPDATES", True
        ),
        allowed_updates=allowed_updates or None,
    )

    logger.info("Telegram bot stopped")
