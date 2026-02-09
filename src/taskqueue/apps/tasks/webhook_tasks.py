"""Celery tasks for delivering webhooks."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import CallbackStatus, Task
from .webhooks import build_webhook_payload, post_webhook, prepare_headers

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=10)
def deliver_webhook(self, task_id: str, event: str):
    """Deliver webhook callback for a given task/event."""
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        logger.warning(f"Webhook delivery skipped: task {task_id} not found")
        return

    if not task.callback_url:
        return

    if task.callback_attempts >= task.callback_max_attempts:
        task.callback_status = CallbackStatus.FAILURE
        task.save(update_fields=["callback_status", "updated_at"])
        return

    task.callback_attempts += 1
    task.callback_last_attempt_at = timezone.now()
    task.save(update_fields=["callback_attempts", "callback_last_attempt_at", "updated_at"])

    payload = build_webhook_payload(task, event)
    import json

    body_bytes = json.dumps(payload).encode("utf-8")
    headers = prepare_headers(task, event, body_bytes)

    status_code, response_body = post_webhook(task.callback_url, headers, body_bytes)

    task.callback_last_response_code = status_code
    task.callback_last_response_body = response_body[:4000]

    if 200 <= status_code < 300:
        task.callback_status = CallbackStatus.SUCCESS
        task.callback_last_error = ""
        task.save(
            update_fields=[
                "callback_status",
                "callback_last_response_code",
                "callback_last_response_body",
                "callback_last_error",
                "updated_at",
            ]
        )
        return

    task.callback_last_error = f"Non-2xx response: {status_code}"
    task.save(
        update_fields=[
            "callback_last_response_code",
            "callback_last_response_body",
            "callback_last_error",
            "updated_at",
        ]
    )

    # Trigger Celery retry
    raise ValueError(f"Webhook returned {status_code}")
