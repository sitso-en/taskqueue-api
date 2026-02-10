"""Celery tasks for delivering webhooks."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import CallbackStatus, Task, WebhookDelivery, WebhookDeliveryStatus
from .webhooks import post_webhook

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=10)
def deliver_webhook(self, delivery_id: str):
    """Deliver webhook callback for an existing delivery record."""
    try:
        delivery = WebhookDelivery.objects.select_related("task").get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        logger.warning(f"Webhook delivery skipped: delivery {delivery_id} not found")
        return

    task: Task = delivery.task

    if not delivery.request_url:
        return

    if delivery.attempts >= task.callback_max_attempts:
        delivery.status = WebhookDeliveryStatus.FAILURE
        delivery.error_message = "Max attempts exceeded"
        delivery.save(update_fields=["status", "error_message"])

        task.callback_status = CallbackStatus.FAILURE
        task.save(update_fields=["callback_status", "updated_at"])
        return

    now = timezone.now()

    delivery.attempts += 1
    delivery.last_attempt_at = now
    delivery.save(update_fields=["attempts", "last_attempt_at"])

    task.callback_attempts += 1
    task.callback_last_attempt_at = now
    task.save(update_fields=["callback_attempts", "callback_last_attempt_at", "updated_at"])

    headers = delivery.request_headers or {}
    body_bytes = (delivery.request_body or "").encode("utf-8")

    try:
        status_code, response_body = post_webhook(delivery.request_url, headers, body_bytes)
    except Exception as e:
        delivery.status = WebhookDeliveryStatus.FAILURE
        delivery.error_message = str(e)
        delivery.save(update_fields=["status", "error_message"])

        task.callback_last_error = str(e)
        task.save(update_fields=["callback_last_error", "updated_at"])
        raise

    delivery.response_status_code = status_code
    delivery.response_body = response_body[:4000]

    task.callback_last_response_code = status_code
    task.callback_last_response_body = response_body[:4000]

    if 200 <= status_code < 300:
        delivery.status = WebhookDeliveryStatus.SUCCESS
        delivery.error_message = ""
        delivery.save(update_fields=["status", "response_status_code", "response_body", "error_message"])

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

    delivery.status = WebhookDeliveryStatus.FAILURE
    delivery.error_message = f"Non-2xx response: {status_code}"
    delivery.save(update_fields=["status", "response_status_code", "response_body", "error_message"])

    task.callback_last_error = f"Non-2xx response: {status_code}"
    task.save(
        update_fields=[
            "callback_last_response_code",
            "callback_last_response_body",
            "callback_last_error",
            "updated_at",
        ]
    )

    raise ValueError(f"Webhook returned {status_code}")
