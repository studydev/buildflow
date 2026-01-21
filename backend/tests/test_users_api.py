"""Test users API endpoints."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.otp_store import get_otp_store

client = TestClient(app)


def get_test_token() -> str:
    """Helper to get a valid access token."""
    otp_store = get_otp_store()
    otp_store.clear()

    client.post("/api/v1/auth/otp", json={"email": "users-api@example.com"})
    entry = otp_store.get("users-api@example.com")

    response = client.post(
        "/api/v1/auth/verify",
        json={"email": "users-api@example.com", "code": entry.code},
    )

    return response.json()["data"]["access_token"]


class TestGetMe:
    """Tests for GET /api/v1/users/me."""

    def setup_method(self):
        """Clear OTP store before each test."""
        get_otp_store().clear()

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
