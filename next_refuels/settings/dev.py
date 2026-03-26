"""Development settings - extend base with dev-friendly defaults."""

from typing import Any, cast

import dj_database_url

from .base import *  # noqa: F403
from .base import BASE_DIR, LOGGING, env

# Разработка: Next.js на :5173, Django (API + /admin) на :8000.
# Браузерные запросы с 5173 на 8000 — cross-origin → нужен CORS.
INSTALLED_APPS = [
    *INSTALLED_APPS,
    "corsheaders",
]
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    *MIDDLEWARE,
]

# Список origin фронта (http://HOST:5173). При доступе по LAN добавьте
# http://192.168.x.x:5173 через запятую в .env (или переопределите целиком).
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    delimiter=",",
)
CORS_ALLOW_CREDENTIALS = True

# Make sure DEBUG is True
DEBUG = True

# Allow all hosts locally
ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS", default=["127.0.0.1", "localhost"], delimiter=","
)

# Use external Postgres in dev when DATABASE_URL is provided.
# Fallback to sqlite for fully local no-DB setup.
DATABASE_URL = env.str("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=env.int("DB_CONN_TIMEOUT", 30),
            ssl_require=env.bool("DB_SSL_REQUIRE", False),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Keep console logging in dev
_logging = cast(dict[str, Any], LOGGING)
_logging["root"]["handlers"] = ["console", "file_general"]
_logging["root"]["level"] = "DEBUG"
# Подробный SQL в sql.log при отладке (в base для prod — WARNING)
_logging["loggers"]["django.db.backends"]["level"] = "DEBUG"

# Email to console in dev to avoid accidental sends
EMAIL_BACKEND = env.str(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

# Relax security for local dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False

# Use local cache in dev
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-next-refuels",
    }
}
