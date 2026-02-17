"""Smoke tests for OpenAPI schema."""

import pytest
from django.urls import reverse
from rest_framework import status


@pytest.mark.django_db
def test_openapi_schema_endpoint(api_client):
    url = reverse("schema")
    resp = api_client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["openapi"]
