"""Отправка записей логов уровня ERROR+ в Telegram (оперативные оповещения)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import ClassVar

# Интервал между сообщениями в один чат (антифлуд при серии ошибок).
_COOLDOWN_SEC = 60.0
_last_sent_at: float = 0.0


class TelegramAlertHandler(logging.Handler):
    """Handler: POST в sendMessage. Нужны TELEGRAM_BOT_TOKEN и TELEGRAM_ALERT_CHAT_ID."""

    _session_note: ClassVar[str] = ""

    def __init__(self, level: int = logging.ERROR) -> None:
        super().__init__(level=level)

    @classmethod
    def set_session_note(cls, note: str) -> None:
        """Короткая метка (например, ALLOWED_HOSTS[0]) в шапке сообщения."""
        cls._session_note = (note or "").strip()

    def emit(self, record: logging.LogRecord) -> None:
        global _last_sent_at
        try:
            from django.conf import settings
        except Exception:
            return

        tg = getattr(settings, "TELEGRAM", None) or {}
        token = (tg.get("TOKEN") if isinstance(tg, dict) else "") or ""
        chat_id = getattr(settings, "TELEGRAM_ALERT_CHAT_ID", None) or ""
        if not token or not chat_id:
            return

        now = time.monotonic()
        if now - _last_sent_at < _COOLDOWN_SEC:
            return
        _last_sent_at = now

        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        if len(msg) > 3500:
            msg = msg[:3490] + "\n…(truncated)"

        header = "Next-Refuels: ошибка"
        if self._session_note:
            header = f"{header} ({self._session_note})"
        text = f"{header}\n\n{msg}"

        payload = json.dumps(
            {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            ensure_ascii=False,
        ).encode("utf-8")

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status != 200:
                    logging.getLogger(__name__).warning(
                        "Telegram alert HTTP %s", resp.status
                    )
        except urllib.error.URLError as exc:
            logging.getLogger(__name__).warning(
                "Telegram alert failed: %s", exc.reason
            )
