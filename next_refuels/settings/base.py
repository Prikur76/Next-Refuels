"""Base settings shared by dev and prod.

Keep only settings that are environment-independent here.
"""

from pathlib import Path

from environs import Env

from .logging_conf import LOGGING

# Environment
env = Env()
env.read_env()


# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY
SECRET_KEY = env.str("SECRET_KEY", "replace-me-with-secure-key")
DEBUG = env.bool("DEBUG", True)

if not DEBUG and SECRET_KEY == "replace-me-with-secure-key":
    raise RuntimeError("SECRET_KEY must be set when DEBUG is False")

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    ["127.0.0.1", "localhost"] if DEBUG else ["refuel.txnxt.ru"],
    delimiter=",",
)

# Apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "ninja",
    "phonenumber_field",
    # Local
    "core",
]

AUTH_USER_MODEL = "core.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.app_entry_redirect.AppEntryRedirectMiddleware",
    "core.middleware.admin_gate.AdminGateMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "core.middleware.auth_throttle.AuthThrottleMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "next_refuels.urls"
ASGI_APPLICATION = "next_refuels.asgi.application"
# WSGI_APPLICATION = "next_refuels.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# Internationalization
LANGUAGE_CODE = "ru-RU"
USE_I18N = True
USE_TZ = True
TIME_ZONE = env.str("TIME_ZONE", default="Europe/Moscow")

# Default phone number region
PHONENUMBER_DEFAULT_REGION = "RU"
PHONENUMBER_DEFAULT_FORMAT = "INTERNATIONAL"

# Static & Media
STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
)

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"
STATICFILES_DIRS: list[str | Path] = []

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default PK field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# === Integrations / Custom settings ===
TELEGRAM = {
    "TOKEN": env.str("TELEGRAM_BOT_TOKEN", ""),
    "BOT_USERNAME": env.str("TELEGRAM_BOT_USERNAME", ""),
    "PROXY_URL": env.str("TELEGRAM_PROXY_URL", ""),
    "DROP_PENDING_UPDATES": env.bool("TELEGRAM_DROP_PENDING_UPDATES", True),
    "ALLOWED_UPDATES": env.list("TELEGRAM_ALLOWED_UPDATES", default=[]),
    "LINK_CODE_TTL_MINUTES": env.int("TELEGRAM_LINK_CODE_TTL_MINUTES", 10),
}

TELEGRAM_ALERT_CHAT_ID = env.str("TELEGRAM_ALERT_CHAT_ID", "").strip()

ELEMENT_API = {
    "URL": env.str("ELEMENT_API_URL", ""),
    "USER": env.str("ELEMENT_API_USER", ""),
    "PASSWORD": env.str("ELEMENT_API_PASSWORD", ""),
}

SYNC_CARS_SCHEDULE_MINUTES = env.int("SYNC_CARS_SCHEDULE_MINUTES", 30)

# UX
CSRF_FAILURE_VIEW = "django.views.csrf.csrf_failure"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
FRONTEND_BASE_URL = env.str(
    "FRONTEND_BASE_URL",
    "http://localhost:5173",
).rstrip("/")
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", 28800)
SESSION_SAVE_EVERY_REQUEST = env.bool("SESSION_SAVE_EVERY_REQUEST", True)
SESSION_EXPIRE_AT_BROWSER_CLOSE = env.bool(
    "SESSION_EXPIRE_AT_BROWSER_CLOSE", False
)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = env.bool("CSRF_COOKIE_HTTPONLY", False)
SESSION_COOKIE_SAMESITE = env.str("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = env.str("CSRF_COOKIE_SAMESITE", "Lax")
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=(
        [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
        if DEBUG
        else []
    ),
    delimiter=",",
)

if not DEBUG and not CSRF_TRUSTED_ORIGINS:
    raise RuntimeError("CSRF_TRUSTED_ORIGINS must be set when DEBUG is False")

# WhiteNoise: раздача статических файлов Django (нужно для /admin при
# запуске без nginx).
WHITENOISE_USE_FINDERS = env.bool("WHITENOISE_USE_FINDERS", DEBUG)
WHITENOISE_AUTOREFRESH = env.bool(
    "WHITENOISE_AUTOREFRESH",
    DEBUG,
)

# Auth hardening
AUTH_THROTTLE_ENABLED = env.bool("AUTH_THROTTLE_ENABLED", True)
AUTH_THROTTLE_LIMIT = env.int("AUTH_THROTTLE_LIMIT", 5)
AUTH_THROTTLE_WINDOW_SECONDS = env.int("AUTH_THROTTLE_WINDOW_SECONDS", 900)
AUTH_THROTTLE_LOCK_SECONDS = env.int("AUTH_THROTTLE_LOCK_SECONDS", 1800)

# Identity provider readiness
AUTH_PROVIDER = env.str("AUTH_PROVIDER", "local")
SSO_METADATA_URL = env.str("SSO_METADATA_URL", "")
SSO_CLIENT_ID = env.str("SSO_CLIENT_ID", "")
SSO_CLIENT_SECRET = env.str("SSO_CLIENT_SECRET", "")
MFA_POLICY_ENABLED = env.bool("MFA_POLICY_ENABLED", False)

# Email defaults (can be overridden in prod)
EMAIL_BACKEND = env.str(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env.str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", "")
SERVER_EMAIL = env.str("SERVER_EMAIL", EMAIL_HOST_USER or "")
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "")

# Admins
ADMINS = [
    (
        env.str("DJANGO_SUPERUSER_USERNAME", "admin"),
        env.str("DJANGO_SUPERUSER_EMAIL", "admin@example.com"),
    )
]

# Logging
LOGGING = LOGGING

# Security defaults (can be toggled by env in prod/dev)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS", False
)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", False)

# Proxy headers
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False
USE_X_FORWARDED_PORT = False

if TELEGRAM_ALERT_CHAT_ID:
    from core.utils.telegram_alert_handler import TelegramAlertHandler

    _host_hint = ALLOWED_HOSTS[0] if ALLOWED_HOSTS else ""
    TelegramAlertHandler.set_session_note(_host_hint)
