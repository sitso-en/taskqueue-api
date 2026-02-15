"""Task API views."""

from django.db.models import Avg, Count, F
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DeadLetterQueue, Task, TaskStatus, WebhookDelivery
from .serializers import (
    DeadLetterQueueSerializer,
    TaskCreateSerializer,
    TaskListSerializer,
    TaskSerializer,
    TaskStatsSerializer,
    WebhookDeliverySerializer,
)
from .queue_routing import get_queue_for_priority
from .tasks import execute_task
from .webhooks import enqueue_webhook


class TaskViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tasks."""

    queryset = Task.objects.all()

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user)
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
        task = serializer.save(owner=request.user)

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

        delivery = enqueue_webhook(task, event)
        return Response({"queued": True, "event": event, "delivery_id": str(delivery.id) if delivery else None})

    @action(detail=True, methods=["get"], url_path="webhook-deliveries")
    def webhook_deliveries(self, request, pk=None):
        """List webhook deliveries for this task."""
        task = self.get_object()
        qs = task.webhook_deliveries.all()

        event = request.query_params.get("event")
        status_param = request.query_params.get("status")
        limit = request.query_params.get("limit")

        if event:
            qs = qs.filter(event=event)
        if status_param:
            qs = qs.filter(status=status_param)
        if limit:
            try:
                qs = qs[: int(limit)]
            except (TypeError, ValueError):
                pass

        return Response(WebhookDeliverySerializer(qs, many=True).data)

    @action(
        detail=True,
        methods=["get"],
        url_path=r"webhook-deliveries/(?P<delivery_id>[^/.]+)",
    )
    def webhook_delivery_detail(self, request, pk=None, delivery_id=None):
        """Get a single webhook delivery record."""
        task = self.get_object()
        try:
            delivery = task.webhook_deliveries.get(id=delivery_id)
        except WebhookDelivery.DoesNotExist:
            return Response({"error": "Delivery not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response(WebhookDeliverySerializer(delivery).data)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"webhook-deliveries/(?P<delivery_id>[^/.]+)/replay",
    )
    def replay_webhook_delivery(self, request, pk=None, delivery_id=None):
        """Replay a specific webhook delivery."""
        task = self.get_object()

        try:
            delivery = task.webhook_deliveries.get(id=delivery_id)
        except WebhookDelivery.DoesNotExist:
            return Response({"error": "Delivery not found"}, status=status.HTTP_404_NOT_FOUND)

        replay = WebhookDelivery.objects.create(
            task=task,
            event=delivery.event,
            request_url=delivery.request_url,
            request_headers=delivery.request_headers,
            request_body=delivery.request_body,
            signature=delivery.signature,
            replay_of=delivery,
        )

        from .webhook_tasks import deliver_webhook

        deliver_webhook.apply_async(args=[str(replay.id)], queue="low", priority=1)

        return Response(WebhookDeliverySerializer(replay).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Get task statistics."""
        qs = Task.objects.filter(owner=request.user)
        stats = {
            "total": qs.count(),
            "pending": qs.filter(status=TaskStatus.PENDING).count(),
            "queued": qs.filter(status=TaskStatus.QUEUED).count(),
            "running": qs.filter(status=TaskStatus.RUNNING).count(),
            "success": qs.filter(status=TaskStatus.SUCCESS).count(),
            "failure": qs.filter(status=TaskStatus.FAILURE).count(),
            "revoked": qs.filter(status=TaskStatus.REVOKED).count(),
            "dead_letters": DeadLetterQueue.objects.filter(
                reprocessed=False, original_task__owner=request.user
            ).count(),
            "avg_duration": qs.filter(
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

    def get_queryset(self):
        return DeadLetterQueue.objects.filter(original_task__owner=self.request.user)
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
