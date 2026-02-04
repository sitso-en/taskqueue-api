"""Tasks app configuration."""

from django.apps import AppConfig


class TasksConfig(AppConfig):
    """Tasks application config."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "taskqueue.apps.tasks"
    label = "tasks"

    def ready(self):
        from . import signals  # noqa: F401
