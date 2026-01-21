"""
Pipeline service for orchestration and control plane operations.

Per tasks.md T111: Create pipeline_service.py for orchestration.

Provides:
- enqueue(): Create pipeline run and send to Service Bus
- get_run(): Get pipeline status
- retry(): Retry a failed pipeline
- cancel(): Cancel a running pipeline
- list_by_content(): Get pipeline history for content
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import PipelineStatus, PipelineType
from app.models.pipeline_run import InvalidStatusTransitionError, PipelineRun
from app.repositories.pipeline_repo import get_pipeline_repository
from app.schemas.pipeline import (
    EnqueuePipelineRequest,
    PipelineMessage,
    PipelineRunResponse,
)
from app.services.queue_service import get_queue_service

logger = logging.getLogger(__name__)


# Topic name for pipeline triggers
PIPELINE_TRIGGERS_TOPIC = "pipeline-triggers"


class PipelineService:
    """
    Service for pipeline orchestration.
    
    Per tasks.md T111:
    - enqueue(): Create and queue a new pipeline run
    - get_run(): Get pipeline status and details
    - retry(): Retry a failed pipeline
    - cancel(): Cancel a pending/running pipeline
    - list_by_content(): List pipeline history for content
    """
    
    def __init__(self):
        self.repo = get_pipeline_repository()
        self.queue = get_queue_service()
    
    async def enqueue(
        self,
        request: EnqueuePipelineRequest,
        triggered_by: Optional[UUID],
        correlation_id: str,
    ) -> PipelineRun:
        """
        Enqueue a new pipeline run.
        
        Per tasks.md T111:
        1. Validate request
        2. Create PipelineRun with status=pending
        3. Build PipelineMessage
        4. Send to Service Bus topic
        5. Return created run
        
        Args:
            request: Enqueue request with pipeline type and params
            triggered_by: User ID who triggered (None for system)
            correlation_id: Request correlation ID
            
        Returns:
            Created PipelineRun with status=pending
        """
        # Build input params from request
        input_params: dict[str, object] = {
            "force_refresh": request.force_refresh,
        }
        if request.source_url:
            input_params["source_url"] = request.source_url
        
        # Determine content_id
        content_id = request.content_id
        
        # For analysis pipeline, content_id may be None initially
        # It gets set after the content is created
        
        # Check for duplicate running pipelines (idempotency)
        if content_id:
            existing = await self._check_duplicate(content_id, request.pipeline_type)
            if existing:
                raise ConflictError(
                    f"Pipeline {request.pipeline_type.value} already running for this content. "
                    f"Run ID: {existing.id}"
                )
        
        # Create PipelineRun
        run = PipelineRun(
            id=uuid4(),
            pipeline_type=request.pipeline_type,
            status=PipelineStatus.PENDING,
            enrichment_version=request.enrichment_version,
            input_params=input_params,
            content_id=content_id,
            triggered_by=triggered_by,
            correlation_id=correlation_id,
            chain=request.chain,
        )
        
        # Persist to Cosmos DB
        created_run = await self.repo.create(run)
        
        # Build message for Service Bus
        message = PipelineMessage(
            run_id=created_run.id,
            pipeline_type=created_run.pipeline_type,
            content_id=content_id,
            enrichment_version=created_run.enrichment_version,
            correlation_id=correlation_id,
            triggered_by=triggered_by,
            input_params=input_params,
            chain=request.chain,
        )
        
        # Send to Service Bus
        await self.queue.send_to_topic(PIPELINE_TRIGGERS_TOPIC, message)
        
        logger.info(
            "Pipeline enqueued",
            extra={
                "run_id": str(created_run.id),
                "pipeline_type": created_run.pipeline_type.value,
                "content_id": str(content_id) if content_id else None,
                "triggered_by": str(triggered_by) if triggered_by else None,
                "correlation_id": correlation_id,
            }
        )
        
        return created_run
    
    async def get_run(self, run_id: UUID) -> Optional[PipelineRun]:
        """
        Get a pipeline run by ID.
        
        Per tasks.md T112.
        
        Args:
            run_id: Pipeline run UUID
            
        Returns:
            PipelineRun if found, None otherwise
        """
        return await self.repo.get_by_id(run_id)
    
    async def retry(
        self,
        run_id: UUID,
        triggered_by: UUID,
        correlation_id: str,
    ) -> PipelineRun:
        """
        Retry a failed pipeline run.
        
        Per tasks.md T114:
        1. Validate run is in failed status
        2. Increment attempt_number
        3. Reset status to pending
        4. Re-send to Service Bus
        
        Args:
            run_id: Pipeline run to retry
            triggered_by: User ID performing the retry
            correlation_id: Request correlation ID
            
        Returns:
            Updated PipelineRun with incremented attempt
            
        Raises:
            NotFoundError: If run not found
            ValidationError: If run is not in failed status
        """
        run = await self.repo.get_by_id(run_id)
        if not run:
            raise NotFoundError("Pipeline run")
        
        if run.status != PipelineStatus.FAILED:
            raise ValidationError(
                f"Cannot retry pipeline with status '{run.status.value}'. "
                "Only failed pipelines can be retried."
            )
        
        # Increment attempt and reset status
        partition_key = str(run.content_id) if run.content_id else None
        updated_run = await self.repo.increment_attempt(run_id, partition_key)
        
        # Build retry message
        message = PipelineMessage(
            run_id=updated_run.id,
            pipeline_type=updated_run.pipeline_type,
            content_id=updated_run.content_id,
            enrichment_version=updated_run.enrichment_version,
            correlation_id=correlation_id,
            triggered_by=triggered_by,
            input_params=updated_run.input_params,
            parent_run_id=updated_run.parent_run_id,
            attempt_number=updated_run.attempt_number,
            chain=updated_run.chain,
        )
        
        # Re-send to Service Bus
        await self.queue.send_to_topic(PIPELINE_TRIGGERS_TOPIC, message)
        
        logger.info(
            "Pipeline retry enqueued",
            extra={
                "run_id": str(run_id),
                "attempt_number": updated_run.attempt_number,
                "triggered_by": str(triggered_by),
                "correlation_id": correlation_id,
            }
        )
        
        return updated_run
    
    async def cancel(
        self,
        run_id: UUID,
        reason: Optional[str] = None,
    ) -> PipelineRun:
        """
        Cancel a pending or running pipeline.
        
        Per tasks.md T115:
        - Sets status to cancelled
        - Only works on pending or running pipelines
        
        Args:
            run_id: Pipeline run to cancel
            reason: Optional cancellation reason
            
        Returns:
            Updated PipelineRun with cancelled status
            
        Raises:
            NotFoundError: If run not found
            ValidationError: If run cannot be cancelled
        """
        run = await self.repo.get_by_id(run_id)
        if not run:
            raise NotFoundError("Pipeline run")
        
        if run.status not in (PipelineStatus.PENDING, PipelineStatus.RUNNING):
            raise ValidationError(
                f"Cannot cancel pipeline with status '{run.status.value}'. "
                "Only pending or running pipelines can be cancelled."
            )
        
        partition_key = str(run.content_id) if run.content_id else None
        
        error_details = None
        if reason:
            error_details = {
                "cancelled_reason": reason,
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
            }
        
        updated_run = await self.repo.update_status(
            run_id=run_id,
            new_status=PipelineStatus.CANCELLED,
            partition_key=partition_key,
            error_details=error_details,
        )
        
        logger.info(
            "Pipeline cancelled",
            extra={
                "run_id": str(run_id),
                "reason": reason,
                "correlation_id": run.correlation_id,
            }
        )
        
        # TODO: In Milestone 2+, attempt to stop the Container Apps Job if running
        
        return updated_run
    
    async def list_by_content(
        self,
        content_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PipelineRun], int]:
        """
        List all pipeline runs for a content item.
        
        Per tasks.md T116.
        
        Args:
            content_id: Content UUID
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            Tuple of (list of PipelineRuns, total count)
        """
        return await self.repo.list_by_content_id(content_id, limit, offset)
    
    async def _check_duplicate(
        self,
        content_id: UUID,
        pipeline_type: PipelineType,
    ) -> Optional[PipelineRun]:
        """
        Check if a pipeline is already running for the content.
        
        Per design.md Clarifications - Sequential Queue:
        Same content_id pipelines execute one at a time.
        
        Returns the running pipeline if found, None otherwise.
        """
        runs = await self.repo.list_by_type(
            pipeline_type=pipeline_type,
            status=PipelineStatus.RUNNING,
            limit=100,
        )
        
        for run in runs:
            if run.content_id == content_id:
                return run
        
        # Also check pending
        pending_runs = await self.repo.list_by_type(
            pipeline_type=pipeline_type,
            status=PipelineStatus.PENDING,
            limit=100,
        )
        
        for run in pending_runs:
            if run.content_id == content_id:
                return run
        
        return None


# Singleton instance
_pipeline_service: Optional[PipelineService] = None


def get_pipeline_service() -> PipelineService:
    """Get or create the pipeline service singleton."""
    global _pipeline_service
    if _pipeline_service is None:
        _pipeline_service = PipelineService()
    return _pipeline_service
