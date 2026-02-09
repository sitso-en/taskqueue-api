"""Task API views."""

from django.db.models import Avg, Count, F
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DeadLetterQueue, Task, TaskStatus
from .serializers import (
    DeadLetterQueueSerializer,
    TaskCreateSerializer,
    TaskListSerializer,
    TaskSerializer,
    TaskStatsSerializer,
)
from .queue_routing import get_queue_for_priority
from .tasks import execute_task
from .webhooks import enqueue_webhook


class TaskViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tasks."""

    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    filterset_fields = ["status", "task_type", "priority"]
    search_fields = ["name", "tags"]
    ordering_fields = ["created_at", "priority", "status"]

    def get_serializer_class(self):
        if self.action == "list":
            return TaskListSerializer
        if self.action == "create":
            return TaskCreateSerializer
        return TaskSerializer

    def create(self, request, *args, **kwargs):
        """Create and queue a new task."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()

        # Queue task for execution
        task.status = TaskStatus.QUEUED
        task.save(update_fields=["status"])

        queue = get_queue_for_priority(task.priority)

        # Schedule based on scheduled_at or execute immediately
        if task.scheduled_at and task.scheduled_at > timezone.now():
            execute_task.apply_async(
                args=[str(task.id)],
                eta=task.scheduled_at,
                queue=queue,
                priority=task.priority,
            )
        else:
            execute_task.apply_async(
                args=[str(task.id)],
                queue=queue,
                priority=task.priority,
            )

        output_serializer = TaskSerializer(task)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel a pending or queued task."""
        task = self.get_object()

        if task.status not in [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING]:
            return Response(
                {"error": f"Cannot cancel task with status: {task.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Revoke Celery task if it exists
        if task.celery_task_id:
            from taskqueue.celery import app
            app.control.revoke(task.celery_task_id, terminate=True)

        task.mark_revoked()
        enqueue_webhook(task, "task.revoked")
        serializer = TaskSerializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        """Retry a failed task."""
        task = self.get_object()

        if task.status not in [TaskStatus.FAILURE, TaskStatus.REVOKED]:
            return Response(
                {"error": f"Cannot retry task with status: {task.status}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Reset task state
        task.status = TaskStatus.QUEUED
        task.error_message = ""
        task.result = None
        task.started_at = None
        task.completed_at = None
        task.save()

        # Re-queue
        execute_task.apply_async(
            args=[str(task.id)],
            queue=get_queue_for_priority(task.priority),
            priority=task.priority,
        )

        serializer = TaskSerializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def trigger_webhook(self, request, pk=None):
        """Manually enqueue a webhook for this task (useful for debugging)."""
        task = self.get_object()
        event = request.data.get("event")

        if not event:
            event = {
                TaskStatus.SUCCESS: "task.succeeded",
                TaskStatus.FAILURE: "task.failed",
                TaskStatus.REVOKED: "task.revoked",
            }.get(task.status, "task.updated")

        enqueue_webhook(task, event)
        return Response({"queued": True, "event": event})

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get task statistics."""
        stats = {
            "total": Task.objects.count(),
            "pending": Task.objects.filter(status=TaskStatus.PENDING).count(),
            "queued": Task.objects.filter(status=TaskStatus.QUEUED).count(),
            "running": Task.objects.filter(status=TaskStatus.RUNNING).count(),
            "success": Task.objects.filter(status=TaskStatus.SUCCESS).count(),
            "failure": Task.objects.filter(status=TaskStatus.FAILURE).count(),
            "revoked": Task.objects.filter(status=TaskStatus.REVOKED).count(),
            "dead_letters": DeadLetterQueue.objects.filter(reprocessed=False).count(),
            "avg_duration": Task.objects.filter(
                status=TaskStatus.SUCCESS,
                started_at__isnull=False,
                completed_at__isnull=False,
            ).aggregate(
                avg=Avg(F("completed_at") - F("started_at"))
            )["avg"],
        }

        if stats["avg_duration"]:
            stats["avg_duration"] = stats["avg_duration"].total_seconds()

        serializer = TaskStatsSerializer(stats)
        return Response(serializer.data)


class DeadLetterQueueViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing dead letter queue."""

    queryset = DeadLetterQueue.objects.all()
    serializer_class = DeadLetterQueueSerializer
    filterset_fields = ["task_type", "reprocessed"]

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        """Reprocess a dead letter queue entry."""
        dlq_entry = self.get_object()

        if dlq_entry.reprocessed:
            return Response(
                {"error": "Entry already reprocessed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create new task from DLQ entry
        task = Task.objects.create(
            name=f"[Reprocessed] {dlq_entry.task_name}",
            task_type=dlq_entry.task_type,
            payload=dlq_entry.payload,
            status=TaskStatus.QUEUED,
        )

        # Queue for execution
        execute_task.apply_async(
            args=[str(task.id)],
            queue=get_queue_for_priority(task.priority),
            priority=task.priority,
        )

        # Mark as reprocessed
        dlq_entry.reprocessed = True
        dlq_entry.reprocessed_at = timezone.now()
        dlq_entry.save()

        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)
