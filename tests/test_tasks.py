"""Tests for Task API."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from taskqueue.apps.tasks.models import Task, TaskStatus


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def sample_task():
    return Task.objects.create(
        name="Test Task",
        task_type="echo",
        payload={"message": "Hello"},
        status=TaskStatus.PENDING,
    )


@pytest.mark.django_db
class TestTaskAPI:
    """Test cases for Task API endpoints."""

    def test_list_tasks(self, api_client):
        """Test listing tasks."""
        Task.objects.create(name="Task 1", task_type="echo")
        Task.objects.create(name="Task 2", task_type="compute")

        url = reverse("task-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_create_task(self, api_client):
        """Test creating a task."""
        url = reverse("task-list")
        data = {
            "name": "New Task",
            "task_type": "echo",
            "payload": {"test": "data"},
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Task"
        assert response.data["status"] == TaskStatus.QUEUED

    def test_create_task_invalid_type(self, api_client):
        """Test creating task with invalid type fails."""
        url = reverse("task-list")
        data = {
            "name": "Invalid Task",
            "task_type": "invalid_type",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_task_detail(self, api_client, sample_task):
        """Test getting task details."""
        url = reverse("task-detail", kwargs={"pk": sample_task.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Test Task"

    def test_cancel_task(self, api_client, sample_task):
        """Test cancelling a task."""
        sample_task.status = TaskStatus.QUEUED
        sample_task.save()

        url = reverse("task-cancel", kwargs={"pk": sample_task.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == TaskStatus.REVOKED

    def test_cancel_completed_task_fails(self, api_client, sample_task):
        """Test that cancelling a completed task fails."""
        sample_task.status = TaskStatus.SUCCESS
        sample_task.save()

        url = reverse("task-cancel", kwargs={"pk": sample_task.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_stats(self, api_client):
        """Test getting task statistics."""
        Task.objects.create(name="T1", task_type="echo", status=TaskStatus.SUCCESS)
        Task.objects.create(name="T2", task_type="echo", status=TaskStatus.FAILURE)
        Task.objects.create(name="T3", task_type="echo", status=TaskStatus.PENDING)

        url = reverse("task-stats")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["total"] == 3
        assert response.data["success"] == 1
        assert response.data["failure"] == 1
        assert response.data["pending"] == 1

    def test_filter_by_status(self, api_client):
        """Test filtering tasks by status."""
        Task.objects.create(name="T1", task_type="echo", status=TaskStatus.SUCCESS)
        Task.objects.create(name="T2", task_type="echo", status=TaskStatus.FAILURE)

        url = reverse("task-list")
        response = api_client.get(url, {"status": TaskStatus.SUCCESS})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["status"] == TaskStatus.SUCCESS


@pytest.mark.django_db
class TestTaskModel:
    """Test cases for Task model."""

    def test_task_creation(self):
        """Test task is created with correct defaults."""
        task = Task.objects.create(name="Test", task_type="echo")

        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0
        assert task.max_retries == 3

    def test_mark_started(self):
        """Test marking task as started."""
        task = Task.objects.create(name="Test", task_type="echo")
        task.mark_started()

        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None

    def test_mark_success(self):
        """Test marking task as successful."""
        task = Task.objects.create(name="Test", task_type="echo")
        task.mark_started()
        task.mark_success({"result": "done"})

        assert task.status == TaskStatus.SUCCESS
        assert task.completed_at is not None
        assert task.result == {"result": "done"}

    def test_duration_calculation(self):
        """Test duration property."""
        task = Task.objects.create(name="Test", task_type="echo")
        task.mark_started()
        task.mark_success()

        assert task.duration is not None
        assert task.duration >= 0
