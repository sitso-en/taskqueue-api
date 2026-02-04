"""pytest configuration."""

import os

import django
from django.conf import settings


def pytest_configure():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taskqueue.settings")
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("DEBUG", "True")
    os.environ.setdefault("DB_NAME", "taskqueue_test")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
    
    django.setup()
