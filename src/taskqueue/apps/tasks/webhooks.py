"""Webhook callback helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request

from django.utils import timezone

from .models import Task, WebhookDelivery
from .queue_routing import get_queue_for_priority


def build_webhook_payload(task: Task, event: str) -> dict:
    """Build a stable webhook payload."""
    return {
        "event": event,
        "sent_at": timezone.now().isoformat(),
        "task": {
            "id": str(task.id),
            "name": task.name,
            "task_type": task.task_type,
            "status": task.status,
            "priority": task.priority,
            "queue": get_queue_for_priority(task.priority),
            "payload": task.payload,
            "result": task.result,
            "error_message": task.error_message,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "tags": task.tags,
            "metadata": task.metadata,
        },
    }


def compute_signature(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature for payload."""
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    return mac.hexdigest()


def prepare_headers(task: Task, event: str, body: bytes) -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": "taskqueue-api/0.1",
        "X-Taskqueue-Event": event,
        "X-Taskqueue-Task-Id": str(task.id),
    }

    if isinstance(task.callback_headers, dict):
        for k, v in task.callback_headers.items():
            if isinstance(k, str) and isinstance(v, str):
                headers[k] = v

    if task.callback_secret:
        headers["X-Taskqueue-Signature"] = compute_signature(task.callback_secret, body)

    return headers


def post_webhook(url: str, headers: dict[str, str], body: bytes, timeout: int = 10) -> tuple[int, str]:
    """Send webhook POST request and return (status_code, response_body)."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(8192)
            return int(resp.status), data.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        data = e.read(8192) if hasattr(e, "read") else b""
        return int(getattr(e, "code", 0) or 0), data.decode("utf-8", errors="replace")


def should_send_event(task: Task, event: str) -> bool:
    if not task.callback_url:
        return False
    if not task.callback_events:
        return True
    if isinstance(task.callback_events, list):
        return event in task.callback_events
    return True


def enqueue_webhook(task: Task, event: str) -> WebhookDelivery | None:
    """Create a delivery history record and enqueue webhook delivery."""
    if not should_send_event(task, event):
        return None

    payload = build_webhook_payload(task, event)
    body_bytes = json.dumps(payload).encode("utf-8")
    headers = prepare_headers(task, event, body_bytes)

    delivery = WebhookDelivery.objects.create(
        task=task,
        event=event,
        request_url=task.callback_url,
        request_headers=headers,
        request_body=body_bytes.decode("utf-8", errors="replace"),
        signature=headers.get("X-Taskqueue-Signature", ""),
    )

    from .webhook_tasks import deliver_webhook  # local import to avoid circular deps

    deliver_webhook.apply_async(
        args=[str(delivery.id)],
        queue="low",
        priority=1,
    )

    return delivery
