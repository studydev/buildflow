"""Security utilities - JWT token handling with RS256 or HS256."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

# Token types
ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"


class TokenPayload(BaseModel):
    """JWT token payload structure."""

    sub: str  # Subject (user ID)
    email: str
    role: str  # "user" or "contributor"
    type: str  # "access" or "refresh"
    exp: datetime
    iat: datetime
    jti: Optional[str] = None  # JWT ID for refresh token tracking


class TokenPair(BaseModel):
    """Access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # Seconds until access token expires


# =============================================================================
# Key/Secret Loading
# =============================================================================

_private_key: Optional[str] = None
_public_key: Optional[str] = None
_jwt_secret: Optional[str] = None


def _load_key(path: str) -> str:
    """Load a PEM key from file."""
    key_path = Path(path)
    if not key_path.exists():
        raise FileNotFoundError(f"Key file not found: {path}")
    return key_path.read_text()


def get_jwt_algorithm() -> str:
    """Get the JWT algorithm from settings."""
    settings = get_settings()
    return settings.jwt_algorithm


def get_signing_key() -> str:
    """Get the key/secret for signing tokens based on algorithm."""
    global _private_key, _jwt_secret
    settings = get_settings()

    if settings.jwt_algorithm == "HS256":
        if _jwt_secret is None:
            if not settings.jwt_secret:
                raise RuntimeError(
                    "JWT_SECRET is not set. "
                    "Set JWT_SECRET environment variable for HS256 algorithm."
                )
            _jwt_secret = settings.jwt_secret
        return _jwt_secret
    else:
        # RS256
        if _private_key is None:
            if not settings.jwt_private_key_path:
                raise RuntimeError(
                    "JWT_PRIVATE_KEY_PATH is not set. "
                    "Run 'make keys' to generate RSA keys."
                )
            _private_key = _load_key(settings.jwt_private_key_path)
        return _private_key


def get_verification_key() -> str:
    """Get the key/secret for verifying tokens based on algorithm."""
    global _public_key, _jwt_secret
    settings = get_settings()

    if settings.jwt_algorithm == "HS256":
        if _jwt_secret is None:
            if not settings.jwt_secret:
                raise RuntimeError(
                    "JWT_SECRET is not set. "
                    "Set JWT_SECRET environment variable for HS256 algorithm."
                )
            _jwt_secret = settings.jwt_secret
        return _jwt_secret
    else:
        # RS256
        if _public_key is None:
            if not settings.jwt_public_key_path:
                raise RuntimeError(
                    "JWT_PUBLIC_KEY_PATH is not set. "
                    "Run 'make keys' to generate RSA keys."
                )
            _public_key = _load_key(settings.jwt_public_key_path)
        return _public_key


# Legacy functions for backward compatibility
def get_private_key() -> str:
    """Get the private key for signing tokens (RS256 only)."""
    return get_signing_key()


def get_public_key() -> str:
    """Get the public key for verifying tokens (RS256 only)."""
    return get_verification_key()


# =============================================================================
# Token Creation
# =============================================================================


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: The user's unique ID
        email: The user's email
        role: The user's role ("user" or "contributor")
        expires_delta: Custom expiration time (default: 15 minutes)

    Returns:
        Encoded JWT token string
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": ACCESS_TOKEN,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, get_signing_key(), algorithm=get_jwt_algorithm())


def create_refresh_token(
    user_id: str,
    email: str,
    role: str,
    jti: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: The user's unique ID
        email: The user's email
        role: The user's role
        jti: JWT ID for token tracking (optional)
        expires_delta: Custom expiration time (default: 7 days)

    Returns:
        Encoded JWT token string
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": REFRESH_TOKEN,
        "iat": now,
        "exp": expire,
    }

    if jti:
        payload["jti"] = jti

    return jwt.encode(payload, get_signing_key(), algorithm=get_jwt_algorithm())


def create_token_pair(
    user_id: str,
    email: str,
    role: str,
    refresh_jti: Optional[str] = None,
) -> TokenPair:
    """
    Create a pair of access and refresh tokens.

    Args:
        user_id: The user's unique ID
        email: The user's email
        role: The user's role
        refresh_jti: JWT ID for refresh token tracking

    Returns:
        TokenPair with access and refresh tokens
    """
    settings = get_settings()

    access_token = create_access_token(user_id, email, role)
    refresh_token = create_refresh_token(user_id, email, role, jti=refresh_jti)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


# =============================================================================
# Token Verification
# =============================================================================


def decode_token(token: str) -> TokenPayload:
    """
    Decode and verify a JWT token.

    Args:
        token: The JWT token string

    Returns:
        TokenPayload with the decoded claims

    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
    """
    payload = jwt.decode(
        token,
        get_verification_key(),
        algorithms=[get_jwt_algorithm()],
    )

    return TokenPayload(
        sub=payload["sub"],
        email=payload["email"],
        role=payload["role"],
        type=payload["type"],
        exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        jti=payload.get("jti"),
    )


def verify_access_token(token: str) -> TokenPayload:
    """
    Verify an access token.

    Args:
        token: The access token string

    Returns:
        TokenPayload if valid

    Raises:
        jwt.InvalidTokenError: If token is invalid or not an access token
    """
    payload = decode_token(token)

    if payload.type != ACCESS_TOKEN:
        raise jwt.InvalidTokenError("Token is not an access token")

    return payload


def verify_refresh_token(token: str) -> TokenPayload:
    """
    Verify a refresh token.

    Args:
        token: The refresh token string

    Returns:
        TokenPayload if valid

    Raises:
        jwt.InvalidTokenError: If token is invalid or not a refresh token
    """
    payload = decode_token(token)

    if payload.type != REFRESH_TOKEN:
        raise jwt.InvalidTokenError("Token is not a refresh token")

    return payload


# =============================================================================
# Utilities
# =============================================================================


def clear_key_cache() -> None:
    """Clear cached keys (for testing or key rotation)."""
    global _private_key, _public_key
    _private_key = None
    _public_key = None


# =============================================================================
# Cookie Helpers for HttpOnly JWT
# =============================================================================

# Cookie configuration
AUTH_COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds (604800)


def set_auth_cookie(
    response,
    token: str,
    max_age: int = COOKIE_MAX_AGE,
    secure: bool = True,
    httponly: bool = True,
    samesite: str = "none",
) -> None:
    """
    Set authentication cookie on response.

    Args:
        response: FastAPI Response object
        token: JWT access token
        max_age: Cookie lifetime in seconds (default: 7 days)
        secure: Use HTTPS only (default: True)
        httponly: Prevent JavaScript access (default: True)
        samesite: SameSite policy (default: "none" for cross-origin support)
    """
    settings = get_settings()

    # SameSite=None requires Secure=True (HTTPS)
    # In development with HTTP, use Lax instead
    if settings.debug:
        secure = False
        samesite = "lax"  # Fallback for HTTP in development

    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=httponly,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def clear_auth_cookie(response) -> None:
    """
    Clear authentication cookie from response.

    Args:
        response: FastAPI Response object
    """
    settings = get_settings()

    # Match the same settings used when setting the cookie
    if settings.debug:
        secure = False
        samesite = "lax"
    else:
        secure = True
        samesite = "none"

    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite=samesite,
    )
