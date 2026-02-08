"""Unit tests for queue routing."""

import pytest

from taskqueue.apps.tasks.models import TaskPriority
from taskqueue.apps.tasks.queue_routing import (
    QUEUE_CRITICAL,
    QUEUE_DEFAULT,
    QUEUE_HIGH,
    QUEUE_LOW,
    get_queue_for_priority,
)


@pytest.mark.parametrize(
    "priority,expected",
    [
        (TaskPriority.LOW, QUEUE_LOW),
        (2, QUEUE_DEFAULT),
        (TaskPriority.NORMAL, QUEUE_DEFAULT),
        (TaskPriority.HIGH, QUEUE_HIGH),
        (15, QUEUE_HIGH),
        (TaskPriority.CRITICAL, QUEUE_CRITICAL),
        (25, QUEUE_CRITICAL),
    ],
)
def test_get_queue_for_priority(priority, expected):
    assert get_queue_for_priority(int(priority)) == expected
