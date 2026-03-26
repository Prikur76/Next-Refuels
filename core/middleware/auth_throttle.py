from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render


class AuthThrottleMiddleware:
    """Простое ограничение brute-force для POST /accounts/login/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "AUTH_THROTTLE_ENABLED", True):
            return self.get_response(request)

        if not self._is_login_post(request):
            return self.get_response(request)

        key = self._key(request)
        lock_seconds = settings.AUTH_THROTTLE_LOCK_SECONDS
        if cache.get(f"{key}:locked"):
            return self._locked_response(request, lock_seconds)

        response = self.get_response(request)
        if request.user.is_authenticated:
            cache.delete(key)
            cache.delete(f"{key}:locked")
            return response

        fail_count = cache.get(key, 0) + 1
        cache.set(key, fail_count, settings.AUTH_THROTTLE_WINDOW_SECONDS)
        if fail_count >= settings.AUTH_THROTTLE_LIMIT:
            cache.set(f"{key}:locked", True, lock_seconds)
            return self._locked_response(request, lock_seconds)

        return response

    @staticmethod
    def _is_login_post(request) -> bool:
        return request.path == "/accounts/login/" and request.method == "POST"

    @staticmethod
    def _key(request) -> str:
        username = (request.POST.get("username") or "").strip().lower()
        ip = request.META.get("REMOTE_ADDR", "unknown")
        return f"auth:login:fail:{ip}:{username}"

    @staticmethod
    def _locked_response(request, lock_seconds: int) -> HttpResponse:
        context = {
            "message": (
                "Превышено количество попыток входа. "
                f"Повторите через {lock_seconds} секунд."
            )
        }
        return render(
            request,
            "web/access_denied.html",
            context=context,
            status=429,
        )
