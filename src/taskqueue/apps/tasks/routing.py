"""WebSocket URL routing."""

from django.urls import path

from .consumers import TaskListConsumer, TaskStatusConsumer

websocket_urlpatterns = [
    path("ws/tasks/<uuid:task_id>/", TaskStatusConsumer.as_asgi()),
    path("ws/tasks/", TaskListConsumer.as_asgi()),
]
