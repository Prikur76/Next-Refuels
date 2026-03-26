"""
ASGI config for next_refuels project.
"""

import os

from django.core.asgi import get_asgi_application


def _resolve_settings_module() -> str:
    debug_raw = os.getenv("DEBUG", "True").strip().lower()
    is_debug = debug_raw in {"1", "true", "yes", "on"}
    if is_debug:
        return "next_refuels.settings.dev"
    return "next_refuels.settings.prod"


os.environ.setdefault("DJANGO_SETTINGS_MODULE", _resolve_settings_module())


django_application = get_asgi_application()


# Создаем ASGI приложение с поддержкой lifespan
async def application(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    else:
        await django_application(scope, receive, send)
