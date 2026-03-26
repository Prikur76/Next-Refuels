from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone


def health_check(request: HttpRequest) -> JsonResponse:
    """Simple healthcheck endpoint for containers/proxy."""
    return JsonResponse(
        {"status": "healthy", "timestamp": timezone.now()}
    )


def access_denied_view(
    request: HttpRequest, message: str = "Доступ ограничен"
) -> HttpResponse:
    """Render legacy access denied page."""
    context = {"message": message}
    return render(
        request, "web/access_denied.html", context, status=403
    )


class FrontendFriendlyLoginView(LoginView):
    """
    Redirect failed Django form login back to frontend /login.

    This avoids rendering legacy Django HTML inside the frontend app when
    credentials are invalid.
    """

    template_name = "web/login.html"

    def form_invalid(self, form):
        frontend_base_url = str(
            getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173")
        ).rstrip("/")
        username = (self.request.POST.get("username", "") or "").strip()
        next_url = (self.request.POST.get("next", "/") or "/").strip()
        safe_next = next_url if next_url.startswith("/") else "/"
        target = (
            f"{frontend_base_url}/login"
            f"?error=invalid_credentials"
            f"&username={quote(username)}"
            f"&next={quote(safe_next)}"
        )
        return HttpResponseRedirect(target)
