"""pytest configuration."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "taskqueue.settings")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")

# Default to sqlite for local test runs (CI sets DB_* for Postgres).
if not os.environ.get("DB_ENGINE") and not os.environ.get("DB_NAME"):
    os.environ.setdefault("DB_ENGINE", "sqlite")


def pytest_configure():
    django.setup()
