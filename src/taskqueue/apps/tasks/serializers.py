"""Task serializers."""

from rest_framework import serializers

from .models import DeadLetterQueue, Task, TaskPriority, TaskStatus


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for Task model."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    duration = serializers.FloatField(read_only=True)

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
        ]
        read_only_fields = [
            "id",
            "celery_task_id",
            "retry_count",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "result",
            "error_message",
            "duration",
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tasks."""

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


class TaskListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing tasks."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    duration = serializers.FloatField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "task_type",
            "status",
            "status_display",
            "priority",
            "created_at",
            "completed_at",
            "duration",
        ]


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
