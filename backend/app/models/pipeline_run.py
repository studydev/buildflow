"""
PipelineRun model per design.md §5.

Represents a single execution of a pipeline job (analysis, enrichment, etc.).
Each run tracks status, input/output, and execution metadata.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.enums import PipelineStatus, PipelineType, VALID_STATUS_TRANSITIONS


class PipelineRun(BaseModel):
    """
    Pipeline run document stored in Cosmos DB.
    
    Partition Key: content_id (or triggered_by for orphan runs)
    Container: pipeline_runs
    
    Per design.md §5 PipelineRun schema.
    """
    
    # Primary key
    id: UUID = Field(default_factory=uuid4, description="Unique pipeline run ID")
    
    # Pipeline identification
    pipeline_type: PipelineType = Field(description="Type of pipeline: analysis, enrichment, etc.")
    status: PipelineStatus = Field(
        default=PipelineStatus.PENDING,
        description="Current execution status"
    )
    enrichment_version: str = Field(
        default="1.0.0",
        description="Semantic version for enrichment tracking"
    )
    
    # Input/Output
    input_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Job input parameters (source_url, force_refresh, etc.)"
    )
    output_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description="Summary of results when completed"
    )
    error_details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Error information if failed"
    )
    
    # Relations
    content_id: Optional[UUID] = Field(
        default=None,
        description="Related content ID (partition key when present)"
    )
    triggered_by: Optional[UUID] = Field(
        default=None,
        description="User ID who triggered, or None for system triggers"
    )
    parent_run_id: Optional[UUID] = Field(
        default=None,
        description="Parent run ID for chained pipelines"
    )
    
    # Execution metadata
    job_id: Optional[str] = Field(
        default=None,
        description="Azure Container Apps Job execution ID"
    )
    attempt_number: int = Field(
        default=1,
        description="Current retry attempt (starts at 1)"
    )
    correlation_id: str = Field(
        description="Request correlation ID for tracing"
    )
    
    # Chain tracking
    chain: Optional[str] = Field(
        default=None,
        description="Pipeline chain name: full_ingestion, refresh_enrichment, reindex_only"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the run was created"
    )
    started_at: Optional[datetime] = Field(
        default=None,
        description="When execution started"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When execution finished (success or failure)"
    )
    
    def can_transition_to(self, new_status: PipelineStatus) -> bool:
        """
        Check if transition to new_status is valid per design.md §9.
        
        Valid transitions:
        - pending → running, cancelled
        - running → completed, failed, cancelled
        - failed → retrying, pending (manual retry)
        - retrying → running
        - completed → (terminal)
        - cancelled → (terminal)
        """
        valid_next = VALID_STATUS_TRANSITIONS.get(self.status, [])
        return new_status in valid_next
    
    def to_cosmos_document(self) -> dict[str, Any]:
        """Convert to Cosmos DB document format."""
        doc = self.model_dump(mode="json")
        # Ensure id is string for Cosmos DB
        doc["id"] = str(self.id)
        if self.content_id:
            doc["content_id"] = str(self.content_id)
        if self.triggered_by:
            doc["triggered_by"] = str(self.triggered_by)
        if self.parent_run_id:
            doc["parent_run_id"] = str(self.parent_run_id)
        return doc
    
    @classmethod
    def from_cosmos_document(cls, doc: dict[str, Any]) -> "PipelineRun":
        """Create from Cosmos DB document."""
        return cls.model_validate(doc)
    
    class Config:
        use_enum_values = True


class InvalidStatusTransitionError(Exception):
    """Raised when an invalid status transition is attempted."""
    
    def __init__(self, current: PipelineStatus, target: PipelineStatus):
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid status transition from '{current}' to '{target}'. "
            f"Valid transitions: {VALID_STATUS_TRANSITIONS.get(current, [])}"
        )
