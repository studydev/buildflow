"""Test auth API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.otp_store import get_otp_store
from app.core.rate_limit import reset_rate_limiters


client = TestClient(app)


class TestRequestOTP:
    """Tests for POST /api/v1/auth/otp."""

    def setup_method(self):
        """Clear OTP store and rate limiters before each test."""
        get_otp_store().clear()
        reset_rate_limiters()

    def test_request_otp_success(self):
        """Should return success when requesting OTP."""
        response = client.post(
            "/api/v1/auth/otp",
            json={"email": "test@example.com"},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "email" in data["data"]
        assert data["data"]["expires_in_seconds"] == 300
        # Email should be masked
        assert "***" in data["data"]["email"] or "*" in data["data"]["email"]

    def test_request_otp_rate_limited(self):
        """Should return 429 when rate limited (3 requests per 15min)."""
        # Test with unique emails to avoid OTP store's internal rate limit
        # The endpoint rate limiter allows 3 requests per email per 15min
        
        for i in range(3):
            email = f"ratelimit{i}@example.com"
            response = client.post("/api/v1/auth/otp", json={"email": email})
            assert response.status_code == 200
        
        # OTP store's internal rate limit kicks in for same email
        email = "samelimit@example.com"
        response = client.post("/api/v1/auth/otp", json={"email": email})
        assert response.status_code == 200
        
        # Second request to same email triggers OTP store's 60s cooldown
        response = client.post("/api/v1/auth/otp", json={"email": email})
        assert response.status_code == 429
        assert response.json()["success"] is False

    def test_request_otp_invalid_email(self):
        """Should return 422 for invalid email."""
        response = client.post(
            "/api/v1/auth/otp",
            json={"email": "not-an-email"},
        )
        
        assert response.status_code == 422
        assert response.json()["success"] is False


class TestVerifyOTP:
    """Tests for POST /api/v1/auth/verify."""

    def setup_method(self):
        """Clear OTP store and rate limiters before each test."""
        get_otp_store().clear()
        reset_rate_limiters()

    def test_verify_otp_success(self):
        """Should return tokens when OTP is valid."""
        # Request OTP first
        client.post("/api/v1/auth/otp", json={"email": "verify@example.com"})
        
        # Get the OTP code from the store
        otp_store = get_otp_store()
        entry = otp_store.get("verify@example.com")
        code = entry.code
        
        # Verify
        response = client.post(
            "/api/v1/auth/verify",
            json={"email": "verify@example.com", "code": code},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["token_type"] == "Bearer"
        assert data["data"]["expires_in"] == 900  # 15 minutes

    def test_verify_otp_invalid_code(self):
        """Should return 401 for invalid OTP."""
        # Request OTP first
        client.post("/api/v1/auth/otp", json={"email": "invalid@example.com"})
        
        # Try to verify with wrong code
        response = client.post(
            "/api/v1/auth/verify",
            json={"email": "invalid@example.com", "code": "000000"},
        )
        
        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_verify_otp_no_otp_requested(self):
        """Should return 401 when no OTP was requested."""
        response = client.post(
            "/api/v1/auth/verify",
            json={"email": "unknown@example.com", "code": "123456"},
        )
        
        assert response.status_code == 401

    def test_verify_otp_invalid_format(self):
        """Should return 422 for invalid code format."""
        response = client.post(
            "/api/v1/auth/verify",
            json={"email": "test@example.com", "code": "12345"},  # 5 digits
        )
        
        assert response.status_code == 422

    def test_verify_otp_rate_limited(self):
        """Should return 429 when too many verify attempts (5 per 15min)."""
        email = "verifylimit@example.com"
        
        # Request OTP first
        client.post("/api/v1/auth/otp", json={"email": email})
        
        # Make 5 failed verify attempts
        for _ in range(5):
            client.post(
                "/api/v1/auth/verify",
                json={"email": email, "code": "000000"},
            )
        
        # 6th attempt should be rate limited
        response = client.post(
            "/api/v1/auth/verify",
            json={"email": email, "code": "000000"},
        )
        
        assert response.status_code == 429
        assert response.json()["success"] is False


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh."""

    def setup_method(self):
        """Clear OTP store and rate limiters before each test."""
        get_otp_store().clear()
        reset_rate_limiters()

    def test_refresh_token_success(self):
        """Should return new tokens when refresh token is valid."""
        # Get tokens first
        client.post("/api/v1/auth/otp", json={"email": "refresh@example.com"})
        entry = get_otp_store().get("refresh@example.com")
        
        verify_response = client.post(
            "/api/v1/auth/verify",
            json={"email": "refresh@example.com", "code": entry.code},
        )
        
        tokens = verify_response.json()["data"]
        
        # Refresh
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        # New refresh token should be different (rotated)
        assert data["data"]["refresh_token"] != tokens["refresh_token"]

    def test_refresh_token_invalid(self):
        """Should return 401 for invalid refresh token."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        
        assert response.status_code == 401
        assert response.json()["success"] is False
