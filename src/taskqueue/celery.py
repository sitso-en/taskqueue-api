"""
Celery configuration for taskqueue project.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taskqueue.settings")

app = Celery("taskqueue")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f"Request: {self.request!r}")
