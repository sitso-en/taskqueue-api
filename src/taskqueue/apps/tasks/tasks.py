"""Celery tasks for the task queue."""

import logging
import time
import traceback

from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import DeadLetterQueue, Task, TaskStatus
from .webhooks import enqueue_webhook

logger = logging.getLogger(__name__)


def notify_task_update(task: Task):
    """Send task status update via WebSocket."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"task_{task.id}",
        {
            "type": "task_update",
            "task_id": str(task.id),
            "status": task.status,
            "result": task.result,
            "error_message": task.error_message,
        },
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def execute_task(self, task_id: str):
    """
    Execute a queued task.
    
    This is the main task executor that processes tasks from the queue.
    """
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        logger.error(f"Task {task_id} not found")
        return {"error": "Task not found"}

    # Update task with Celery task ID
    task.celery_task_id = self.request.id
    task.save(update_fields=["celery_task_id"])

    # Mark as running
    task.mark_started()
    notify_task_update(task)

    try:
        # Route to specific task handler
        result = route_task(task)
        
        task.mark_success(result)
        notify_task_update(task)
        enqueue_webhook(task, "task.succeeded")

        logger.info(f"Task {task_id} completed successfully")
        return result

    except Exception as exc:
        task.retry_count += 1
        task.save(update_fields=["retry_count"])

        if task.retry_count >= task.max_retries:
            # Move to dead letter queue
            error_tb = traceback.format_exc()
            task.mark_failure(str(exc))
            
            DeadLetterQueue.objects.create(
                original_task=task,
                task_name=task.name,
                task_type=task.task_type,
                payload=task.payload,
                error_message=str(exc),
                traceback=error_tb,
                retry_count=task.retry_count,
            )
            
            notify_task_update(task)
            enqueue_webhook(task, "task.failed")
            logger.error(f"Task {task_id} moved to dead letter queue: {exc}")
            return {"error": str(exc), "dead_letter": True}

        # Retry
        task.status = TaskStatus.RETRY
        task.save(update_fields=["status"])
        notify_task_update(task)
        
        logger.warning(f"Task {task_id} retry {task.retry_count}/{task.max_retries}: {exc}")
        raise self.retry(exc=exc, countdown=task.retry_delay * task.retry_count)


def route_task(task: Task) -> dict:
    """Route task to appropriate handler based on task_type."""
    handlers = {
        "echo": handle_echo_task,
        "compute": handle_compute_task,
        "sleep": handle_sleep_task,
        "http_request": handle_http_request_task,
        "process_data": handle_process_data_task,
        "send_email": handle_send_email_task,
        "resize_image": handle_resize_image_task,
        "generate_report": handle_generate_report_task,
    }

    handler = handlers.get(task.task_type)
    if not handler:
        raise ValueError(f"Unknown task type: {task.task_type}")

    return handler(task.payload)


# --- Task Handlers ---

def handle_echo_task(payload: dict) -> dict:
    """Simple echo task for testing."""
    return {"echoed": payload}


def handle_compute_task(payload: dict) -> dict:
    """Simulate a computation task."""
    operation = payload.get("operation", "sum")
    numbers = payload.get("numbers", [])

    if operation == "sum":
        result = sum(numbers)
    elif operation == "product":
        result = 1
        for n in numbers:
            result *= n
    elif operation == "average":
        result = sum(numbers) / len(numbers) if numbers else 0
    else:
        raise ValueError(f"Unknown operation: {operation}")

    return {"operation": operation, "result": result}


def handle_sleep_task(payload: dict) -> dict:
    """Simulate a long-running task."""
    duration = min(payload.get("duration", 1), 300)  # Max 5 minutes
    time.sleep(duration)
    return {"slept_for": duration}


def handle_http_request_task(payload: dict) -> dict:
    """Simulate an HTTP request task."""
    import urllib.request
    import urllib.error
    
    url = payload.get("url")
    if not url:
        raise ValueError("URL is required")

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return {
                "url": url,
                "status_code": response.status,
                "content_length": len(response.read()),
            }
    except urllib.error.URLError as e:
        raise ValueError(f"HTTP request failed: {e}")


def handle_process_data_task(payload: dict) -> dict:
    """Simulate a data processing task."""
    data = payload.get("data", [])
    operation = payload.get("operation", "transform")

    if operation == "transform":
        processed = [item.upper() if isinstance(item, str) else item * 2 for item in data]
    elif operation == "filter":
        predicate = payload.get("predicate", "truthy")
        if predicate == "truthy":
            processed = [item for item in data if item]
        elif predicate == "even":
            processed = [item for item in data if isinstance(item, int) and item % 2 == 0]
        else:
            processed = data
    elif operation == "aggregate":
        processed = {"count": len(data), "items": data}
    else:
        processed = data

    return {"processed": processed, "count": len(data)}


def handle_send_email_task(payload: dict) -> dict:
    """
    Simulate sending an email.
    
    In production, integrate with SMTP, SendGrid, Mailgun, etc.
    """
    to = payload.get("to")
    subject = payload.get("subject", "No Subject")
    body = payload.get("body", "")
    
    if not to:
        raise ValueError("'to' email address is required")
    
    # Validate email format (basic check)
    if "@" not in to or "." not in to:
        raise ValueError(f"Invalid email address: {to}")
    
    # Simulate sending delay
    time.sleep(0.5)
    
    # In production, this would call your email service
    # Example: sendgrid.send(to=to, subject=subject, body=body)
    
    return {
        "status": "sent",
        "to": to,
        "subject": subject,
        "body_length": len(body),
        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def handle_resize_image_task(payload: dict) -> dict:
    """
    Simulate image resizing.
    
    In production, use Pillow or similar library.
    """
    image_url = payload.get("image_url")
    width = payload.get("width")
    height = payload.get("height")
    format = payload.get("format", "jpeg")
    
    if not image_url:
        raise ValueError("'image_url' is required")
    
    if not width and not height:
        raise ValueError("At least 'width' or 'height' must be specified")
    
    valid_formats = ["jpeg", "png", "webp", "gif"]
    if format not in valid_formats:
        raise ValueError(f"Invalid format. Must be one of: {', '.join(valid_formats)}")
    
    # Simulate processing time
    time.sleep(1)
    
    # In production, this would:
    # 1. Download the image
    # 2. Resize using Pillow
    # 3. Upload to storage (S3, etc.)
    # 4. Return the new URL
    
    return {
        "status": "resized",
        "original_url": image_url,
        "new_dimensions": {"width": width, "height": height},
        "format": format,
        "output_url": f"https://cdn.example.com/resized/{width}x{height}.{format}",
    }


def handle_generate_report_task(payload: dict) -> dict:
    """
    Simulate report generation.
    
    In production, query databases, generate PDFs, etc.
    """
    report_type = payload.get("report_type", "summary")
    date_range = payload.get("date_range", {})
    filters = payload.get("filters", {})
    output_format = payload.get("output_format", "json")
    
    valid_types = ["summary", "detailed", "analytics", "financial"]
    if report_type not in valid_types:
        raise ValueError(f"Invalid report_type. Must be one of: {', '.join(valid_types)}")
    
    valid_formats = ["json", "csv", "pdf", "xlsx"]
    if output_format not in valid_formats:
        raise ValueError(f"Invalid output_format. Must be one of: {', '.join(valid_formats)}")
    
    # Simulate report generation time
    time.sleep(2)
    
    # In production, this would query your data sources and generate the report
    report_id = f"RPT-{int(time.time())}"
    
    return {
        "status": "generated",
        "report_id": report_id,
        "report_type": report_type,
        "output_format": output_format,
        "date_range": date_range,
        "filters_applied": filters,
        "download_url": f"https://reports.example.com/{report_id}.{output_format}",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
