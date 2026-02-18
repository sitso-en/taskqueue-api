"""
URL configuration for taskqueue project.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny


def healthcheck(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", healthcheck, name="healthcheck"),
    path("health", healthcheck, name="healthcheck-no-slash"),
    path("health/", healthcheck, name="healthcheck-slash"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[AllowAny]), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="swagger-ui",
    ),
    path("api/v1/auth/", include("taskqueue.apps.core.urls")),
    path("api/v1/", include("taskqueue.apps.tasks.urls")),
    path("", include("django_prometheus.urls")),
]
