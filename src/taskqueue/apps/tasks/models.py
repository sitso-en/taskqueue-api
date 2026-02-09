"""Task models."""

import uuid

from django.db import models
from django.utils import timezone


class TaskStatus(models.TextChoices):
    """Task status choices."""

    PENDING = "pending", "Pending"
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure"
    REVOKED = "revoked", "Revoked"
    RETRY = "retry", "Retry"


class TaskPriority(models.IntegerChoices):
    """Task priority levels."""

    LOW = 1, "Low"
    NORMAL = 5, "Normal"
    HIGH = 10, "High"
    CRITICAL = 20, "Critical"


class CallbackStatus(models.TextChoices):
    """Webhook callback delivery status."""

    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure"


class Task(models.Model):
    """Represents a task submitted to the queue."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    task_type = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        db_index=True,
    )
    priority = models.IntegerField(
        choices=TaskPriority.choices,
        default=TaskPriority.NORMAL,
        db_index=True,
    )
    
    # Celery task tracking
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    # Retry configuration
    max_retries = models.PositiveIntegerField(default=3)
    retry_count = models.PositiveIntegerField(default=0)
    retry_delay = models.PositiveIntegerField(default=60, help_text="Delay between retries in seconds")
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="Schedule task for later execution")
    
    # Result
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Webhooks
    callback_url = models.URLField(blank=True, null=True)
    callback_headers = models.JSONField(default=dict, blank=True)
    callback_secret = models.CharField(max_length=255, blank=True)
    callback_events = models.JSONField(
        default=list,
        blank=True,
        help_text="Events to notify (e.g. task.succeeded, task.failed, task.revoked)",
    )
    callback_max_attempts = models.PositiveIntegerField(default=5)
    callback_attempts = models.PositiveIntegerField(default=0)
    callback_status = models.CharField(
        max_length=20,
        choices=CallbackStatus.choices,
        default=CallbackStatus.PENDING,
        db_index=True,
    )
    callback_last_attempt_at = models.DateTimeField(null=True, blank=True)
    callback_last_response_code = models.IntegerField(null=True, blank=True)
    callback_last_response_body = models.TextField(blank=True)
    callback_last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["task_type", "status"]),
            models.Index(fields=["priority", "status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.id})"

    @property
    def duration(self) -> float | None:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def mark_started(self):
        """Mark task as started."""
        self.status = TaskStatus.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

    def mark_success(self, result=None):
        """Mark task as successful."""
        self.status = TaskStatus.SUCCESS
        self.completed_at = timezone.now()
        self.result = result
        self.save(update_fields=["status", "completed_at", "result", "updated_at"])

    def mark_failure(self, error_message: str):
        """Mark task as failed."""
        self.status = TaskStatus.FAILURE
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=["status", "completed_at", "error_message", "updated_at"])

    def mark_revoked(self):
        """Mark task as revoked/cancelled."""
        self.status = TaskStatus.REVOKED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])


class DeadLetterQueue(models.Model):
    """Store failed tasks that have exhausted retries."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        related_name="dead_letters",
    )
    
    task_name = models.CharField(max_length=255)
    task_type = models.CharField(max_length=255)
    payload = models.JSONField(default=dict)
    
    error_message = models.TextField()
    traceback = models.TextField(blank=True)
    
    retry_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    reprocessed = models.BooleanField(default=False)
    reprocessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Dead letter queue"

    def __str__(self):
        return f"DLQ: {self.task_name} ({self.id})"
