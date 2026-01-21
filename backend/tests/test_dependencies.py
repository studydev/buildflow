"""Test authentication dependencies."""

import os
import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import AppException
from app.core.rate_limit import reset_rate_limiters
from app.dependencies import get_current_user, get_current_user_token, require_role
from app.main import app as main_app
from app.models.enums import UserRole
from app.models.user import UserPublic
from app.services.otp_store import get_otp_store

# Skip role/permission tests in dev mode (contributors are auto-assigned)
skip_in_debug_mode = pytest.mark.skipif(
    os.environ.get("DEBUG", "true").lower() == "true",
    reason="Dev mode auto-assigns contributor role to new users"
)


def create_test_app() -> FastAPI:
    """Create a fresh test app for each test class."""
    app = FastAPI()

    @app.exception_handler(AppException)
    async def handle_app_exception(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.code, "message": exc.message}},
        )
    return app


client = TestClient(main_app)


def get_test_token() -> str:
    """Helper to get a valid access token."""
    otp_store = get_otp_store()
    otp_store.clear()
    reset_rate_limiters()

    # Request OTP
    client.post("/api/v1/auth/otp", json={"email": "deps-test@example.com"})
    entry = otp_store.get("deps-test@example.com")

    # Verify OTP
    response = client.post(
        "/api/v1/auth/verify",
        json={"email": "deps-test@example.com", "code": entry.code},
    )

    return response.json()["data"]["access_token"]


class TestGetCurrentUserToken:
    """Tests for get_current_user_token dependency."""

    def setup_method(self):
        """Clear OTP store and rate limiters before each test."""
        get_otp_store().clear()
        reset_rate_limiters()
        self.test_app = create_test_app()
        self.test_client = TestClient(self.test_app)
        self.unique_path = f"/test-{uuid.uuid4().hex[:8]}"

    def test_valid_token(self):
        """Should accept valid token."""
        token = get_test_token()

        @self.test_app.get(f"{self.unique_path}-protected")
        async def protected(payload=Depends(get_current_user_token)):
            return {"sub": payload.sub, "email": payload.email}

        response = self.test_client.get(
            f"{self.unique_path}-protected",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["email"] == "deps-test@example.com"

    def test_missing_token(self):
        """Should reject missing token with 401."""
        @self.test_app.get(f"{self.unique_path}-missing")
        async def protected_missing(payload=Depends(get_current_user_token)):
            return {"sub": payload.sub}

        response = self.test_client.get(f"{self.unique_path}-missing")

        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_invalid_token(self):
        """Should reject invalid token with 401."""
        @self.test_app.get(f"{self.unique_path}-invalid")
        async def protected_invalid(payload=Depends(get_current_user_token)):
            return {"sub": payload.sub}

        response = self.test_client.get(
            f"{self.unique_path}-invalid",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401
        assert response.json()["success"] is False


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    def setup_method(self):
        """Clear OTP store and rate limiters before each test."""
        get_otp_store().clear()
        reset_rate_limiters()
        self.test_app = create_test_app()
        self.test_client = TestClient(self.test_app)
        self.unique_path = f"/test-{uuid.uuid4().hex[:8]}"

    @skip_in_debug_mode
    def test_returns_user_public(self):
        """Should return UserPublic model."""
        token = get_test_token()

        @self.test_app.get(f"{self.unique_path}-user")
        async def get_user(user: UserPublic = Depends(get_current_user)):
            return {"id": user.id, "email": user.email, "role": user.role.value}

        response = self.test_client.get(
            f"{self.unique_path}-user",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "deps-test@example.com"
        assert data["role"] == "user"


class TestRequireRole:
    """Tests for require_role dependency."""

    def setup_method(self):
        """Clear OTP store and rate limiters before each test."""
        get_otp_store().clear()
        reset_rate_limiters()
        self.test_app = create_test_app()
        self.test_client = TestClient(self.test_app)
        self.unique_path = f"/test-{uuid.uuid4().hex[:8]}"

    def test_user_can_access_user_endpoint(self):
        """User role should access user-level endpoints."""
        token = get_test_token()

        @self.test_app.get(f"{self.unique_path}-user-only")
        async def user_only(user: UserPublic = Depends(require_role(UserRole.USER))):
            return {"ok": True}

        response = self.test_client.get(
            f"{self.unique_path}-user-only",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    @skip_in_debug_mode
    def test_user_cannot_access_contributor_endpoint(self):
        """User role should not access contributor-level endpoints."""
        token = get_test_token()  # Gets a 'user' role token

        @self.test_app.get(f"{self.unique_path}-contributor-only")
        async def contributor_only(
            user: UserPublic = Depends(require_role(UserRole.CONTRIBUTOR))
        ):
            return {"ok": True}

        response = self.test_client.get(
            f"{self.unique_path}-contributor-only",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
        assert response.json()["success"] is False
