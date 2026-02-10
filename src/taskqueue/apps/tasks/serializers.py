"""Task serializers."""

from rest_framework import serializers

from .models import DeadLetterQueue, Task, TaskPriority, TaskStatus, WebhookDelivery
from .queue_routing import get_queue_for_priority


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    duration = serializers.FloatField(read_only=True)
    queue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "task_type",
            "payload",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "queue",
            "celery_task_id",
            "max_retries",
            "retry_count",
            "retry_delay",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "scheduled_at",
            "result",
            "error_message",
            "duration",
            "tags",
            "metadata",
            "callback_url",
            "callback_events",
            "callback_status",
            "callback_attempts",
            "callback_max_attempts",
            "callback_last_attempt_at",
            "callback_last_response_code",
            "callback_last_error",
        ]
        read_only_fields = [
            "id",
            "queue",
            "celery_task_id",
            "retry_count",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "result",
            "error_message",
            "duration",
            "callback_url",
            "callback_events",
            "callback_status",
            "callback_attempts",
            "callback_max_attempts",
            "callback_last_attempt_at",
            "callback_last_response_code",
            "callback_last_error",
        ]


    def get_queue(self, obj):
        return get_queue_for_priority(obj.priority)


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tasks."""

    callback_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Task
        fields = [
            "name",
            "task_type",
            "payload",
            "priority",
            "max_retries",
            "retry_delay",
            "scheduled_at",
            "tags",
            "metadata",
            "callback_url",
            "callback_headers",
            "callback_secret",
            "callback_events",
            "callback_max_attempts",
        ]

    def validate_task_type(self, value):
        """Validate task type is supported."""
        valid_types = [
            "echo",
            "compute",
            "sleep",
            "http_request",
            "process_data",
            "send_email",
            "resize_image",
            "generate_report",
        ]
        if value not in valid_types:
            raise serializers.ValidationError(
                f"Invalid task type. Must be one of: {', '.join(valid_types)}"
            )
        return value

    def validate_callback_headers(self, value):
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("callback_headers must be a JSON object")
        for k, v in value.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise serializers.ValidationError("callback_headers must be string:string pairs")
        return value

    def validate_callback_events(self, value):
        if value in (None, ""):
            return []
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise serializers.ValidationError("callback_events must be a list of strings")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if attrs.get("callback_url") and not attrs.get("callback_events"):
            attrs["callback_events"] = ["task.succeeded", "task.failed", "task.revoked"]

        return attrs


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing tasks."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    duration = serializers.FloatField(read_only=True)
    queue = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "task_type",
            "status",
            "status_display",
            "priority",
            "queue",
            "created_at",
            "completed_at",
            "duration",
            "callback_status",
            "callback_attempts",
            "callback_last_response_code",
        ]

    def get_queue(self, obj):
        return get_queue_for_priority(obj.priority)


class DeadLetterQueueSerializer(serializers.ModelSerializer):
    """Serializer for DeadLetterQueue model."""

    class Meta:
        model = DeadLetterQueue
        fields = [
            "id",
            "original_task",
            "task_name",
            "task_type",
            "payload",
            "error_message",
            "traceback",
            "retry_count",
            "created_at",
            "reprocessed",
            "reprocessed_at",
        ]
        read_only_fields = ["id", "created_at", "reprocessed_at"]


class WebhookDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDelivery
        fields = [
            "id",
            "task",
            "event",
            "status",
            "attempts",
            "request_url",
            "request_headers",
            "request_body",
            "signature",
            "queued_at",
            "last_attempt_at",
            "response_status_code",
            "response_body",
            "error_message",
            "replay_of",
        ]
        read_only_fields = fields


class TaskStatsSerializer(serializers.Serializer):
    """Serializer for task statistics."""

    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    queued = serializers.IntegerField()
    running = serializers.IntegerField()
    success = serializers.IntegerField()
    failure = serializers.IntegerField()
    revoked = serializers.IntegerField()
    dead_letters = serializers.IntegerField()
    avg_duration = serializers.FloatField(allow_null=True)
