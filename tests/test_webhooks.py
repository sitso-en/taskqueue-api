"""Unit tests for webhook helpers."""

from unittest.mock import patch

import pytest

from taskqueue.apps.tasks.models import Task, WebhookDelivery
from taskqueue.apps.tasks.webhooks import build_webhook_payload, compute_signature, enqueue_webhook


@pytest.mark.django_db
def test_build_webhook_payload_structure():
    task = Task.objects.create(name="T", task_type="echo", payload={"a": 1})
    payload = build_webhook_payload(task, "task.succeeded")

    assert payload["event"] == "task.succeeded"
    assert "task" in payload
    assert payload["task"]["id"] == str(task.id)
    assert payload["task"]["task_type"] == "echo"


def test_compute_signature_stable():
    secret = "supersecret"
    body = b"{\"hello\": \"world\"}"
    sig1 = compute_signature(secret, body)
    sig2 = compute_signature(secret, body)
    assert sig1 == sig2
    assert len(sig1) == 64


@pytest.mark.django_db
def test_enqueue_webhook_calls_celery_task():
    task = Task.objects.create(
        name="T",
        task_type="echo",
        callback_url="https://example.com/webhook",
        callback_events=["task.succeeded"],
    )

    with patch("taskqueue.apps.tasks.webhook_tasks.deliver_webhook.apply_async") as apply_async:
        delivery = enqueue_webhook(task, "task.succeeded")

    assert delivery is not None
    assert WebhookDelivery.objects.count() == 1

    apply_async.assert_called_once()
    assert apply_async.call_args.kwargs["args"] == [str(delivery.id)]
