"""Schemas for Analysis Requests API."""

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisRequestCreate(BaseModel):
    """Request body for creating an analysis request."""

    source_url: str = Field(
        ...,
        description="GitHub repository URL or redirect URL (e.g., aka.ms) to analyze",
        examples=[
            "https://github.com/Azure-Samples/azure-functions-python",
            "https://aka.ms/ignite25-LAB510GHRepo",
        ],
    )

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that the URL is a valid HTTP/HTTPS URL."""
        # Normalize the URL
        v = v.strip().rstrip("/")

        # Allow any valid HTTP/HTTPS URL (redirect validation done in service layer)
        url_pattern = r"^https?://[\w\-\.]+(:\d+)?(/[\w\-\.~!$&'()*+,;=:@%]*)*/?(\?[\w\-\.~!$&'()*+,;=:@%/?]*)?(#[\w\-\.~!$&'()*+,;=:@%/?]*)?$"

        if not re.match(url_pattern, v, re.IGNORECASE):
            raise ValueError(
                "Invalid URL. Must be a valid HTTP or HTTPS URL"
            )

        return v


class StatusHistoryResponse(BaseModel):
    """Status history entry response."""

    status: str
    timestamp: datetime
    message: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    """Analysis result response."""

    # 기본 정보
    title: str
    title_kr: Optional[str] = None
    description: Optional[str] = None
    description_kr: Optional[str] = None
    topic: Optional[str] = None

    # 분류 정보
    content_type: Optional[str] = None
    categories: List[str] = []
    level: Optional[str] = None
    duration_minutes: Optional[int] = None

    # 기술 스택
    technologies: List[str] = []
    prerequisites: List[str] = []

    # 학습 정보
    learning_objectives: List[str] = []
    lab_modules: List[str] = []

    # 메타데이터
    raw_metadata: Optional[dict] = None


class AnalysisRequestResponse(BaseModel):
    """Response for a single analysis request."""

    id: str
    source_url: str
    status: str
    progress: int = Field(ge=0, le=100)
    error_message: Optional[str] = None
    result: Optional[AnalysisResultResponse] = None
    content_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        """Pydantic config."""

        from_attributes = True


class AnalysisRequestDetailResponse(AnalysisRequestResponse):
    """Detailed response including status history."""

    status_history: List[StatusHistoryResponse] = []


class AnalysisRequestListResponse(BaseModel):
    """Response for listing analysis requests."""

    items: List[AnalysisRequestResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class AnalysisRequestStatusUpdate(BaseModel):
    """Request for manually updating analysis status (admin only)."""

    status: str
    message: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
