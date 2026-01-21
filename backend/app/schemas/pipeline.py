"""
Pipeline schemas per stack.md and design.md.

Includes:
- PipelineMessage: Service Bus message format
- Request/Response schemas for Pipeline Control API
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import PipelineStatus, PipelineType

if TYPE_CHECKING:
    from app.models.pipeline_run import PipelineRun


# =============================================================================
# Pipeline Message Schema (Service Bus)
# =============================================================================


class PipelineMessage(BaseModel):
    """
    Standard message schema for pipeline triggering via Azure Service Bus.

    Per stack.md Pipeline Message Schema.
    """

    run_id: UUID = Field(description="Unique pipeline run ID")
    pipeline_type: PipelineType = Field(description="Type of pipeline to execute")
    content_id: Optional[UUID] = Field(
        default=None,
        description="Related content ID (if applicable)"
    )
    enrichment_version: str = Field(
        default="1.0.0",
        description="Semantic version for enrichment tracking"
    )
    correlation_id: str = Field(description="Request correlation ID for tracing")
    triggered_by: Optional[UUID] = Field(
        default=None,
        description="User ID who triggered, or None for system"
    )
    input_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Pipeline-specific parameters"
    )
    parent_run_id: Optional[UUID] = Field(
        default=None,
        description="Parent run ID for chained pipelines"
    )
    attempt_number: int = Field(
        default=1,
        description="Current retry attempt"
    )
    chain: Optional[str] = Field(
        default=None,
        description="Pipeline chain name for automatic chaining"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Message creation timestamp"
    )

    def to_service_bus_message(self) -> str:
        """Serialize to JSON string for Service Bus."""
        return self.model_dump_json()

    @classmethod
    def from_service_bus_message(cls, message_body: str) -> "PipelineMessage":
        """Parse from Service Bus message body."""
        return cls.model_validate_json(message_body)

    class Config:
        use_enum_values = True


# =============================================================================
# API Request Schemas
# =============================================================================


class EnqueuePipelineRequest(BaseModel):
    """
    Request body for POST /api/v1/pipelines (enqueue).

    Per tasks.md T111.
    """

    pipeline_type: PipelineType = Field(description="Type of pipeline to execute")

    # Either source_url (for analysis) or content_id (for other pipelines)
    source_url: Optional[str] = Field(
        default=None,
        description="GitHub repository URL (required for analysis pipeline)"
    )
    content_id: Optional[UUID] = Field(
        default=None,
        description="Content ID to process (required for non-analysis pipelines)"
    )

    # Optional parameters
    chain: Optional[str] = Field(
        default=None,
        description="Pipeline chain: full_ingestion, refresh_enrichment, reindex_only"
    )
    enrichment_version: str = Field(
        default="1.0.0",
        description="Enrichment version to use"
    )
    force_refresh: bool = Field(
        default=False,
        description="Force reprocessing even if cached data exists"
    )

    @field_validator("chain")
    @classmethod
    def validate_chain(cls, v: Optional[str]) -> Optional[str]:
        """Validate chain name is one of the allowed values."""
        valid_chains = {"full_ingestion", "refresh_enrichment", "reindex_only"}
        if v is not None and v not in valid_chains:
            raise ValueError(f"Invalid chain. Must be one of: {valid_chains}")
        return v

    def model_post_init(self, __context) -> None:
        """Validate that appropriate identifiers are provided."""
        if self.pipeline_type == PipelineType.ANALYSIS:
            if not self.source_url:
                raise ValueError("source_url is required for analysis pipeline")
        else:
            if not self.content_id:
                raise ValueError(f"content_id is required for {self.pipeline_type} pipeline")


class RetryPipelineRequest(BaseModel):
    """Request body for POST /api/v1/pipelines/{run_id}/retry."""

    # No body required, but could add optional parameters later
    pass


class CancelPipelineRequest(BaseModel):
    """Request body for POST /api/v1/pipelines/{run_id}/cancel."""

    reason: Optional[str] = Field(
        default=None,
        description="Optional reason for cancellation"
    )


# =============================================================================
# API Response Schemas
# =============================================================================


class PipelineRunResponse(BaseModel):
    """
    Pipeline run in API response format.

    Per design.md §5 PipelineRun schema.
    """

    id: UUID
    pipeline_type: PipelineType
    status: PipelineStatus
    enrichment_version: str

    # Input/Output
    input_params: dict[str, Any]
    output_summary: Optional[dict[str, Any]] = None
    error_details: Optional[dict[str, Any]] = None

    # Relations
    content_id: Optional[UUID] = None
    triggered_by: Optional[UUID] = None
    parent_run_id: Optional[UUID] = None

    # Execution metadata
    job_id: Optional[str] = None
    attempt_number: int
    correlation_id: str
    chain: Optional[str] = None

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PipelineRunDetailResponse(PipelineRunResponse):
    """
    Detailed pipeline run response with additional metadata.

    Used for GET /api/v1/pipelines/{run_id}.
    """

    # Additional computed fields
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Execution duration if completed"
    )

    @classmethod
    def from_run(cls, run: "PipelineRun") -> "PipelineRunDetailResponse":  # noqa: F821
        """Create from PipelineRun model with computed fields."""
        duration = None
        if run.started_at and run.completed_at:
            duration = (run.completed_at - run.started_at).total_seconds()

        return cls(
            **run.model_dump(),
            duration_seconds=duration,
        )


class PipelineHistoryResponse(BaseModel):
    """
    Response for GET /api/v1/content/{id}/pipeline-history.
    """

    content_id: UUID
    runs: list[PipelineRunResponse]
    total_count: int

    class Config:
        from_attributes = True


class EnqueuePipelineResponse(BaseModel):
    """
    Response for POST /api/v1/pipelines.

    Returns 202 Accepted with run_id.
    """

    run_id: UUID
    status: PipelineStatus = PipelineStatus.PENDING
    message: str = "Pipeline enqueued successfully"


# =============================================================================
# Pipeline Log Schema
# =============================================================================


class PipelineLogEntry(BaseModel):
    """Individual log entry from pipeline execution."""

    timestamp: datetime
    level: str  # INFO, WARNING, ERROR, DEBUG
    message: str
    metadata: Optional[dict[str, Any]] = None


class PipelineLogsResponse(BaseModel):
    """
    Response for GET /api/v1/pipelines/{run_id}/logs.

    Per tasks.md T113.
    """

    run_id: UUID
    logs: list[PipelineLogEntry]
    has_more: bool = False
    next_cursor: Optional[str] = None
