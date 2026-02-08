"""Admin configuration for tasks."""

from django.contrib import admin
from django.utils.html import format_html

from .models import DeadLetterQueue, Task, TaskStatus


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin interface for Task model."""

    list_display = [
        "id",
        "name",
        "task_type",
        "status_badge",
        "priority",
        "retry_count",
        "created_at",
        "duration_display",
    ]
    list_filter = ["status", "task_type", "priority", "created_at"]
    search_fields = ["id", "name", "celery_task_id"]
    readonly_fields = [
        "id",
        "celery_task_id",
        "retry_count",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "result",
        "error_message",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Task Info", {"fields": ("id", "name", "task_type", "payload", "tags", "metadata")}),
        ("Status", {"fields": ("status", "priority", "celery_task_id")}),
        ("Retry Config", {"fields": ("max_retries", "retry_count", "retry_delay")}),
        ("Timing", {"fields": ("created_at", "updated_at", "started_at", "completed_at", "scheduled_at")}),
        ("Result", {"fields": ("result", "error_message"), "classes": ("collapse",)}),
    )

    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            TaskStatus.PENDING: "#6c757d",
            TaskStatus.QUEUED: "#17a2b8",
            TaskStatus.RUNNING: "#ffc107",
            TaskStatus.SUCCESS: "#28a745",
            TaskStatus.FAILURE: "#dc3545",
            TaskStatus.REVOKED: "#6c757d",
            TaskStatus.RETRY: "#fd7e14",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def duration_display(self, obj):
        """Display task duration."""
        if obj.duration:
            return f"{obj.duration:.2f}s"
        return "-"

    duration_display.short_description = "Duration"

    actions = ["cancel_tasks", "retry_tasks"]

    @admin.action(description="Cancel selected tasks")
    def cancel_tasks(self, request, queryset):
        """Cancel selected tasks."""
        from taskqueue.celery import app

        cancelled = 0
        for task in queryset.filter(status__in=[TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING]):
            if task.celery_task_id:
                app.control.revoke(task.celery_task_id, terminate=True)
            task.mark_revoked()
            cancelled += 1

        self.message_user(request, f"Cancelled {cancelled} tasks.")

    @admin.action(description="Retry failed tasks")
    def retry_tasks(self, request, queryset):
        """Retry failed tasks."""
        from .queue_routing import get_queue_for_priority
        from .tasks import execute_task

        retried = 0
        for task in queryset.filter(status__in=[TaskStatus.FAILURE, TaskStatus.REVOKED]):
            task.status = TaskStatus.QUEUED
            task.error_message = ""
            task.result = None
            task.started_at = None
            task.completed_at = None
            task.save()
            execute_task.apply_async(
                args=[str(task.id)],
                queue=get_queue_for_priority(task.priority),
                priority=task.priority,
            )
            retried += 1

        self.message_user(request, f"Retried {retried} tasks.")


@admin.register(DeadLetterQueue)
class DeadLetterQueueAdmin(admin.ModelAdmin):
    """Admin interface for DeadLetterQueue."""

    list_display = [
        "id",
        "task_name",
        "task_type",
        "retry_count",
        "created_at",
        "reprocessed",
    ]
    list_filter = ["task_type", "reprocessed", "created_at"]
    search_fields = ["id", "task_name", "error_message"]
    readonly_fields = [
        "id",
        "original_task",
        "task_name",
        "task_type",
        "payload",
        "error_message",
        "traceback",
        "retry_count",
        "created_at",
        "reprocessed_at",
    ]
    ordering = ["-created_at"]

    actions = ["reprocess_entries"]

    @admin.action(description="Reprocess selected entries")
    def reprocess_entries(self, request, queryset):
        """Reprocess selected dead letter entries."""
        from .queue_routing import get_queue_for_priority
        from .tasks import execute_task
        from django.utils import timezone

        reprocessed = 0
        for entry in queryset.filter(reprocessed=False):
            task = Task.objects.create(
                name=f"[Reprocessed] {entry.task_name}",
                task_type=entry.task_type,
                payload=entry.payload,
                status=TaskStatus.QUEUED,
            )
            execute_task.apply_async(
                args=[str(task.id)],
                queue=get_queue_for_priority(task.priority),
                priority=task.priority,
            )
            entry.reprocessed = True
            entry.reprocessed_at = timezone.now()
            entry.save()
            reprocessed += 1

        self.message_user(request, f"Reprocessed {reprocessed} entries.")
