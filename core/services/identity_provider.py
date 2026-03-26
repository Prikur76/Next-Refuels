from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import authenticate


@dataclass
class IdentityResult:
    success: bool
    user: object | None = None
    message: str = ""


class LocalIdentityProvider:
    provider_name = "local"

    def authenticate(self, username: str, password: str) -> IdentityResult:
        user = authenticate(username=username, password=password)
        if not user:
            return IdentityResult(
                success=False,
                message="Неверные учетные данные",
            )
        return IdentityResult(success=True, user=user)


class OidcSamlIdentityProvider:
    provider_name = "sso"

    def authenticate(self, username: str, password: str) -> IdentityResult:
        return IdentityResult(
            success=False,
            message=(
                "SSO провайдер не подключен. Используется локальный fallback."
            ),
        )


def get_identity_provider():
    if settings.AUTH_PROVIDER.lower() in {"oidc", "saml", "sso"}:
        return OidcSamlIdentityProvider()
    return LocalIdentityProvider()
