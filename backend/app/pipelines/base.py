"""
BasePipeline class with lifecycle hooks per tasks.md T108.

This abstract base class defines the pipeline execution model:
- Lifecycle: on_start → execute → on_success/on_failure
- Status management: Updates PipelineRun status at each stage
- Retry logic: Exponential backoff for transient failures
- Chaining: Triggers next pipeline in chain on success
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from app.models.enums import PipelineStatus, PipelineType
from app.models.pipeline_run import PipelineRun
from app.repositories.pipeline_repo import get_pipeline_repository
from app.schemas.pipeline import PipelineMessage

logger = logging.getLogger(__name__)


# =============================================================================
# Pipeline Configuration
# =============================================================================


# Global timeout per design.md Clarifications
GLOBAL_TIMEOUT_SECONDS = 600  # 10 minutes

# Pipeline chains per stack.md
PIPELINE_CHAINS: dict[str, list[PipelineType]] = {
    "full_ingestion": [
        PipelineType.ANALYSIS,
        PipelineType.ENRICHMENT,
        PipelineType.LOCALIZATION,
        PipelineType.ASSET_GENERATION,
        PipelineType.INDEXING,
    ],
    "refresh_enrichment": [
        PipelineType.ENRICHMENT,
        PipelineType.LOCALIZATION,
        PipelineType.INDEXING,
    ],
    "reindex_only": [
        PipelineType.INDEXING,
    ],
}

# Retryable error types
RETRYABLE_ERRORS = (
    TimeoutError,
    ConnectionError,
    # TODO: Add Azure-specific exceptions in later milestones
    # httpx.TimeoutException,
    # azure.cosmos.exceptions.CosmosHttpResponseError,
)


# =============================================================================
# Pipeline Result
# =============================================================================


class PipelineResult(BaseModel):
    """Result of a pipeline execution."""

    success: bool
    output: dict[str, Any] = {}
    error: Optional[str] = None
    next_pipeline: Optional[PipelineType] = None


# =============================================================================
# Base Pipeline Class
# =============================================================================


class BasePipeline(ABC):
    """
    Abstract base class for all pipeline implementations.

    Per tasks.md T108, provides:
    - run(): Full lifecycle management
    - execute(): Abstract method for subclass implementation
    - on_start(), on_success(), on_failure(): Lifecycle hooks
    - update_status(): Status management
    - is_retryable(), schedule_retry(): Retry logic
    - trigger_next_pipeline(): Chaining support

    Usage:
        class AnalysisPipeline(BasePipeline):
            pipeline_type = PipelineType.ANALYSIS
            max_attempts = 3

            async def execute(self, message: PipelineMessage) -> dict:
                # Implementation
                return {"extracted": True}
    """

    # Subclasses must override
    pipeline_type: PipelineType = None  # type: ignore
    max_attempts: int = 3

    def __init__(self):
        self.repo = get_pipeline_repository()
        self._run: Optional[PipelineRun] = None
        self._queue_service = None  # Lazy loaded

    @property
    def queue_service(self):
        """Lazy load queue service to avoid circular imports."""
        if self._queue_service is None:
            from app.services.queue_service import get_queue_service
            self._queue_service = get_queue_service()
        return self._queue_service

    # =========================================================================
    # Main Execution
    # =========================================================================

    async def run(self, message: PipelineMessage) -> PipelineResult:
        """
        Execute the full pipeline lifecycle.

        Flow:
        1. Load PipelineRun from database
        2. on_start() → status = RUNNING
        3. execute() → subclass implementation
        4. on_success() → status = COMPLETED, trigger next

        On error:
        4. on_failure() → status = FAILED, optionally retry

        Args:
            message: Pipeline message from Service Bus

        Returns:
            PipelineResult with success/failure and output
        """
        try:
            # Load or verify pipeline run
            self._run = await self.repo.get_by_id(message.run_id)
            if not self._run:
                raise ValueError(f"Pipeline run not found: {message.run_id}")

            # Start execution
            await self.on_start(message)

            # Execute pipeline logic (subclass implements)
            output = await self.execute(message)

            # Success
            await self.on_success(message, output)

            return PipelineResult(
                success=True,
                output=output,
                next_pipeline=self._get_next_in_chain(message.chain),
            )

        except Exception as e:
            await self.on_failure(message, e)

            return PipelineResult(
                success=False,
                error=str(e),
            )

    @abstractmethod
    async def execute(self, message: PipelineMessage) -> dict[str, Any]:
        """
        Execute pipeline-specific logic.

        Subclasses must implement this method.

        Args:
            message: Pipeline message with input parameters

        Returns:
            Dict with execution results (stored in output_summary)

        Raises:
            Any exception on failure
        """
        pass

    # =========================================================================
    # Lifecycle Hooks
    # =========================================================================

    async def on_start(self, message: PipelineMessage) -> None:
        """
        Called when pipeline execution starts.

        Updates status to RUNNING and records start time.
        """
        logger.info(
            "Pipeline starting",
            extra={
                "run_id": str(message.run_id),
                "pipeline_type": self.pipeline_type.value,
                "attempt_number": message.attempt_number,
                "correlation_id": message.correlation_id,
            }
        )

        await self.update_status(
            PipelineStatus.RUNNING,
            job_id=self._get_job_id(),
        )

    async def on_success(self, message: PipelineMessage, output: dict[str, Any]) -> None:
        """
        Called when pipeline execution succeeds.

        Updates status to COMPLETED and triggers next pipeline in chain.
        """
        logger.info(
            "Pipeline completed successfully",
            extra={
                "run_id": str(message.run_id),
                "pipeline_type": self.pipeline_type.value,
                "correlation_id": message.correlation_id,
            }
        )

        await self.update_status(
            PipelineStatus.COMPLETED,
            output_summary=output,
        )

        # Trigger next pipeline in chain
        if message.chain:
            await self.trigger_next_pipeline(message)

    async def on_failure(self, message: PipelineMessage, error: Exception) -> None:
        """
        Called when pipeline execution fails.

        Updates status to FAILED and optionally schedules retry.
        """
        logger.error(
            "Pipeline failed",
            extra={
                "run_id": str(message.run_id),
                "pipeline_type": self.pipeline_type.value,
                "error": str(error),
                "attempt_number": message.attempt_number,
                "correlation_id": message.correlation_id,
            },
            exc_info=True,
        )

        error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "attempt_number": message.attempt_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self.update_status(
            PipelineStatus.FAILED,
            error_details=error_details,
        )

        # Check if we should retry
        if self.is_retryable(error) and message.attempt_number < self.max_attempts:
            await self.schedule_retry(message)

    # =========================================================================
    # Status Management
    # =========================================================================

    async def update_status(
        self,
        status: PipelineStatus,
        output_summary: Optional[dict[str, Any]] = None,
        error_details: Optional[dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> None:
        """
        Update pipeline run status in database.

        Validates state transition before updating.
        """
        if not self._run:
            return

        partition_key = str(self._run.content_id) if self._run.content_id else None

        self._run = await self.repo.update_status(
            run_id=self._run.id,
            new_status=status,
            partition_key=partition_key,
            output_summary=output_summary,
            error_details=error_details,
            job_id=job_id,
        )

    # =========================================================================
    # Retry Logic
    # =========================================================================

    def is_retryable(self, error: Exception) -> bool:
        """
        Check if the error is retryable.

        Returns True for transient errors like timeouts and network issues.
        """
        return isinstance(error, RETRYABLE_ERRORS)

    async def schedule_retry(self, message: PipelineMessage) -> None:
        """
        Schedule a retry with exponential backoff.

        Delay = 2^attempt_number seconds (2s, 4s, 8s, etc.)
        """
        delay_seconds = 2 ** message.attempt_number

        logger.info(
            "Scheduling pipeline retry",
            extra={
                "run_id": str(message.run_id),
                "pipeline_type": self.pipeline_type.value,
                "attempt_number": message.attempt_number + 1,
                "delay_seconds": delay_seconds,
                "correlation_id": message.correlation_id,
            }
        )

        # Update status to RETRYING
        await self.update_status(PipelineStatus.RETRYING)

        # Increment attempt and re-enqueue
        retry_message = PipelineMessage(
            run_id=message.run_id,
            pipeline_type=message.pipeline_type,
            content_id=message.content_id,
            enrichment_version=message.enrichment_version,
            correlation_id=message.correlation_id,
            triggered_by=message.triggered_by,
            input_params=message.input_params,
            parent_run_id=message.parent_run_id,
            attempt_number=message.attempt_number + 1,
            chain=message.chain,
        )

        await self.queue_service.send_with_delay(
            topic="pipeline-triggers",
            message=retry_message,
            delay_seconds=delay_seconds,
        )

    # =========================================================================
    # Chaining
    # =========================================================================

    def _get_next_in_chain(self, chain: Optional[str]) -> Optional[PipelineType]:
        """Get the next pipeline type in the chain, if any."""
        if not chain or chain not in PIPELINE_CHAINS:
            return None

        chain_sequence = PIPELINE_CHAINS[chain]
        try:
            current_index = chain_sequence.index(self.pipeline_type)
            if current_index < len(chain_sequence) - 1:
                return chain_sequence[current_index + 1]
        except ValueError:
            pass

        return None

    async def trigger_next_pipeline(self, message: PipelineMessage) -> Optional[PipelineType]:
        """
        Trigger the next pipeline in the chain.

        Per stack.md Pipeline Chaining and tasks.md T304:
        - On success, enqueue next in chain with same correlation_id and parent_run_id
        - Chain terminates correctly at end
        - Failed pipeline stops chain (no cascading)

        Returns:
            Next pipeline type if triggered, None otherwise
        """
        next_type = self._get_next_in_chain(message.chain)
        if not next_type:
            logger.info(
                "Pipeline chain complete",
                extra={
                    "run_id": str(message.run_id),
                    "chain": message.chain,
                    "correlation_id": message.correlation_id,
                }
            )
            return None

        logger.info(
            "Triggering next pipeline in chain",
            extra={
                "run_id": str(message.run_id),
                "current_type": self.pipeline_type.value,
                "next_type": next_type.value,
                "chain": message.chain,
                "correlation_id": message.correlation_id,
            }
        )

        # Create new pipeline run for next step
        from uuid import uuid4

        new_run_id = uuid4()
        new_run = PipelineRun(
            id=new_run_id,
            pipeline_type=next_type,
            status=PipelineStatus.PENDING,
            enrichment_version=message.enrichment_version,
            input_params=message.input_params,
            content_id=message.content_id,
            triggered_by=message.triggered_by,
            parent_run_id=message.run_id,  # Link to current run
            correlation_id=message.correlation_id,
            chain=message.chain,
        )

        # Persist to database
        await self.repo.create(new_run)

        # Build message for next pipeline
        next_message = PipelineMessage(
            run_id=new_run_id,
            pipeline_type=next_type,
            content_id=message.content_id,
            enrichment_version=message.enrichment_version,
            correlation_id=message.correlation_id,
            triggered_by=message.triggered_by,
            input_params=message.input_params,
            parent_run_id=message.run_id,
            attempt_number=1,
            chain=message.chain,
        )

        # Send to Service Bus
        await self.queue_service.send_to_topic("pipeline-triggers", next_message)

        logger.info(
            "Next pipeline enqueued successfully",
            extra={
                "new_run_id": str(new_run_id),
                "next_type": next_type.value,
                "parent_run_id": str(message.run_id),
                "chain": message.chain,
                "correlation_id": message.correlation_id,
            }
        )

        return next_type

    # =========================================================================
    # Helpers
    # =========================================================================

    def _get_job_id(self) -> str:
        """
        Get Azure Container Apps Job execution ID from environment.

        Returns a placeholder if not running in Container Apps.
        """
        import os
        return os.environ.get("CONTAINER_APP_JOB_EXECUTION_NAME", "local-execution")
