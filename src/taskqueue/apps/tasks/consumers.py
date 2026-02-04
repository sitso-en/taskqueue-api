"""WebSocket consumers for real-time task updates."""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class TaskStatusConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for task status updates."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.task_id = self.scope["url_route"]["kwargs"]["task_id"]
        self.room_group_name = f"task_{self.task_id}"

        # Join task-specific group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        logger.info(f"WebSocket connected for task {self.task_id}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info(f"WebSocket disconnected for task {self.task_id}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        # Currently we don't expect client messages, but could add ping/pong
        pass

    async def task_update(self, event):
        """Send task update to WebSocket client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "task_update",
                    "task_id": event["task_id"],
                    "status": event["status"],
                    "result": event.get("result"),
                    "error_message": event.get("error_message"),
                }
            )
        )


class TaskListConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time task list updates."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.room_group_name = "tasks_all"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        logger.info("WebSocket connected for task list updates")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def task_created(self, event):
        """Notify when a new task is created."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "task_created",
                    "task": event["task"],
                }
            )
        )

    async def task_update(self, event):
        """Notify when a task status changes."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "task_update",
                    "task_id": event["task_id"],
                    "status": event["status"],
                }
            )
        )
