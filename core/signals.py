"""Сигналы приложения core."""

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from core.models import Car, FuelRecord, Region
from core.utils.logging import log_action


@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    """
    Создаёт системные группы пользователей и базовые права.
    """
    # Чтобы не создавать при миграциях других приложений
    if sender.name != "core":
        return

    groups = {
        "Заправщик": {
            "permissions": [
                ("add_fuelrecord", FuelRecord),
                ("view_fuelrecord", FuelRecord),
            ],
        },
        "Менеджер": {
            "permissions": [
                ("view_fuelrecord", FuelRecord),
                ("change_fuelrecord", FuelRecord),
                ("view_car", Car),
                ("view_region", Region),
            ],
        },
        "Администратор": {
            "permissions": "all",  # получит все права
        },
    }

    for group_name, config in groups.items():
        group, created = Group.objects.get_or_create(name=group_name)

        if config["permissions"] == "all":
            all_perms = Permission.objects.all()
            group.permissions.set(all_perms)
        else:
            perms = []
            for perm_code, model in config["permissions"]:
                ct = ContentType.objects.get_for_model(model)
                perm = Permission.objects.get(
                    codename=perm_code, content_type=ct
                )
                perms.append(perm)
            group.permissions.set(perms)

        group.save()
        if created:
            print(f"Group '{group_name}' created.")
        else:
            print(f"Group '{group_name}' already exists.")


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ip = request.META.get("REMOTE_ADDR")
    log_action(user, "login", "Пользователь вошёл в систему", ip)


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    ip = request.META.get("REMOTE_ADDR")
    log_action(user, "logout", "Пользователь вышел из системы", ip)
