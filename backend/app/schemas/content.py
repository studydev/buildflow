"""Content schemas for API requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContentResponse(BaseModel):
    """Content item response for API."""

    id: str
    title: str
    description: str
    content_type: str
    categories: list[str]
    level: str
    duration_minutes: int
    thumbnail_url: Optional[str] = None
    icon: Optional[str] = None
    source_url: str
    view_count: int
    bookmark_count: int
    published_at: Optional[datetime] = None

    # Bilingual fields (T502)
    title_kr: Optional[str] = None
    description_kr: Optional[str] = None
    summary_short: Optional[str] = None
    summary_kr: Optional[str] = None
    prerequisites: list[str] = Field(default_factory=list)
    prerequisites_kr: list[str] = Field(default_factory=list)
    learning_outcomes: list[str] = Field(default_factory=list)
    learning_outcomes_kr: list[str] = Field(default_factory=list)
    difficulty_level: Optional[str] = None


class ContentListResponse(BaseModel):
    """Paginated content list response."""

    items: list[ContentResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class ContentCreateRequest(BaseModel):
    """Request to create new content."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    source_url: str = Field(..., description="GitHub repository URL")
    content_type: str = Field(default="workshop")
    categories: list[str] = Field(default_factory=list)
    level: str = Field(default="beginner")
    duration_minutes: int = Field(default=60, ge=1, le=480)
    thumbnail_url: Optional[str] = None
    icon: Optional[str] = None


class ContentUpdateRequest(BaseModel):
    """Request to update content."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=2000)
    categories: Optional[list[str]] = None
    level: Optional[str] = None
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    thumbnail_url: Optional[str] = None
    icon: Optional[str] = None


class ContentSearchParams(BaseModel):
    """Query parameters for content search."""

    q: str = Field(..., min_length=1, max_length=100, description="Search query")
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class ContentListParams(BaseModel):
    """Query parameters for content listing."""

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    category: Optional[str] = None
    level: Optional[str] = None
