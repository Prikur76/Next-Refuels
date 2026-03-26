# mypy: ignore-errors
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Optional

from django.contrib.auth.models import Group
from django.test import Client
from django.utils import timezone

from core.models import Car, FuelRecord, Region, User


@dataclass(frozen=True)
class UserSpec:
    username: str
    password: str
    groups: tuple[str, ...] = ()
    region: Optional[Region] = None
    must_change_password: bool = False
    is_active: bool = True


def create_region(
    *, name: str, short_name: str = "", active: bool = True
) -> Region:
    return Region.objects.create(
        name=name, short_name=short_name, active=active
    )


def ensure_group(name: str) -> Group:
    group, _ = Group.objects.get_or_create(name=name)
    return group


def create_user(
    *,
    username: str,
    password: str,
    groups: Iterable[str] = (),
    region: Optional[Region] = None,
    must_change_password: bool = False,
    is_active: bool = True,
    email: str = "",
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
) -> User:
    # Note: PhoneNumberField will parse/normalize on save.
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email or None,
        first_name=first_name,
        last_name=last_name,
        phone=phone or None,
        region=region,
        is_active=is_active,
    )
    user.must_change_password = must_change_password
    user.save(update_fields=["must_change_password", "is_active"])

    for group_name in groups:
        user.groups.add(ensure_group(group_name))
    return user


def login_client(client: Client, *, username: str, password: str) -> Client:
    client.login(username=username, password=password)
    return client


def create_car(
    *,
    code: str,
    state_number: str,
    model: str,
    region: Optional[Region],
    is_active: bool = True,
    status: str = "АКТИВЕН",
    department: str = "Dep",
    owner_inn: str = "1234567890",
    vin: str = "",
    manufacture_year: int = 2020,
) -> Car:
    return Car.objects.create(
        code=code,
        state_number=state_number,
        model=model,
        manufacture_year=manufacture_year,
        owner_inn=owner_inn,
        department=department,
        vin=vin,
        region=region,
        is_active=is_active,
        status=status,
    )


def create_fuel_record(
    *,
    car: Car,
    employee: User,
    liters: Decimal,
    fuel_type: str = "GASOLINE",
    source: str = "TGBOT",
    notes: str = "",
    filled_at: Optional[Any] = None,
) -> FuelRecord:
    return FuelRecord.objects.create_fuel_record(
        car=car,
        employee=employee,
        liters=liters,
        fuel_type=fuel_type,
        source=source,
        notes=notes,
        filled_at=filled_at or timezone.now(),
    )


def post_json(client: Client, url: str, payload: dict[str, Any]) -> Any:
    return client.post(
        url, data=json.dumps(payload), content_type="application/json"
    )


def patch_json(client: Client, url: str, payload: dict[str, Any]) -> Any:
    return client.patch(
        url, data=json.dumps(payload), content_type="application/json"
    )

