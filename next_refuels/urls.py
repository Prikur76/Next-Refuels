"""
URL configuration for next_refuels project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import render
from django.urls import include, path

from core import api_views
from core.api import api
from core.views import FrontendFriendlyLoginView, access_denied_view

urlpatterns = [
    path("", include("core.urls")),
    path("api/v1/", api.urls),
    path(
        "api/v1/reports/export/csv/",
        api_views.export_reports_csv,
        name="api_export_reports_csv",
    ),
    path(
        "api/v1/reports/export/csv",
        api_views.export_reports_csv,
        name="api_export_reports_csv_no_slash",
    ),
    path(
        "api/v1/reports/export/xlsx/",
        api_views.export_reports_xlsx,
        name="api_export_reports_xlsx",
    ),
    path(
        "api/v1/reports/export/xlsx",
        api_views.export_reports_xlsx,
        name="api_export_reports_xlsx_no_slash",
    ),
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        FrontendFriendlyLoginView.as_view(),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="/"),
        name="logout",
    ),
    # Accept logout POST without trailing slash to avoid APPEND_SLASH POST errors
    path(
        "accounts/logout",
        auth_views.LogoutView.as_view(next_page="/"),
        name="logout_no_slash",
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )


# Обработчики ошибок 403, 404, 500
def handler403(request, exception=None):
    return access_denied_view(
        request,
        "Недостаточно прав для выполнения операции.",
    )


def handler404(request, exception=None):
    return render(request, "404.html", status=404)


def handler500(request):
    return render(request, "500.html", status=500)


# Expose the handlers with their original names.
