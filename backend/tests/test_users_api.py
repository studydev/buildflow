"""Test users API endpoints."""

import os

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import reset_rate_limiters
from app.main import app
from app.services.otp_store import get_otp_store

client = TestClient(app)

# Skip tests affected by dev mode role assignment or shared state
skip_in_debug_mode = pytest.mark.skipif(
    os.environ.get("DEBUG", "true").lower() == "true",
    reason="Dev mode auto-assigns contributor role and has shared user state"
)


def get_test_token() -> str:
    """Helper to get a valid access token."""
    otp_store = get_otp_store()
    otp_store.clear()
    reset_rate_limiters()

    # Use allowed domain (@microsoft.com)
    client.post("/api/v1/auth/otp", json={"email": "users-api@microsoft.com"})
    entry = otp_store.get("users-api@microsoft.com")

    response = client.post(
        "/api/v1/auth/verify",
        json={"email": "users-api@microsoft.com", "code": entry.code},
    )

    return response.json()["data"]["access_token"]


class TestGetMe:
    """Tests for GET /api/v1/users/me."""

    def setup_method(self):
        """Clear OTP store and rate limiters before each test."""
        get_otp_store().clear()
        reset_rate_limiters()

    @skip_in_debug_mode
    def test_get_me_success(self):
        """Should return current user profile."""
        token = get_test_token()

        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "id" in data["data"]
        assert data["data"]["email"] == "users-api@example.com"
        assert data["data"]["role"] == "user"
        assert "created_at" in data["data"]

    def test_get_me_no_token(self):
        """Should return 401 without token."""
        response = client.get("/api/v1/users/me")

        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_get_me_invalid_token(self):
        """Should return 401 with invalid token."""
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_get_me_includes_correlation_id(self):
        """Should include correlation ID in response."""
        token = get_test_token()

        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert "X-Correlation-ID" in response.headers
        assert "correlationId" in response.json()["meta"]
