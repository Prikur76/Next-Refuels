from __future__ import annotations

from typing import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect


class AppEntryRedirectMiddleware:
    """
    Route entry requests from Django to the correct destination.

    Requirements:
    - GET `/` on Django:
      - admin user -> redirect to `/admin/` (on port 8000)
      - anonymous -> redirect to frontend `/login` (port 5173)
      - authenticated non-admin -> redirect to frontend `/`
    - everything else (except API, admin and auth endpoints, static/media)
      -> redirect to frontend `/`.
    """

    _ADMIN_GROUP_NAME = "Администратор"
    _ADMIN_PREFIX = "/admin"
    _FRONTEND_LOGIN_PATH = "/login"
    _FRONTEND_MAIN_PATH = "/"

    _ALLOW_PREFIXES = (
        "/api/v1/",
        "/static/",
        "/media/",
        "/accounts/",
        "/health/",
        "/robots.txt",
    )

    def __init__(
        self, get_response: Callable[[HttpRequest], HttpResponse]
    ):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path or ""

        # Keep admin HTML <head> icons coming from the Next frontend.
        # Without this, requests like `/favicon.png` would be redirected
        # to the frontend main HTML instead of returning the image.
        if path in ("/favicon.png", "/apple-touch-icon.png", "/logo.png"):
            frontend_base_url = self._frontend_base_url()
            return self._redirect(
                f"{frontend_base_url}{path}"
            )

        # If user opens Django login URL directly in browser, route them
        # to the frontend login page. Keep POST working for the form.
        if (
            path.startswith("/accounts/login/")
            and request.method in ("GET", "HEAD")
        ):
            frontend_base_url = self._frontend_base_url()
            return self._redirect(f"{frontend_base_url}{self._FRONTEND_LOGIN_PATH}")

        # Root entry:
        if path == "/":
            return self._handle_root(request)

        # Let admin + already handled by AdminGateMiddleware.
        if path.startswith(self._ADMIN_PREFIX):
            return self.get_response(request)

        # Allow health/static/media/auth/API.
        if any(path.startswith(prefix) for prefix in self._ALLOW_PREFIXES):
            return self.get_response(request)

        # Everything else -> frontend main.
        return self._redirect_to_frontend_main()

    def _handle_root(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        frontend_base_url = self._frontend_base_url()

        if user is None or not getattr(user, "is_authenticated", False):
            return self._redirect(f"{frontend_base_url}{self._FRONTEND_LOGIN_PATH}")

        # Authenticated:
        if self._is_admin_user(user):
            admin_url = request.build_absolute_uri("/admin/")
            return HttpResponseRedirect(admin_url)

        return self._redirect_to_frontend_main()

    def _is_admin_user(self, user) -> bool:
        if bool(getattr(user, "is_superuser", False)):
            return True

        # Reuse the same cached key as AdminGateMiddleware to avoid
        # repeated group membership DB queries during redirects.
        cache_key = f"admin_gate:is_admin_group:{user.id}"
        cached = cache.get(cache_key)
        if isinstance(cached, bool):
            return cached

        is_admin_group = user.groups.filter(
            name=self._ADMIN_GROUP_NAME
        ).exists()
        cache.set(cache_key, bool(is_admin_group), 60)
        return bool(is_admin_group)

    @staticmethod
    def _redirect(url: str) -> HttpResponseRedirect:
        return HttpResponseRedirect(url)

    def _redirect_to_frontend_main(self) -> HttpResponseRedirect:
        return self._redirect(f"{self._frontend_base_url()}{self._FRONTEND_MAIN_PATH}")

    def _frontend_base_url(self) -> str:
        base_url = getattr(
            settings,
            "FRONTEND_BASE_URL",
            "http://localhost:5173",
        )
        return str(base_url).rstrip("/")

