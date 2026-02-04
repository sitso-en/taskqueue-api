"""Celery tasks for the task queue."""

import logging
import time
import traceback

from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import DeadLetterQueue, Task, TaskStatus

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
