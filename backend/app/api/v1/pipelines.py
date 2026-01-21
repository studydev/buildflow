"""
Pipeline Control API endpoints.

Per tasks.md T111-T116:
- POST /api/v1/pipelines - Enqueue pipeline (T111)
- GET /api/v1/pipelines/{run_id} - Get status (T112)
- GET /api/v1/pipelines/{run_id}/logs - Get logs (T113)
- POST /api/v1/pipelines/{run_id}/retry - Retry failed (T114)
- POST /api/v1/pipelines/{run_id}/cancel - Cancel pipeline (T115)
- GET /api/v1/content/{id}/pipeline-history - List history (T116)
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.core.exceptions import NotFoundError
from app.dependencies import get_current_user, require_role
from app.models.enums import UserRole
from app.models.user import UserPublic
from app.schemas import APIResponse, Meta
from app.schemas.pipeline import (
    CancelPipelineRequest,
    EnqueuePipelineRequest,
    EnqueuePipelineResponse,
    PipelineHistoryResponse,
    PipelineLogsResponse,
    PipelineRunDetailResponse,
    PipelineRunResponse,
)
from app.services.pipeline_service import get_pipeline_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipelines", tags=["Pipelines"])


# =============================================================================
# Pipeline Enqueue (T111)
# =============================================================================


@router.post(
    "",
    response_model=APIResponse[EnqueuePipelineResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a new pipeline",
    description="Enqueue a pipeline job for execution. Returns 202 Accepted with run_id.",
)
async def enqueue_pipeline(
    request: Request,
    body: EnqueuePipelineRequest,
    user: UserPublic = Depends(require_role(UserRole.CONTRIBUTOR)),
):
    """
    Enqueue a new pipeline for execution.

    Per tasks.md T111:
    - Validates input (source_url or content_id required)
    - Creates PipelineRun with status=pending
    - Sends message to Service Bus
    - Returns 202 Accepted with run_id

    **Requires contributor role.**
    """
    # Get correlation ID from request state (set by middleware)
    correlation_id = getattr(request.state, "correlation_id", str(UUID(int=0)))

    service = get_pipeline_service()

    # Convert user.id to UUID if it's a string
    triggered_by = UUID(user.id) if isinstance(user.id, str) else user.id

    run = await service.enqueue(
        request=body,
        triggered_by=triggered_by,
        correlation_id=correlation_id,
    )

    return APIResponse(
        success=True,
        data=EnqueuePipelineResponse(
            run_id=run.id,
            status=run.status,
            message="Pipeline enqueued successfully",
        ),
        meta=Meta.create(correlation_id=correlation_id),
    )


# =============================================================================
# Pipeline Status (T112)
# =============================================================================


@router.get(
    "/{run_id}",
    response_model=APIResponse[PipelineRunDetailResponse],
    summary="Get pipeline status",
    description="Get the current status and details of a pipeline run.",
)
async def get_pipeline_status(
    request: Request,
    run_id: UUID,
    user: UserPublic = Depends(get_current_user),
):
    """
    Get pipeline run status and details.

    Per tasks.md T112:
    - Returns full PipelineRun with status, timestamps, output/error
    - Includes output_summary when completed
    - Includes error_details when failed
    """
    correlation_id = getattr(request.state, "correlation_id", str(UUID(int=0)))

    service = get_pipeline_service()
    run = await service.get_run(run_id)

    if not run:
        raise NotFoundError("Pipeline run")

    # Calculate duration if available
    duration_seconds = None
    if run.started_at and run.completed_at:
        duration_seconds = (run.completed_at - run.started_at).total_seconds()

    response_data = PipelineRunDetailResponse(
        id=run.id,
        pipeline_type=run.pipeline_type,
        status=run.status,
        enrichment_version=run.enrichment_version,
        input_params=run.input_params,
        output_summary=run.output_summary,
        error_details=run.error_details,
        content_id=run.content_id,
        triggered_by=run.triggered_by,
        parent_run_id=run.parent_run_id,
        job_id=run.job_id,
        attempt_number=run.attempt_number,
        correlation_id=run.correlation_id,
        chain=run.chain,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=duration_seconds,
    )

    return APIResponse(
        success=True,
        data=response_data,
        meta=Meta.create(correlation_id=correlation_id),
    )


# =============================================================================
# Pipeline Logs (T113)
# =============================================================================


@router.get(
    "/{run_id}/logs",
    response_model=APIResponse[PipelineLogsResponse],
    summary="Get pipeline logs",
    description="Get execution logs from a pipeline run.",
)
async def get_pipeline_logs(
    request: Request,
    run_id: UUID,
    user: UserPublic = Depends(require_role(UserRole.CONTRIBUTOR)),
):
    """
    Get execution logs from a pipeline run.

    Per tasks.md T113:
    - Fetches logs from Container Apps Job execution
    - Handles case where job hasn't started yet

    TODO: Implement log fetching from Container Apps in Milestone 2+.
    For now, returns placeholder with run status info.
    """
    correlation_id = getattr(request.state, "correlation_id", str(UUID(int=0)))

    service = get_pipeline_service()
    run = await service.get_run(run_id)

    if not run:
        raise NotFoundError("Pipeline run")

    # TODO: Fetch actual logs from Azure Container Apps Job
    # For Milestone 1, return placeholder
    from app.schemas.pipeline import PipelineLogEntry

    logs = []

    # Add status-based log entries
    if run.created_at:
        logs.append(PipelineLogEntry(
            timestamp=run.created_at,
            level="INFO",
            message=f"Pipeline {run.pipeline_type.value} created",
            metadata={"status": "pending"},
        ))

    if run.started_at:
        logs.append(PipelineLogEntry(
            timestamp=run.started_at,
            level="INFO",
            message=f"Pipeline execution started (attempt {run.attempt_number})",
            metadata={"job_id": run.job_id},
        ))

    if run.completed_at and run.status.value == "completed":
        logs.append(PipelineLogEntry(
            timestamp=run.completed_at,
            level="INFO",
            message="Pipeline completed successfully",
            metadata=run.output_summary,
        ))
    elif run.completed_at and run.status.value == "failed":
        logs.append(PipelineLogEntry(
            timestamp=run.completed_at,
            level="ERROR",
            message="Pipeline execution failed",
            metadata=run.error_details,
        ))

    return APIResponse(
        success=True,
        data=PipelineLogsResponse(
            run_id=run_id,
            logs=logs,
            has_more=False,
        ),
        meta=Meta.create(correlation_id=correlation_id),
    )


# =============================================================================
# Pipeline Retry (T114)
# =============================================================================


@router.post(
    "/{run_id}/retry",
    response_model=APIResponse[PipelineRunResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed pipeline",
    description="Retry a failed pipeline run. Increments attempt number and re-enqueues.",
)
async def retry_pipeline(
    request: Request,
    run_id: UUID,
    user: UserPublic = Depends(require_role(UserRole.CONTRIBUTOR)),
):
    """
    Retry a failed pipeline run.

    Per tasks.md T114:
    - Only works on failed pipelines (returns 400 otherwise)
    - Increments attempt_number
    - Resets status to pending
    - Re-sends to Service Bus
    """
    correlation_id = getattr(request.state, "correlation_id", str(UUID(int=0)))

    service = get_pipeline_service()

    # Convert user.id to UUID if it's a string
    triggered_by = UUID(user.id) if isinstance(user.id, str) else user.id

    run = await service.retry(
        run_id=run_id,
        triggered_by=triggered_by,
        correlation_id=correlation_id,
    )

    return APIResponse(
        success=True,
        data=PipelineRunResponse(
            id=run.id,
            pipeline_type=run.pipeline_type,
            status=run.status,
            enrichment_version=run.enrichment_version,
            input_params=run.input_params,
            output_summary=run.output_summary,
            error_details=run.error_details,
            content_id=run.content_id,
            triggered_by=run.triggered_by,
            parent_run_id=run.parent_run_id,
            job_id=run.job_id,
            attempt_number=run.attempt_number,
            correlation_id=run.correlation_id,
            chain=run.chain,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        ),
        meta=Meta.create(correlation_id=correlation_id),
    )


# =============================================================================
# Pipeline Cancel (T115)
# =============================================================================


@router.post(
    "/{run_id}/cancel",
    response_model=APIResponse[PipelineRunResponse],
    summary="Cancel a pipeline",
    description="Cancel a pending or running pipeline.",
)
async def cancel_pipeline(
    request: Request,
    run_id: UUID,
    body: Optional[CancelPipelineRequest] = None,
    user: UserPublic = Depends(require_role(UserRole.CONTRIBUTOR)),
):
    """
    Cancel a pending or running pipeline.

    Per tasks.md T115:
    - Sets status to cancelled
    - Works on pending or running pipelines
    - Returns 400 for already completed/failed
    """
    correlation_id = getattr(request.state, "correlation_id", str(UUID(int=0)))

    reason = body.reason if body else None

    service = get_pipeline_service()

    run = await service.cancel(
        run_id=run_id,
        reason=reason,
    )

    return APIResponse(
        success=True,
        data=PipelineRunResponse(
            id=run.id,
            pipeline_type=run.pipeline_type,
            status=run.status,
            enrichment_version=run.enrichment_version,
            input_params=run.input_params,
            output_summary=run.output_summary,
            error_details=run.error_details,
            content_id=run.content_id,
            triggered_by=run.triggered_by,
            parent_run_id=run.parent_run_id,
            job_id=run.job_id,
            attempt_number=run.attempt_number,
            correlation_id=run.correlation_id,
            chain=run.chain,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        ),
        meta=Meta.create(correlation_id=correlation_id),
    )


# =============================================================================
# Pipeline History (T116)
# =============================================================================


# Note: This endpoint is under /content, but we define it here for organization.
# It will be re-exported or mounted appropriately.

history_router = APIRouter(prefix="/content", tags=["Content"])


@history_router.get(
    "/{content_id}/pipeline-history",
    response_model=APIResponse[PipelineHistoryResponse],
    summary="Get pipeline history for content",
    description="List all pipeline runs for a content item, ordered by created_at desc.",
)
async def get_pipeline_history(
    request: Request,
    content_id: UUID,
    limit: int = 50,
    offset: int = 0,
    user: UserPublic = Depends(require_role(UserRole.CONTRIBUTOR)),
):
    """
    List all pipeline runs for a content item.

    Per tasks.md T116:
    - Returns list of PipelineRuns for given content_id
    - Includes all pipeline types
    - Paginated with limit/offset
    """
    correlation_id = getattr(request.state, "correlation_id", str(UUID(int=0)))

    service = get_pipeline_service()

    runs, total_count = await service.list_by_content(
        content_id=content_id,
        limit=limit,
        offset=offset,
    )

    response_runs = [
        PipelineRunResponse(
            id=run.id,
            pipeline_type=run.pipeline_type,
            status=run.status,
            enrichment_version=run.enrichment_version,
            input_params=run.input_params,
            output_summary=run.output_summary,
            error_details=run.error_details,
            content_id=run.content_id,
            triggered_by=run.triggered_by,
            parent_run_id=run.parent_run_id,
            job_id=run.job_id,
            attempt_number=run.attempt_number,
            correlation_id=run.correlation_id,
            chain=run.chain,
            created_at=run.created_at,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
        for run in runs
    ]

    return APIResponse(
        success=True,
        data=PipelineHistoryResponse(
            content_id=content_id,
            runs=response_runs,
            total_count=total_count,
        ),
        meta=Meta.create(correlation_id=correlation_id),
    )
