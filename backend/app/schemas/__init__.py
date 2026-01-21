"""Base response schemas following Constitution v1.0.0."""

from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field


T = TypeVar("T")


class Meta(BaseModel):
    """Response metadata - required in all API responses."""

    timestamp: str = Field(description="ISO8601 timestamp")
    correlationId: str = Field(description="Request correlation ID for tracing")
    message: Optional[str] = Field(default=None, description="Optional status message")

    @classmethod
    def create(cls, correlation_id: Optional[str] = None, message: Optional[str] = None) -> "Meta":
        """Factory method to create Meta with current timestamp."""
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlationId=correlation_id or str(uuid4()),
            message=message,
        )


class ErrorDetail(BaseModel):
    """Individual error detail for validation errors."""

    field: Optional[str] = Field(default=None, description="Field that caused the error")
    issue: str = Field(description="Description of the issue")


class ErrorBody(BaseModel):
    """Error information structure."""

    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    details: List[ErrorDetail] = Field(
        default_factory=list, description="Additional error details"
    )


class APIResponse(BaseModel, Generic[T]):
    """
    Standard success response envelope.
    
    Constitution v1.0.0 requires all responses use this envelope:
    {
        "success": true,
        "data": { ... },
        "meta": { "timestamp": "ISO8601", "correlationId": "uuid" }
    }
    """

    success: bool = Field(default=True, description="Whether the request succeeded")
    data: Optional[T] = Field(default=None, description="Response payload")
    meta: Meta = Field(default_factory=Meta.create, description="Response metadata")


class APIErrorResponse(BaseModel):
    """
    Standard error response envelope.
    
    Constitution v1.0.0 requires errors use this structure:
    {
        "success": false,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Human-readable message",
            "details": [...]
        },
        "meta": { "timestamp": "ISO8601", "correlationId": "uuid" }
    }
    """

    success: bool = Field(default=False, description="Always false for errors")
    error: ErrorBody = Field(description="Error information")
    meta: Meta = Field(description="Response metadata")


# Common response data models
class HealthData(BaseModel):
    """Health check response data."""

    status: str = Field(description="Health status")


class MessageData(BaseModel):
    """Simple message response data."""

    message: str = Field(description="Response message")
