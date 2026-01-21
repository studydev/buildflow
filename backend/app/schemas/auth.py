"""Auth-related request/response schemas."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class OTPRequest(BaseModel):
    """Request body for POST /auth/otp."""

    email: EmailStr = Field(
        ...,
        description="Email address to send OTP to",
        examples=["user@example.com"],
    )


class OTPResponse(BaseModel):
    """Response data for POST /auth/otp."""

    message: str = Field(
        default="OTP sent successfully",
        description="Status message",
    )
    email: str = Field(
        ...,
        description="Email address OTP was sent to (masked)",
    )
    expires_in_seconds: int = Field(
        default=300,
        description="OTP expiration time in seconds",
    )
    dev_code: Optional[str] = Field(
        default=None,
        description="OTP code for development only - NOT included in production",
    )


class VerifyRequest(BaseModel):
    """Request body for POST /auth/verify."""

    email: EmailStr = Field(
        ...,
        description="Email address used to request OTP",
        examples=["user@example.com"],
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code",
        examples=["123456"],
    )


class TokenResponse(BaseModel):
    """Response data for successful authentication."""

    access_token: str = Field(
        ...,
        description="JWT access token",
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token for obtaining new access tokens",
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type (always Bearer)",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
    )


class RefreshRequest(BaseModel):
    """Request body for POST /auth/refresh."""

    refresh_token: str = Field(
        ...,
        description="Refresh token to exchange for new access token",
    )


class RefreshResponse(BaseModel):
    """Response data for token refresh."""

    access_token: str = Field(
        ...,
        description="New JWT access token",
    )
    refresh_token: str = Field(
        ...,
        description="New JWT refresh token (rotated)",
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
    )
