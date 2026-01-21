"""Base response schemas - re-export from __init__.py for convenience."""

from app.schemas import (
    APIErrorResponse,
    APIResponse,
    ErrorBody,
    ErrorDetail,
    HealthData,
    MessageData,
    Meta,
)

__all__ = [
    "APIResponse",
    "APIErrorResponse",
    "ErrorBody",
    "ErrorDetail",
    "HealthData",
    "MessageData",
    "Meta",
]
