"""Task queue routing based on priority."""

from __future__ import annotations

from .models import TaskPriority

QUEUE_CRITICAL = "critical"
QUEUE_HIGH = "high"
QUEUE_DEFAULT = "default"
QUEUE_LOW = "low"

ALL_TASK_QUEUES = (QUEUE_CRITICAL, QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW)


def get_queue_for_priority(priority: int) -> str:
    """Map a task priority to a Celery queue name."""
    if priority >= TaskPriority.CRITICAL:
        return QUEUE_CRITICAL
    if priority >= TaskPriority.HIGH:
        return QUEUE_HIGH
    if priority <= TaskPriority.LOW:
        return QUEUE_LOW
    return QUEUE_DEFAULT
