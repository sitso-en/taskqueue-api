"""Task URL configuration."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeadLetterQueueViewSet, TaskViewSet

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"dead-letters", DeadLetterQueueViewSet, basename="dead-letter")

urlpatterns = [
    path("", include(router.urls)),
]
