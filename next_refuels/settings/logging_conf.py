"""
Central logging configuration for Django project.

This file is imported inside base.py:
    from .logging_conf import LOGGING
"""

from __future__ import annotations

import os
from pathlib import Path

# Directory for storing log files
BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} [{name}:{lineno}] {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file_general": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "project.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
            "encoding": "utf-8",
            "delay": True,
        },
        "file_errors": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "errors.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 30,
            "formatter": "verbose",
            "level": "ERROR",
            "encoding": "utf-8",
        },
        "file_sql": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "sql.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "level": "DEBUG",
            "encoding": "utf-8",
            "delay": True,
        },
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file_general", "file_errors"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file_general"],
            "level": "INFO",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["file_errors"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["file_errors", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["file_sql"],
            # В проде не засыпаем sql.log каждым запросом; в dev см. settings/dev.py
            "level": "WARNING",
            "propagate": False,
        },
        # App-specific loggers
        "core.refuel_bot": {
            "handlers": ["console", "file_general"],
            "level": "INFO",
            "propagate": False,
        },
        "next_refuels.custom": {
            "handlers": ["console", "file_errors"],
            # Должен совпадать с log_action(...): logger.info пишет аудит в файлы
            "level": "INFO",
            "propagate": False,
        },
        "core.clients": {
            "handlers": ["console", "file_general"],
            "level": "INFO",
            "propagate": False,
        },
        # Подавление подробных логов httpx
        "httpx": {
            "handlers": ["file_errors"],  # Только ошибки попадут в errors.log
            "level": "WARNING",  # Игнорируем INFO (POST, GET и т.п.)
            "propagate": False,
        },
        "httpcore": {
            "handlers": [],
            "level": "WARNING",
            "propagate": False,
        },
        "urllib3": {
            "handlers": [],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

_telegram_chat = (os.environ.get("TELEGRAM_ALERT_CHAT_ID") or "").strip()
if _telegram_chat:
    LOGGING["handlers"]["telegram_alerts"] = {
        "class": "core.utils.telegram_alert_handler.TelegramAlertHandler",
        "level": "ERROR",
        "formatter": "verbose",
    }
    for _key in ("django.request", "django.security", "next_refuels.custom"):
        _h = list(LOGGING["loggers"][_key]["handlers"])
        if "telegram_alerts" not in _h:
            _h.append("telegram_alerts")
        LOGGING["loggers"][_key]["handlers"] = _h
