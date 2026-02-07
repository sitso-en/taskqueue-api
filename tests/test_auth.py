"""Tests for Authentication API."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestAuthAPI:
    """Test cases for Authentication API endpoints."""

    def test_register_user(self, api_client):
        """Test user registration."""
        url = reverse("register")
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepass123",
            "password_confirm": "securepass123",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]
        assert response.data["user"]["username"] == "newuser"

    def test_register_password_mismatch(self, api_client):
        """Test registration fails with mismatched passwords."""
        url = reverse("register")
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "securepass123",
            "password_confirm": "differentpass",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login(self, api_client, user):
        """Test user login returns tokens."""
        url = reverse("token_obtain_pair")
        data = {
            "username": "testuser",
            "password": "testpass123",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data
        assert response.data["user"]["username"] == "testuser"

    def test_login_invalid_credentials(self, api_client, user):
        """Test login fails with wrong password."""
        url = reverse("token_obtain_pair")
        data = {
            "username": "testuser",
            "password": "wrongpassword",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh(self, api_client, user):
        """Test token refresh endpoint."""
        # First, login to get tokens
        login_url = reverse("token_obtain_pair")
        login_response = api_client.post(
            login_url,
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )

        refresh_token = login_response.data["refresh"]

        # Now refresh the token
        refresh_url = reverse("token_refresh")
        response = api_client.post(
            refresh_url,
            {"refresh": refresh_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_token_verify(self, api_client, user):
        """Test token verify endpoint."""
        # First, login to get tokens
        login_url = reverse("token_obtain_pair")
        login_response = api_client.post(
            login_url,
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )

        access_token = login_response.data["access"]

        # Verify the token
        verify_url = reverse("token_verify")
        response = api_client.post(
            verify_url,
            {"token": access_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

    def test_get_profile(self, api_client, user):
        """Test getting user profile."""
        api_client.force_authenticate(user=user)
        url = reverse("profile")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["username"] == "testuser"
        assert response.data["email"] == "test@example.com"

    def test_update_profile(self, api_client, user):
        """Test updating user profile."""
        api_client.force_authenticate(user=user)
        url = reverse("profile")
        data = {"first_name": "Test", "last_name": "User"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "Test"
        assert response.data["last_name"] == "User"

    def test_change_password(self, api_client, user):
        """Test password change."""
        api_client.force_authenticate(user=user)
        url = reverse("change_password")
        data = {
            "old_password": "testpass123",
            "new_password": "newsecurepass456",
            "new_password_confirm": "newsecurepass456",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Verify new password works
        api_client.logout()
        login_url = reverse("token_obtain_pair")
        login_response = api_client.post(
            login_url,
            {"username": "testuser", "password": "newsecurepass456"},
            format="json",
        )
        assert login_response.status_code == status.HTTP_200_OK

    def test_change_password_wrong_old_password(self, api_client, user):
        """Test password change fails with wrong old password."""
        api_client.force_authenticate(user=user)
        url = reverse("change_password")
        data = {
            "old_password": "wrongpassword",
            "new_password": "newsecurepass456",
            "new_password_confirm": "newsecurepass456",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout(self, api_client, user):
        """Test logout blacklists refresh token."""
        # Login first
        login_url = reverse("token_obtain_pair")
        login_response = api_client.post(
            login_url,
            {"username": "testuser", "password": "testpass123"},
            format="json",
        )

        refresh_token = login_response.data["refresh"]
        api_client.force_authenticate(user=user)

        # Logout
        logout_url = reverse("logout")
        response = api_client.post(
            logout_url,
            {"refresh": refresh_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify refresh token is blacklisted
        refresh_url = reverse("token_refresh")
        refresh_response = api_client.post(
            refresh_url,
            {"refresh": refresh_token},
            format="json",
        )
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED
