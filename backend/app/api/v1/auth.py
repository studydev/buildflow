"""Auth API endpoints."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.domain_validator import validate_internal_email
from app.core.exceptions import (
    AuthenticationError,
    DomainNotAllowedError,
    EmailSendError,
    RateLimitError,
)
from app.core.rate_limit import (
    check_rate_limit,
    get_otp_request_limiter,
    get_otp_verify_limiter,
)
from app.core.security import set_auth_cookie
from app.schemas import APIResponse, Meta
from app.services.email_service import send_otp_email

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
    OTP is valid for 3 minutes.
    Only internal employee emails (@microsoft.com, @github.com) are allowed.
    Rate limited to 1 request per email per 3 minutes.

    For dev bypass accounts (in non-production environments),
    returns success without sending an email.
    """
    correlation_id = request.state.correlation_id
    email = body.email.lower()

    # T016: Validate domain first (FR-001)
    is_valid, error_message = validate_internal_email(email)
    if not is_valid:
        raise DomainNotAllowedError(message=error_message)

    auth_service = get_auth_service()

    # Check if this is a dev bypass account
    is_bypass = auth_service.is_dev_bypass_email(email)

    if is_bypass:
        # For dev bypass account, skip rate limiting and email sending
        logger.info("Dev bypass OTP request for: %s", email)

        response_data = OTPResponse(
            message="Dev bypass account - enter any code to login",
            email=auth_service._mask_email(email),
            expires_in_seconds=180,
        )

        response = APIResponse(
            success=True,
            data=response_data,
            meta=Meta.create(correlation_id),
        )

        return JSONResponse(content=response.model_dump())

    # Check rate limit before processing (only for non-bypass accounts)
    check_rate_limit(
        get_otp_request_limiter(),
        email,
        "Too many OTP requests. Please wait before requesting a new one.",
    )

    is_new, masked_email, expires_in, otp_code = auth_service.request_otp(email)

    if not is_new:
        # Rate limited - return 429
        raise RateLimitError(
            message="OTP already sent. Please wait before requesting a new one.",
        )

    # T014: Send OTP email via Azure Communication Services
    try:
        email_sent = await send_otp_email(email, otp_code)
        if not email_sent:
            logger.error("Failed to send OTP email to %s", masked_email)
            raise EmailSendError()
    except EmailSendError:
        raise  # Re-raise our custom error
    except Exception as e:
        logger.error("Email service error: %s", e)
        raise EmailSendError()

    # T018: Remove dev_code from response (FR-020)
    response_data = OTPResponse(
        message="OTP sent successfully",
        email=masked_email,
        expires_in_seconds=expires_in,
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
    T017: Sets HttpOnly cookie with access token for browser authentication.
    Rate limited to 5 verify attempts per email per 15 minutes.

    For dev bypass accounts (in non-production environments),
    any OTP code will be accepted.
    """
    correlation_id = request.state.correlation_id
    email = body.email.lower()

    auth_service = get_auth_service()

    # Check if this is a dev bypass account (skip rate limiting)
    is_bypass = auth_service.is_dev_bypass_email(email)

    if not is_bypass:
        # Check rate limit before processing (only for non-bypass accounts)
        check_rate_limit(
            get_otp_verify_limiter(),
            email,
            "Too many verification attempts. Please wait before trying again.",
        )

    success, message, tokens = await auth_service.verify_otp(email, body.code)

    if not success:
        raise AuthenticationError(message=message)

    # T042: Save login history on successful authentication
    try:
        from app.models.login_history import LoginHistory
        from app.repositories.login_history_repo import get_login_history_repository

        # T043: Extract user_agent and ip_address from request
        user_agent = request.headers.get("user-agent", "unknown")
        ip_address = request.client.host if request.client else "unknown"

        history = LoginHistory.create(
            email=email,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        history_repo = get_login_history_repository()
        await history_repo.create(history)
        logger.info("Login history saved for: %s", email)
    except Exception as e:
        # Don't fail login if history save fails - just log the error
        logger.warning("Failed to save login history: %s", e)

    # Build response with token data
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

    # T017: Create response and set HttpOnly cookie (FR-008)
    json_response = JSONResponse(content=response.model_dump())
    set_auth_cookie(json_response, tokens.access_token)

    return json_response


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


@router.get(
    "/me",
    response_model=APIResponse,
    summary="Get Current User",
    description="Get the currently authenticated user's information.",
    responses={
        200: {"description": "User information retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def get_current_user_info(request: Request) -> JSONResponse:
    """
    T025: Get current authenticated user info.

    Validates the session via HttpOnly cookie and returns user details.
    Used by frontend to check session validity on page load.
    """
    import jwt

    from app.core.security import AUTH_COOKIE_NAME, verify_access_token

    correlation_id = request.state.correlation_id

    # Get token from cookie
    access_token = request.cookies.get(AUTH_COOKIE_NAME)
    if not access_token:
        raise AuthenticationError(message="Missing authentication token")

    try:
        payload = verify_access_token(access_token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(message="Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError(message="Invalid authentication token")

    response = APIResponse(
        success=True,
        data={
            "id": payload.sub,
            "email": payload.email,
            "display_name": None,
            "role": payload.role,
            "created_at": payload.iat.isoformat() if hasattr(payload.iat, 'isoformat') else str(payload.iat),
        },
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump())


@router.post(
    "/logout",
    response_model=APIResponse,
    summary="Logout",
    description="Logout and clear authentication cookie.",
    responses={
        200: {"description": "Logged out successfully"},
    },
)
async def logout(request: Request) -> JSONResponse:
    """
    T038: Logout endpoint - clears the HttpOnly auth cookie.
    """
    from app.core.security import clear_auth_cookie

    correlation_id = request.state.correlation_id

    response_data = APIResponse(
        success=True,
        data={"message": "Logged out successfully"},
        meta=Meta.create(correlation_id),
    )

    response = JSONResponse(content=response_data.model_dump())
    clear_auth_cookie(response)

    return response
