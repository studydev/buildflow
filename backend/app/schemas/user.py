"""User-related request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class UserResponse(BaseModel):
    """Response data for user profile."""

    id: str = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    display_name: Optional[str] = Field(None, description="Display name")
    role: UserRole = Field(..., description="User role")
    created_at: datetime = Field(..., description="Account creation date")


class UserUpdateRequest(BaseModel):
    """Request body for updating user profile."""

    display_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Display name",
    )
