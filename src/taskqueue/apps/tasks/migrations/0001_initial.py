# Generated manually to introduce migrations for the tasks app.

import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Task",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("name", models.CharField(max_length=255, db_index=True)),
                ("task_type", models.CharField(max_length=255, db_index=True)),
                ("payload", models.JSONField(default=dict, blank=True)),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("pending", "Pending"),
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                            ("revoked", "Revoked"),
                            ("retry", "Retry"),
                        ],
                        default="pending",
                        db_index=True,
                    ),
                ),
                (
                    "priority",
                    models.IntegerField(
                        choices=[(1, "Low"), (5, "Normal"), (10, "High"), (20, "Critical")],
                        default=5,
                        db_index=True,
                    ),
                ),
                ("celery_task_id", models.CharField(max_length=255, blank=True, null=True, db_index=True)),
                ("max_retries", models.PositiveIntegerField(default=3)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                (
                    "retry_delay",
                    models.PositiveIntegerField(default=60, help_text="Delay between retries in seconds"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("started_at", models.DateTimeField(null=True, blank=True)),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                (
                    "scheduled_at",
                    models.DateTimeField(
                        null=True,
                        blank=True,
                        help_text="Schedule task for later execution",
                    ),
                ),
                ("result", models.JSONField(null=True, blank=True)),
                ("error_message", models.TextField(blank=True)),
                ("tags", models.JSONField(default=list, blank=True)),
                ("metadata", models.JSONField(default=dict, blank=True)),
                ("callback_url", models.URLField(blank=True, null=True)),
                ("callback_headers", models.JSONField(default=dict, blank=True)),
                ("callback_secret", models.CharField(max_length=255, blank=True)),
                (
                    "callback_events",
                    models.JSONField(
                        default=list,
                        blank=True,
                        help_text="Events to notify (e.g. task.succeeded, task.failed, task.revoked)",
                    ),
                ),
                ("callback_max_attempts", models.PositiveIntegerField(default=5)),
                ("callback_attempts", models.PositiveIntegerField(default=0)),
                (
                    "callback_status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("pending", "Pending"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                        ],
                        default="pending",
                        db_index=True,
                    ),
                ),
                ("callback_last_attempt_at", models.DateTimeField(null=True, blank=True)),
                ("callback_last_response_code", models.IntegerField(null=True, blank=True)),
                ("callback_last_response_body", models.TextField(blank=True)),
                ("callback_last_error", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="tasks_task_status_created_at_idx"),
                    models.Index(fields=["task_type", "status"], name="tasks_task_task_type_status_idx"),
                    models.Index(
                        fields=["priority", "status", "created_at"],
                        name="tasks_task_priority_status_created_at_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="WebhookDelivery",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("event", models.CharField(max_length=100, db_index=True)),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("pending", "Pending"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                        ],
                        default="pending",
                        db_index=True,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("request_url", models.URLField()),
                ("request_headers", models.JSONField(default=dict, blank=True)),
                ("request_body", models.TextField(blank=True)),
                ("signature", models.CharField(max_length=128, blank=True)),
                ("queued_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("last_attempt_at", models.DateTimeField(null=True, blank=True)),
                ("response_status_code", models.IntegerField(null=True, blank=True)),
                ("response_body", models.TextField(blank=True)),
                ("error_message", models.TextField(blank=True)),
                (
                    "replay_of",
                    models.ForeignKey(
                        to="tasks.webhookdelivery",
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        related_name="replays",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        to="tasks.task",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webhook_deliveries",
                    ),
                ),
            ],
            options={
                "ordering": ["-queued_at"],
                "indexes": [
                    models.Index(
                        fields=["task", "event", "queued_at"],
                        name="tasks_webhookdelivery_task_event_queued_at_idx",
                    ),
                    models.Index(
                        fields=["status", "queued_at"],
                        name="tasks_webhookdelivery_status_queued_at_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DeadLetterQueue",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("task_name", models.CharField(max_length=255)),
                ("task_type", models.CharField(max_length=255)),
                ("payload", models.JSONField(default=dict)),
                ("error_message", models.TextField()),
                ("traceback", models.TextField(blank=True)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reprocessed", models.BooleanField(default=False)),
                ("reprocessed_at", models.DateTimeField(null=True, blank=True)),
                (
                    "original_task",
                    models.ForeignKey(
                        to="tasks.task",
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        related_name="dead_letters",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "verbose_name_plural": "Dead letter queue",
            },
        ),
    ]
