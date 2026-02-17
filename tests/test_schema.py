"""Smoke tests for OpenAPI schema."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_openapi_schema_endpoint():
    client = APIClient()
    url = reverse("schema")
    resp = client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["openapi"]
