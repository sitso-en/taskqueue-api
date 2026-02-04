"""Signal handlers for tasks."""

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Task
from .serializers import TaskListSerializer


@receiver(post_save, sender=Task)
def notify_task_list_update(sender, instance, created, **kwargs):
    """Notify WebSocket clients when tasks are created or updated."""
    channel_layer = get_channel_layer()

    if created:
        serializer = TaskListSerializer(instance)
        async_to_sync(channel_layer.group_send)(
            "tasks_all",
            {
                "type": "task_created",
                "task": serializer.data,
            },
        )
    else:
        async_to_sync(channel_layer.group_send)(
            "tasks_all",
            {
                "type": "task_update",
                "task_id": str(instance.id),
                "status": instance.status,
            },
        )
