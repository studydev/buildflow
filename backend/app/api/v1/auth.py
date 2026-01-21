"""Auth API endpoints."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.exceptions import AuthenticationError, RateLimitError
from app.core.rate_limit import (
    check_rate_limit,
    get_otp_request_limiter,
    get_otp_verify_limiter,
)
from app.schemas import APIResponse, Meta

settings = get_settings()
from app.schemas.auth import (
    OTPRequest,
    OTPResponse,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
    VerifyRequest,
)
from app.services.auth_service import get_auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/otp",
    response_model=APIResponse,
    summary="Request OTP",
    description="Request a one-time password to be sent to the provided email address.",
    responses={
        200: {"description": "OTP sent successfully"},
        429: {"description": "Rate limited - too many requests"},
    },
)
async def request_otp(request: Request, body: OTPRequest) -> JSONResponse:
    """
    Request OTP for email authentication.

    Sends a 6-digit OTP to the provided email address.
    OTP is valid for 5 minutes.
    Rate limited to 3 requests per email per 15 minutes.
    """
    correlation_id = request.state.correlation_id
    email = body.email.lower()

    # Check rate limit before processing
    check_rate_limit(
        get_otp_request_limiter(),
        email,
        "Too many OTP requests. Please wait before requesting a new one.",
    )

    auth_service = get_auth_service()

    is_new, masked_email, expires_in, otp_code = auth_service.request_otp(email)

    if not is_new:
        # Rate limited - return 429
        raise RateLimitError(
            message="OTP already sent. Please wait before requesting a new one.",
        )

    # Include OTP code in response for development/debug mode only
    response_data = OTPResponse(
        message="OTP sent successfully",
        email=masked_email,
        expires_in_seconds=expires_in,
        dev_code=otp_code if settings.debug else None,
    )

    response = APIResponse(
        success=True,
        data=response_data,
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump())


@router.post(
    "/verify",
    response_model=APIResponse,
    summary="Verify OTP",
    description="Verify the OTP code and receive JWT tokens.",
    responses={
        200: {"description": "Authentication successful"},
        401: {"description": "Invalid or expired OTP"},
    },
)
async def verify_otp(request: Request, body: VerifyRequest) -> JSONResponse:
    """
    Verify OTP and get JWT tokens.

    Returns access and refresh tokens on successful verification.
    Rate limited to 5 verify attempts per email per 15 minutes.
    """
    correlation_id = request.state.correlation_id
    email = body.email.lower()

    # Check rate limit before processing
    check_rate_limit(
        get_otp_verify_limiter(),
        email,
        "Too many verification attempts. Please wait before trying again.",
    )

    auth_service = get_auth_service()

    success, message, tokens = await auth_service.verify_otp(email, body.code)

    if not success:
        raise AuthenticationError(message=message)

    response = APIResponse(
        success=True,
        data=TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
        ),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump())


@router.post(
    "/refresh",
    response_model=APIResponse,
    summary="Refresh Token",
    description="Exchange a refresh token for a new access token.",
    responses={
        200: {"description": "Tokens refreshed successfully"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(request: Request, body: RefreshRequest) -> JSONResponse:
    """
    Refresh access token.

    Exchange a valid refresh token for new access and refresh tokens.
    The old refresh token is invalidated (rotation).
    """
    correlation_id = request.state.correlation_id
    auth_service = get_auth_service()

    success, message, tokens = auth_service.refresh_tokens(body.refresh_token)

    if not success:
        raise AuthenticationError(message=message)

    response = APIResponse(
        success=True,
        data=RefreshResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
        ),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump())
