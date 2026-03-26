from __future__ import annotations

from typing import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect


class AdminGateMiddleware:
    """
    Restrict access to Django admin.

    If a request targets `/admin/` and the user is not an administrator,
    redirect to the frontend main page.
    """

    _ADMIN_PREFIX = "/admin"
    _ADMIN_GROUP_NAME = "Администратор"
    _CACHE_TTL_SECONDS = 60

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.path.startswith(self._ADMIN_PREFIX):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user is None:
            return self._redirect_to_frontend()

        if self._is_admin(user):
            return self.get_response(request)

        return self._redirect_to_frontend()

    def _is_admin(self, user) -> bool:
        """
        Fast admin check with short cache.

        Note: group membership changes will be reflected after TTL.
        """
        if not getattr(user, "is_authenticated", False):
            return False

        if bool(getattr(user, "is_superuser", False)):
            return True

        cache_key = f"admin_gate:is_admin_group:{user.id}"
        cached = cache.get(cache_key)
        if isinstance(cached, bool):
            return cached

        is_admin_group = user.groups.filter(
            name=self._ADMIN_GROUP_NAME
        ).exists()
        cache.set(cache_key, bool(is_admin_group), self._CACHE_TTL_SECONDS)
        return bool(is_admin_group)

    @staticmethod
    def _redirect_to_frontend() -> HttpResponseRedirect:
        base_url = getattr(
            settings,
            "FRONTEND_BASE_URL",
            "http://localhost:5173",
        )
        base_url = str(base_url).rstrip("/")
        return HttpResponseRedirect(f"{base_url}/")

