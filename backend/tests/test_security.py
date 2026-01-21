"""Test JWT security utilities."""

from datetime import timedelta

import jwt
import pytest

from app.core import security


class TestKeyLoading:
    """Tests for RSA key loading."""

    def test_get_private_key_loads_from_file(self):
        """Should load private key from file."""
        security.clear_key_cache()
        key = security.get_private_key()

        assert key is not None
        assert "-----BEGIN PRIVATE KEY-----" in key

    def test_get_public_key_loads_from_file(self):
        """Should load public key from file."""
        security.clear_key_cache()
        key = security.get_public_key()

        assert key is not None
        assert "-----BEGIN PUBLIC KEY-----" in key

    def test_keys_are_cached(self):
        """Keys should be cached after first load."""
        security.clear_key_cache()

        key1 = security.get_private_key()
        key2 = security.get_private_key()

        # Should be the same object (cached)
        assert key1 is key2


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token(self):
        """Should create a valid access token."""
        token = security.create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="user",
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        """Should create a valid refresh token."""
        token = security.create_refresh_token(
            user_id="user-123",
            email="test@example.com",
            role="contributor",
        )

        assert token is not None
        assert isinstance(token, str)

    def test_create_token_pair(self):
        """Should create both access and refresh tokens."""
        pair = security.create_token_pair(
            user_id="user-123",
            email="test@example.com",
            role="user",
        )

        assert pair.access_token is not None
        assert pair.refresh_token is not None
        assert pair.token_type == "Bearer"
        assert pair.expires_in == 15 * 60  # 15 minutes in seconds


class TestTokenDecoding:
    """Tests for JWT token verification."""

    def test_decode_access_token(self):
        """Should decode and verify access token."""
        token = security.create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="contributor",
        )

        payload = security.verify_access_token(token)

        assert payload.sub == "user-123"
        assert payload.email == "test@example.com"
        assert payload.role == "contributor"
        assert payload.type == "access"

    def test_decode_refresh_token(self):
        """Should decode and verify refresh token."""
        token = security.create_refresh_token(
            user_id="user-456",
            email="admin@example.com",
            role="user",
            jti="refresh-token-id-xyz",
        )

        payload = security.verify_refresh_token(token)

        assert payload.sub == "user-456"
        assert payload.email == "admin@example.com"
        assert payload.role == "user"
        assert payload.type == "refresh"
        assert payload.jti == "refresh-token-id-xyz"

    def test_verify_access_token_rejects_refresh_token(self):
        """verify_access_token should reject refresh tokens."""
        refresh_token = security.create_refresh_token(
            user_id="user-123",
            email="test@example.com",
            role="user",
        )

        with pytest.raises(jwt.InvalidTokenError) as exc_info:
            security.verify_access_token(refresh_token)

        assert "not an access token" in str(exc_info.value)

    def test_verify_refresh_token_rejects_access_token(self):
        """verify_refresh_token should reject access tokens."""
        access_token = security.create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="user",
        )

        with pytest.raises(jwt.InvalidTokenError) as exc_info:
            security.verify_refresh_token(access_token)

        assert "not a refresh token" in str(exc_info.value)

    def test_expired_token_raises_error(self):
        """Should raise error for expired tokens."""
        # Create token that expires immediately
        token = security.create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="user",
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            security.decode_token(token)

    def test_invalid_token_raises_error(self):
        """Should raise error for invalid tokens."""
        with pytest.raises(jwt.InvalidTokenError):
            security.decode_token("invalid.token.here")

    def test_tampered_token_raises_error(self):
        """Should raise error for tampered tokens."""
        token = security.create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="user",
        )

        # Tamper with the token
        tampered = token[:-5] + "XXXXX"

        with pytest.raises(jwt.InvalidTokenError):
            security.decode_token(tampered)


class TestTokenPayload:
    """Tests for TokenPayload model."""

    def test_payload_contains_required_fields(self):
        """Token payload should contain all required fields."""
        token = security.create_access_token(
            user_id="user-123",
            email="test@example.com",
            role="user",
        )

        payload = security.decode_token(token)

        assert hasattr(payload, "sub")
        assert hasattr(payload, "email")
        assert hasattr(payload, "role")
        assert hasattr(payload, "type")
        assert hasattr(payload, "exp")
        assert hasattr(payload, "iat")
