"""
WSGI config for next_refuels project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application


def _resolve_settings_module() -> str:
    debug_raw = os.getenv("DEBUG", "True").strip().lower()
    is_debug = debug_raw in {"1", "true", "yes", "on"}
    if is_debug:
        return "next_refuels.settings.dev"
    return "next_refuels.settings.prod"


os.environ.setdefault("DJANGO_SETTINGS_MODULE", _resolve_settings_module())


application = get_wsgi_application()
