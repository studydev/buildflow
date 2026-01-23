"""Analysis Requests API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from app.core.exceptions import NotFoundError, ValidationError
from app.dependencies import require_contributor
from app.models.enums import AnalysisStatus
from app.models.user import User
from app.schemas import APIResponse, Meta
from app.schemas.analysis import (
    AnalysisRequestCreate,
    AnalysisRequestDetailResponse,
    AnalysisRequestListResponse,
    AnalysisRequestResponse,
    AnalysisResultResponse,
    StatusHistoryResponse,
)
from app.services.analysis_service import AnalysisService, get_analysis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis-requests", tags=["analysis"])


def _to_response(request) -> AnalysisRequestResponse:
    """Convert AnalysisRequest model to response schema."""
    result_response = None
    if request.result:
        result_response = AnalysisResultResponse(
            title=request.result.title,
            title_kr=request.result.title_kr,
            description=request.result.description,
            description_kr=request.result.description_kr,
            topic=request.result.topic,
            content_type=request.result.content_type,
            categories=request.result.categories or [],
            level=request.result.level,
            duration_minutes=request.result.duration_minutes,
            technologies=request.result.technologies or [],
            prerequisites=request.result.prerequisites or [],
            learning_objectives=request.result.learning_objectives or [],
            lab_modules=request.result.lab_modules or [],
            raw_metadata=request.result.raw_metadata,
        )

    return AnalysisRequestResponse(
        id=request.id,
        source_url=request.source_url,
        status=request.status.value if hasattr(request.status, 'value') else request.status,
        progress=request.progress,
        error_message=request.error_message,
        result=result_response,
        created_at=request.created_at,
        updated_at=request.updated_at,
        completed_at=request.completed_at,
    )


def _to_detail_response(request) -> AnalysisRequestDetailResponse:
    """Convert AnalysisRequest model to detailed response schema."""
    base = _to_response(request)

    status_history = [
        StatusHistoryResponse(
            status=entry.status.value if hasattr(entry.status, 'value') else entry.status,
            timestamp=entry.timestamp,
            message=entry.message,
        )
        for entry in (request.status_history or [])
    ]

    return AnalysisRequestDetailResponse(
        **base.model_dump(),
        status_history=status_history,
    )


@router.post(
    "",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new analysis request",
    description="Submit a GitHub repository URL for analysis. Only github.com URLs are allowed.",
)
async def create_analysis_request(
    data: AnalysisRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_contributor),
    service: AnalysisService = Depends(get_analysis_service),
):
    """
    Create a new analysis request for a GitHub repository.

    - **source_url**: GitHub repository URL (https://github.com/{owner}/{repo})
                      or redirect URL (e.g., https://aka.ms/...) that resolves to GitHub

    Returns the created request immediately. Analysis runs in background.
    Poll GET /analysis-requests/{id} to check status.
    """
    # Validate URL and resolve redirects (SSRF protection)
    is_valid, resolved_url, error_msg = await service.validate_and_resolve_url(data.source_url)
    if not is_valid:
        raise ValidationError(error_msg)

    # Update the source URL with the resolved URL
    data.source_url = resolved_url

    # Create or find existing request
    request, is_duplicate = await service.create_request(
        user_id=current_user.id,
        data=data,
        check_duplicate=True,
    )

    # Start background processing if this is a new request
    if not is_duplicate:
        from app.services.analysis_pipeline import run_analysis_pipeline

        # Add background task to process the request
        background_tasks.add_task(
            run_analysis_pipeline,
            request_id=request.id,
            user_id=request.user_id,
        )
        logger.info(f"Queued analysis pipeline for request {request.id}")

    response_data = _to_response(request)

    return APIResponse(
        success=True,
        data=response_data.model_dump(),
        meta=Meta.create(
            message="Analysis request already exists" if is_duplicate else "Analysis request created and processing started",
        ),
    )


@router.get(
    "",
    response_model=APIResponse,
    summary="List my analysis requests",
    description="Get a paginated list of the current user's analysis requests.",
)
async def list_analysis_requests(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(require_contributor),
    service: AnalysisService = Depends(get_analysis_service),
):
    """List analysis requests for the current user."""
    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = AnalysisStatus(status)
        except ValueError:
            raise ValidationError(f"Invalid status: {status}")

    requests, total = await service.list_user_requests(
        user_id=current_user.id,
        page=page,
        limit=limit,
        status=status_filter,
    )

    items = [_to_response(r) for r in requests]
    has_more = (page * limit) < total

    response_data = AnalysisRequestListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        has_more=has_more,
    )

    return APIResponse(
        success=True,
        data=response_data.model_dump(),
    )


@router.get(
    "/{request_id}",
    response_model=APIResponse,
    summary="Get analysis request details",
    description="Get detailed information about a specific analysis request.",
)
async def get_analysis_request(
    request_id: str,
    current_user: User = Depends(require_contributor),
    service: AnalysisService = Depends(get_analysis_service),
):
    """Get a specific analysis request by ID."""
    request = await service.get_request(request_id, current_user.id)

    if not request:
        raise NotFoundError(f"Analysis request not found: {request_id}")

    response_data = _to_detail_response(request)

    return APIResponse(
        success=True,
        data=response_data.model_dump(),
    )


@router.delete(
    "/{request_id}",
    response_model=APIResponse,
    summary="Delete analysis request",
    description="Delete an analysis request. Only the owner can delete their requests.",
)
async def delete_analysis_request(
    request_id: str,
    current_user: User = Depends(require_contributor),
    service: AnalysisService = Depends(get_analysis_service),
):
    """Delete an analysis request."""
    deleted = await service.delete_request(request_id, current_user.id)

    if not deleted:
        raise NotFoundError(f"Analysis request not found: {request_id}")

    return APIResponse(
        success=True,
        data={"deleted": True},
        meta=Meta.create(message="Analysis request deleted"),
    )


@router.post(
    "/{request_id}/cancel",
    response_model=APIResponse,
    summary="Cancel analysis request",
    description="Cancel a pending or in-progress analysis request.",
)
async def cancel_analysis_request(
    request_id: str,
    current_user: User = Depends(require_contributor),
    service: AnalysisService = Depends(get_analysis_service),
):
    """Cancel an analysis request."""
    request = await service.cancel_request(request_id, current_user.id)

    if not request:
        raise NotFoundError(f"Analysis request not found: {request_id}")

    response_data = _to_response(request)

    return APIResponse(
        success=True,
        data=response_data.model_dump(),
        meta=Meta.create(message="Analysis request cancelled"),
    )
