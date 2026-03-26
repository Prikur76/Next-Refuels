import logging

from asgiref.sync import sync_to_async

from core.models import SystemLog

logger = logging.getLogger("next_refuels.custom")


def log_action(user=None, action="info", details="", ip_address=None):
    """SystemLog в БД и зеркало в next_refuels.custom (project.log / консоль)."""
    log_record = SystemLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        details=details,
        ip_address=ip_address,
    )

    # Пишем также в общий лог
    username = user.username if user and user.is_authenticated else "SYSTEM"
    ip_info = f" [{ip_address}]" if ip_address else ""
    logger.info(f"{username}{ip_info} — {action}: {details}")

    return log_record


def log_access_event(
    *,
    actor=None,
    action="info",
    target_user=None,
    details="",
    before="",
    after="",
    scope="",
    ip_address=None,
):
    """Логирование событий управления доступом."""
    target_suffix = ""
    if target_user:
        target_suffix = f" | target={target_user.username}"
    change_suffix = ""
    if before or after:
        change_suffix = f" | before={before} -> after={after}"
    scope_suffix = f" | scope={scope}" if scope else ""
    return log_action(
        user=actor,
        action=action,
        details=f"{details}{target_suffix}{change_suffix}{scope_suffix}",
        ip_address=ip_address,
    )


@sync_to_async
def log_command_action(action: str, details: str, user=None):
    """Те же БД + файлы, что и log_action (management-команды, без IP)."""
    return log_action(
        user=user,
        action=action,
        details=details,
        ip_address=None,
    )


async def log_sync_success(message: str, stats: dict):
    """Логирует успешную синхронизацию"""
    await log_command_action("info", message)


async def log_sync_failure(error: str):
    """Логирует ошибку синхронизации"""
    await log_command_action(
        "error",
        f"Ошибка синхронизации автомобилей: {error}",
    )
