"""Custom exceptions following Constitution v1.0.0 error codes."""

from typing import List, Optional

from app.schemas import ErrorDetail


class AppException(Exception):
    """
    Base application exception.

    All custom exceptions should inherit from this class.
    Automatically converted to APIErrorResponse by exception handlers.
    """

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        details: Optional[List[ErrorDetail]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(self.message)


class ValidationError(AppException):
    """
    Validation error - 400 Bad Request.

    Use for: malformed requests, invalid input formats, constraint violations.
    """

    def __init__(self, message: str, details: Optional[List[ErrorDetail]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class AuthenticationError(AppException):
    """
    Authentication error - 401 Unauthorized.

    Use for: missing token, invalid token, expired token.
    """

    def __init__(self, message: str = "Authentication required", code: str = "AUTH_ERROR"):
        super().__init__(
            message=message,
            code=code,
            status_code=401,
        )


class ForbiddenError(AppException):
    """
    Forbidden error - 403 Forbidden.

    Use for: valid token but insufficient permissions.
    """

    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=403,
        )


class NotFoundError(AppException):
    """
    Not found error - 404 Not Found.

    Use for: resource does not exist.
    """

    def __init__(self, resource: str = "Resource"):
        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            status_code=404,
        )


class ConflictError(AppException):
    """
    Conflict error - 409 Conflict.

    Use for: duplicate resource, state conflict.
    """

    def __init__(self, message: str = "Resource already exists"):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
        )


class RateLimitError(AppException):
    """
    Rate limit error - 429 Too Many Requests.

    Use for: exceeded rate limits.
    """

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )


class DomainNotAllowedError(AppException):
    """
    Domain not allowed error - 400 Bad Request.

    Use for: email domain is not in the allowed list for internal employees.
    """

    def __init__(self, message: str = "내부 직원 전용 로그인 서비스입니다."):
        super().__init__(
            message=message,
            code="DOMAIN_NOT_ALLOWED",
            status_code=400,
        )


class EmailSendError(AppException):
    """
    Email send error - 500 Internal Server Error.

    Use for: failed to send email via Azure Communication Services.
    """

    def __init__(self, message: str = "이메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요."):
        super().__init__(
            message=message,
            code="EMAIL_SEND_FAILED",
            status_code=500,
        )


class InternalError(AppException):
    """
    Internal server error - 500 Internal Server Error.

    Use for: unexpected errors, should be logged.
    """

    def __init__(self, message: str = "Internal server error"):
        super().__init__(
            message=message,
            code="INTERNAL_ERROR",
            status_code=500,
        )


# Error codes as constants for consistency
class ErrorCodes:
    """Standard error codes from Constitution v1.0.0."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    OTP_INVALID = "OTP_INVALID"
    OTP_EXPIRED = "OTP_EXPIRED"
    OTP_MAX_ATTEMPTS = "OTP_MAX_ATTEMPTS"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    BLOCKED_DOMAIN = "BLOCKED_DOMAIN"
    INVALID_URL = "INVALID_URL"
    INTERNAL_ERROR = "INTERNAL_ERROR"
