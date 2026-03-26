from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q

from core.models import User

AppUser = get_user_model()

ROLE_MANAGER = "Менеджер"
ROLE_ADMIN = "Администратор"
ROLE_FUELER = "Заправщик"
MANAGED_ROLES = (ROLE_FUELER, ROLE_MANAGER, ROLE_ADMIN)


@dataclass
class AccessCreatePayload:
    email: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    password: str | None = None
    region_id: int | None = None
    activate: bool = True


@dataclass
class AccessUpdatePayload:
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    region_id: int | None = None


class UserAccessService:
    """Scoped RBAC операции управления пользователями."""

    @staticmethod
    def _is_admin(user: User) -> bool:
        return bool(getattr(user, "is_superuser", False)) or user.groups.filter(
            name=ROLE_ADMIN
        ).exists()

    @staticmethod
    def _is_manager(user: User) -> bool:
        return user.groups.filter(name=ROLE_MANAGER).exists()

    @staticmethod
    def _ensure_manager_or_admin(actor: User) -> None:
        if not (
            UserAccessService._is_admin(actor)
            or UserAccessService._is_manager(actor)
        ):
            raise PermissionDenied("Недостаточно прав для управления доступом")

    @staticmethod
    def _scope_label(user: User) -> str:
        region = user.region_id or "none"
        return f"region={region}"

    @staticmethod
    def _ensure_actor_scope(actor: User) -> None:
        if UserAccessService._is_admin(actor):
            return
        if not actor.region_id:
            raise PermissionDenied("У менеджера не задан region для access-операций")

    @staticmethod
    def _roles_of(user: User) -> set[str]:
        return set(user.groups.values_list("name", flat=True))

    @staticmethod
    def _target_in_scope(actor: User, target: User) -> bool:
        return bool(actor.region_id and actor.region_id == target.region_id)

    @staticmethod
    def _target_is_admin(target: User) -> bool:
        return bool(getattr(target, "is_superuser", False)) or target.groups.filter(
            name=ROLE_ADMIN
        ).exists()

    @staticmethod
    def _username_from_email(email: str) -> str:
        local_part = (email or "").split("@", maxsplit=1)[0].strip().lower()
        candidate = re.sub(r"[^a-z0-9._-]+", "_", local_part).strip("._-")
        if not candidate:
            raise ValueError("Не удалось сформировать username из email")
        return candidate

    @staticmethod
    def _build_unique_username(base_username: str) -> str:
        username = base_username
        suffix = 1
        while AppUser.objects.filter(username=username).exists():
            username = f"{base_username}_{suffix}"
            suffix += 1
        return username

    @staticmethod
    def _check_scope(actor: User, target: User) -> None:
        if UserAccessService._is_admin(actor):
            return
        UserAccessService._ensure_actor_scope(actor)

        if not UserAccessService._target_in_scope(actor, target):
            raise PermissionDenied(
                "Операция вне зоны ответственности менеджера"
            )

    @staticmethod
    def list_users_for_actor(actor: User, active_only: bool = False):
        UserAccessService._ensure_manager_or_admin(actor)
        UserAccessService._ensure_actor_scope(actor)
        qs = (
            AppUser.objects.select_related("region")
            .prefetch_related("groups")
            .order_by("username")
        )
        if active_only:
            qs = qs.filter(is_active=True)
        if UserAccessService._is_admin(actor):
            return qs

        scope_filter = Q()
        if actor.region_id:
            scope_filter |= Q(region_id=actor.region_id)
        if not scope_filter:
            return qs.none()
        return qs.filter(scope_filter)

    @staticmethod
    @transaction.atomic
    def create_fueler(
        actor: User,
        payload: AccessCreatePayload,
    ) -> tuple[User, str | None]:
        UserAccessService._ensure_manager_or_admin(actor)
        UserAccessService._ensure_actor_scope(actor)

        region_id = payload.region_id
        if not UserAccessService._is_admin(actor):
            region_id = actor.region_id

        email = (payload.email or "").strip()
        if not email:
            raise ValueError("Email не задан")

        username_base = UserAccessService._username_from_email(email)
        username = UserAccessService._build_unique_username(username_base)

        password_value = (payload.password or "").strip()
        generated_password: str | None = None
        if password_value:
            if len(password_value) < 8:
                raise ValueError("Пароль должен содержать минимум 8 символов")
            password_to_set = password_value
        else:
            generated_password = secrets.token_urlsafe(12)
            password_to_set = generated_password

        user = AppUser.objects.create_user(
            username=username,
            email=email,
            password=password_to_set,
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=payload.phone,
            region_id=region_id,
            is_active=payload.activate,
            must_change_password=True,
        )
        fueler_group, _ = Group.objects.get_or_create(name=ROLE_FUELER)
        user.groups.add(fueler_group)
        return user, generated_password

    @staticmethod
    @transaction.atomic
    def set_active(actor: User, target_id: int, is_active: bool) -> User:
        UserAccessService._ensure_manager_or_admin(actor)
        UserAccessService._ensure_actor_scope(actor)
        target = AppUser.objects.get(id=target_id)
        UserAccessService._check_scope(actor, target)

        if not UserAccessService._is_admin(
            actor
        ) and UserAccessService._target_is_admin(target):
            raise PermissionDenied(
                "Менеджер не может изменять статус администратора"
            )

        target.is_active = is_active
        target.save(update_fields=["is_active"])
        return target

    @staticmethod
    @transaction.atomic
    def assign_role(actor: User, target_id: int, role: str) -> User:
        UserAccessService._ensure_manager_or_admin(actor)
        UserAccessService._ensure_actor_scope(actor)
        if role not in MANAGED_ROLES:
            raise PermissionDenied("Неизвестная роль для назначения")
        target = AppUser.objects.get(id=target_id)
        UserAccessService._check_scope(actor, target)

        if not UserAccessService._is_admin(
            actor
        ) and UserAccessService._target_is_admin(target):
            raise PermissionDenied(
                "Менеджер не может изменять роль администратора"
            )

        if not UserAccessService._is_admin(actor) and role != ROLE_FUELER:
            raise PermissionDenied(
                "Менеджер может назначать только роль Заправщик"
            )

        groups_to_keep = [
            name
            for name in UserAccessService._roles_of(target)
            if name not in MANAGED_ROLES
        ]
        target.groups.clear()
        for group_name in groups_to_keep:
            group, _ = Group.objects.get_or_create(name=group_name)
            target.groups.add(group)
        role_group, _ = Group.objects.get_or_create(name=role)
        target.groups.add(role_group)
        return target

    @staticmethod
    @transaction.atomic
    def reset_password(actor: User, target_id: int) -> tuple[User, str]:
        UserAccessService._ensure_manager_or_admin(actor)
        UserAccessService._ensure_actor_scope(actor)
        target = AppUser.objects.get(id=target_id)
        UserAccessService._check_scope(actor, target)
        password = secrets.token_urlsafe(12)
        target.set_password(password)
        target.must_change_password = True
        target.save(update_fields=["password", "must_change_password"])
        return target, password

    @staticmethod
    @transaction.atomic
    def set_password(
        actor: User,
        target_id: int,
        password: str | None = None,
        generate_temporary: bool = False,
    ) -> tuple[User, str | None]:
        UserAccessService._ensure_manager_or_admin(actor)
        UserAccessService._ensure_actor_scope(actor)
        target = AppUser.objects.get(id=target_id)
        UserAccessService._check_scope(actor, target)

        if not UserAccessService._is_admin(
            actor
        ) and UserAccessService._target_is_admin(target):
            raise PermissionDenied(
                "Менеджер не может менять пароль администратора"
            )

        password_value = (password or "").strip()
        if generate_temporary:
            next_password = secrets.token_urlsafe(12)
            temporary_password = next_password
        else:
            if len(password_value) < 8:
                raise ValueError("Пароль должен содержать минимум 8 символов")
            next_password = password_value
            temporary_password = None

        target.set_password(next_password)
        target.must_change_password = True
        target.save(update_fields=["password", "must_change_password"])
        return target, temporary_password

    @staticmethod
    @transaction.atomic
    def set_scope(
        actor: User,
        target_id: int,
        region_id: int | None,
    ) -> User:
        if not UserAccessService._is_admin(actor):
            raise PermissionDenied(
                "Изменение scope доступно только администратору"
            )
        target = AppUser.objects.get(id=target_id)
        target.region_id = region_id
        target.save(update_fields=["region_id"])
        return target

    @staticmethod
    @transaction.atomic
    def update_profile(
        actor: User,
        target_id: int,
        payload: AccessUpdatePayload,
    ) -> User:
        UserAccessService._ensure_manager_or_admin(actor)
        UserAccessService._ensure_actor_scope(actor)
        target = AppUser.objects.get(id=target_id)
        UserAccessService._check_scope(actor, target)

        if not UserAccessService._is_admin(
            actor
        ) and UserAccessService._target_is_admin(target):
            raise PermissionDenied(
                "Менеджер не может изменять профиль администратора"
            )

        if payload.email is not None:
            email = payload.email.strip()
            if not email:
                raise ValueError("Email не может быть пустым")
            target.email = email

        if payload.first_name is not None:
            target.first_name = payload.first_name.strip()

        if payload.last_name is not None:
            target.last_name = payload.last_name.strip()

        if payload.phone is not None:
            target.phone = payload.phone.strip() or None

        if payload.region_id is not None:
            if not UserAccessService._is_admin(actor):
                raise PermissionDenied(
                    "Менеджер не может менять регион сотрудника"
                )
            target.region_id = payload.region_id

        target.save()
        return target

    @staticmethod
    def get_scope_label(user: User) -> str:
        return UserAccessService._scope_label(user)
