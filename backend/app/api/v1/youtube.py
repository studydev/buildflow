"""YouTube Analysis Requests API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from pydantic import BaseModel, Field

from app.core.exceptions import NotFoundError, ValidationError
from app.dependencies import require_contributor
from app.models.enums import YouTubeAnalysisStatus
from app.models.user import User
from app.models.youtube import YouTubeAnalysisRequest, YouTubeContent
from app.repositories.youtube_repo import get_youtube_repo
from app.schemas import APIResponse, Meta
from app.services.youtube_content_service import get_youtube_content_service
from app.services.youtube_pipeline import get_youtube_pipeline, get_youtube_service
from app.services.youtube_search_service import get_youtube_search_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/youtube", tags=["youtube"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class YouTubeAnalysisCreate(BaseModel):
    """Request schema for creating a YouTube analysis request."""

    source_url: str = Field(
        ...,
        description="YouTube video URL",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )


class YouTubeAnalysisResultResponse(BaseModel):
    """Response schema for YouTube analysis result."""

    video_id: Optional[str] = None
    video_url: Optional[str] = None
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    title: Optional[str] = None
    title_en: Optional[str] = None
    title_kr: Optional[str] = None
    description_en: Optional[str] = None
    description_kr: Optional[str] = None
    thumbnail_url: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    duration_seconds: int = 0
    upload_date: Optional[str] = None
    script_summary_en: Optional[str] = None
    script_summary_kr: Optional[str] = None
    content_type: Optional[str] = None
    categories: list[str] = []
    technologies: list[str] = []
    level: Optional[str] = None


class YouTubeAnalysisResponse(BaseModel):
    """Response schema for a YouTube analysis request."""

    id: str
    source_url: str
    video_id: str
    status: str
    progress: int
    error_message: Optional[str] = None
    result: Optional[YouTubeAnalysisResultResponse] = None
    content_ids: list[str] = []
    user_email: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class YouTubeAnalysisListResponse(BaseModel):
    """Response schema for listing YouTube analysis requests."""

    items: list[YouTubeAnalysisResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class YouTubeContentResponse(BaseModel):
    """Response schema for YouTube content."""

    id: str
    video_id: str
    analysis_request_id: Optional[str] = None  # For script lookup
    source_url: str
    channel_name: Optional[str] = None
    title: str
    title_en: Optional[str] = None
    title_kr: Optional[str] = None
    description: str
    description_en: Optional[str] = None
    description_kr: Optional[str] = None
    thumbnail_url: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    duration_seconds: int = 0
    duration_minutes: int = 0
    upload_date: Optional[str] = None
    script_summary_en: Optional[str] = None
    script_summary_kr: Optional[str] = None
    content_type: str
    status: str
    categories: list[str] = []
    technologies: list[str] = []
    level: str
    created_at: str
    updated_at: str
    published_at: Optional[str] = None


class YouTubeContentListResponse(BaseModel):
    """Response schema for listing YouTube content."""

    items: list[YouTubeContentResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class YouTubeContentUpdate(BaseModel):
    """Request schema for updating YouTube content."""

    title: Optional[str] = None
    title_en: Optional[str] = None
    title_kr: Optional[str] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    description_kr: Optional[str] = None
    script_summary_en: Optional[str] = None
    script_summary_kr: Optional[str] = None
    categories: Optional[list[str]] = None
    technologies: Optional[list[str]] = None
    level: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================


def _to_analysis_response(request: YouTubeAnalysisRequest) -> YouTubeAnalysisResponse:
    """Convert YouTubeAnalysisRequest to response schema."""
    result_response = None
    if request.result:
        result_response = YouTubeAnalysisResultResponse(
            video_id=request.result.video_id,
            video_url=request.result.video_url,
            channel_id=request.result.channel_id,
            channel_name=request.result.channel_name,
            title=request.result.title,
            title_en=request.result.title_en,
            title_kr=request.result.title_kr,
            description_en=request.result.description_en,
            description_kr=request.result.description_kr,
            thumbnail_url=request.result.thumbnail_url,
            view_count=request.result.view_count,
            like_count=request.result.like_count,
            duration_seconds=request.result.duration_seconds,
            upload_date=request.result.upload_date,
            script_summary_en=request.result.script_summary_en,
            script_summary_kr=request.result.script_summary_kr,
            content_type=request.result.content_type,
            categories=request.result.categories or [],
            technologies=request.result.technologies or [],
            level=request.result.level,
        )

    return YouTubeAnalysisResponse(
        id=request.id,
        source_url=request.source_url,
        video_id=request.video_id,
        status=request.status.value,
        progress=request.progress,
        error_message=request.error_message,
        result=result_response,
        content_ids=request.content_ids or [],
        user_email=request.user_email,
        created_at=request.created_at.isoformat(),
        updated_at=request.updated_at.isoformat(),
        completed_at=request.completed_at.isoformat() if request.completed_at else None,
    )


def _to_content_response(content: YouTubeContent) -> YouTubeContentResponse:
    """Convert YouTubeContent to response schema."""
    return YouTubeContentResponse(
        id=content.id,
        video_id=content.video_id,
        analysis_request_id=content.analysis_request_id,
        source_url=content.source_url,
        channel_name=content.channel_name,
        title=content.title,
        title_en=content.title_en,
        title_kr=content.title_kr,
        description=content.description,
        description_en=content.description_en,
        description_kr=content.description_kr,
        thumbnail_url=content.thumbnail_url,
        view_count=content.view_count,
        like_count=content.like_count,
        duration_seconds=content.duration_seconds,
        duration_minutes=content.duration_minutes,
        upload_date=content.upload_date.isoformat() if content.upload_date else None,
        script_summary_en=content.script_summary_en,
        script_summary_kr=content.script_summary_kr,
        content_type=content.content_type.value if hasattr(content.content_type, 'value') else content.content_type,
        status=content.status.value if hasattr(content.status, 'value') else content.status,
        categories=content.categories or [],
        technologies=content.technologies or [],
        level=content.level,
        created_at=content.created_at.isoformat(),
        updated_at=content.updated_at.isoformat(),
        published_at=content.published_at.isoformat() if content.published_at else None,
    )


# =============================================================================
# Background Task
# =============================================================================


async def run_youtube_pipeline(request_id: str, user_id: str):
    """Run YouTube analysis pipeline in background."""
    logger.info(f"Starting YouTube pipeline for request {request_id}")

    try:
        youtube_repo = get_youtube_repo()
        pipeline = get_youtube_pipeline()

        # Get the request
        request = await youtube_repo.get_by_id_no_auth(request_id)
        if not request:
            logger.error(f"YouTube request not found: {request_id}")
            return

        # Process through pipeline
        await pipeline.process_request(request)
        logger.info(f"YouTube pipeline completed for request {request_id}")

    except Exception as e:
        logger.error(f"YouTube pipeline failed for request {request_id}: {e}")
        # Update request status to failed
        try:
            youtube_repo = get_youtube_repo()
            request = await youtube_repo.get_by_id_no_auth(request_id)
            if request:
                request.set_error(str(e))
                await youtube_repo.update(request)
        except Exception as update_error:
            logger.error(f"Failed to update error status: {update_error}")


# =============================================================================
# Analysis Request Endpoints
# =============================================================================


@router.post(
    "/analyze",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new YouTube analysis request",
    description="Submit a YouTube video URL for analysis.",
)
async def create_youtube_analysis(
    data: YouTubeAnalysisCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_contributor),
):
    """
    Create a new analysis request for a YouTube video.

    - **source_url**: YouTube video URL (https://www.youtube.com/watch?v=...)

    Returns the created request immediately. Analysis runs in background.
    Poll GET /youtube/requests/{id} to check status.
    """
    youtube_service = get_youtube_service()
    youtube_repo = get_youtube_repo()

    # Validate YouTube URL
    is_valid, error_msg = youtube_service.validate_youtube_url(data.source_url)
    if not is_valid:
        raise ValidationError(error_msg)

    # Extract video ID
    video_id = youtube_service.extract_video_id(data.source_url)
    if not video_id:
        raise ValidationError("Could not extract video ID from URL")

    # Check for duplicate (same video by same user)
    existing = await youtube_repo.get_by_video_id(video_id, current_user.id)
    if existing and existing.status == YouTubeAnalysisStatus.COMPLETED:
        return APIResponse(
            success=True,
            data=_to_analysis_response(existing).model_dump(),
            meta=Meta.create(message="Analysis request already exists for this video"),
        )

    # Create new request
    request = YouTubeAnalysisRequest(
        user_id=current_user.id,
        user_email=current_user.email,
        source_url=data.source_url,
        video_id=video_id,
        status=YouTubeAnalysisStatus.PENDING,
    )

    await youtube_repo.create(request)
    logger.info(f"Created YouTube analysis request: {request.id}")

    # Start background processing
    background_tasks.add_task(run_youtube_pipeline, request.id, request.user_id)
    logger.info(f"Queued YouTube pipeline for request {request.id}")

    return APIResponse(
        success=True,
        data=_to_analysis_response(request).model_dump(),
        meta=Meta.create(message="YouTube analysis request created and processing started"),
    )


@router.get(
    "/requests",
    response_model=APIResponse,
    summary="List YouTube analysis requests",
    description="Get a paginated list of YouTube analysis requests for the current user.",
)
async def list_youtube_requests(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(require_contributor),
):
    """List YouTube analysis requests for the current user."""
    youtube_repo = get_youtube_repo()

    # Parse status filter
    status_enum = None
    if status_filter:
        try:
            status_enum = YouTubeAnalysisStatus(status_filter)
        except ValueError:
            raise ValidationError(f"Invalid status: {status_filter}")

    offset = (page - 1) * limit
    requests = await youtube_repo.list_by_user(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        status=status_enum,
    )
    total = await youtube_repo.count_by_user(current_user.id)

    items = [_to_analysis_response(r) for r in requests]
    has_more = (page * limit) < total

    response_data = YouTubeAnalysisListResponse(
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
    "/requests/{request_id}",
    response_model=APIResponse,
    summary="Get YouTube analysis request details",
    description="Get detailed information about a specific YouTube analysis request.",
)
async def get_youtube_request(
    request_id: str,
    current_user: User = Depends(require_contributor),
):
    """Get a specific YouTube analysis request by ID."""
    youtube_repo = get_youtube_repo()

    request = await youtube_repo.get_by_id(request_id, current_user.id)
    if not request:
        raise NotFoundError(f"YouTube analysis request not found: {request_id}")

    return APIResponse(
        success=True,
        data=_to_analysis_response(request).model_dump(),
    )


@router.post(
    "/requests/{request_id}/retry",
    response_model=APIResponse,
    summary="Retry a failed YouTube analysis",
    description="Retry a failed YouTube analysis request (e.g., after quota reset).",
)
async def retry_youtube_request(
    request_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_contributor),
):
    """Retry a failed YouTube analysis request."""
    youtube_repo = get_youtube_repo()

    request = await youtube_repo.get_by_id(request_id, current_user.id)
    if not request:
        raise NotFoundError(f"YouTube analysis request not found: {request_id}")

    if request.status != YouTubeAnalysisStatus.FAILED:
        raise ValidationError("Only failed requests can be retried")

    # Reset status to pending
    request.status = YouTubeAnalysisStatus.PENDING
    request.progress = 0
    request.error_message = None
    await youtube_repo.update(request)

    # Start background processing
    background_tasks.add_task(run_youtube_pipeline, request.id, request.user_id)
    logger.info(f"Queued YouTube pipeline retry for request {request.id}")

    return APIResponse(
        success=True,
        data=_to_analysis_response(request).model_dump(),
        meta=Meta.create(message="YouTube analysis retry started"),
    )


@router.delete(
    "/requests/{request_id}",
    response_model=APIResponse,
    summary="Delete YouTube analysis request",
    description="Delete a YouTube analysis request and its linked content.",
)
async def delete_youtube_request(
    request_id: str,
    current_user: User = Depends(require_contributor),
):
    """Delete a YouTube analysis request and its linked content."""
    youtube_repo = get_youtube_repo()
    content_service = get_youtube_content_service()

    request = await youtube_repo.get_by_id(request_id, current_user.id)
    if not request:
        raise NotFoundError(f"YouTube analysis request not found: {request_id}")

    deleted_contents = []

    # Delete linked content
    if request.content_ids:
        for content_id in request.content_ids:
            try:
                await content_service.delete_content(content_id)
                deleted_contents.append(content_id)
            except Exception as e:
                logger.warning(f"Failed to delete content {content_id}: {e}")

    # Delete the request
    await youtube_repo.delete(request_id)

    return APIResponse(
        success=True,
        data={
            "deleted": True,
            "deleted_contents": deleted_contents,
        },
        meta=Meta.create(message=f"YouTube analysis request deleted with {len(deleted_contents)} content(s)"),
    )


# =============================================================================
# Search Endpoints (Azure AI Search)
# =============================================================================


@router.get(
    "/search",
    response_model=APIResponse,
    summary="Search YouTube content using Azure AI Search",
    description="Search published YouTube content with keyword and vector search capabilities.",
)
async def search_youtube_contents(
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    language: Optional[str] = Query(None, description="Filter by language (en, ko)"),
    sort: Optional[str] = Query(None, description="Sort field (popular, likes, recent, relevance)"),
    order: Optional[str] = Query("desc", description="Sort order (asc, desc)"),
):
    """Search YouTube content using Azure AI Search (public endpoint)."""
    search_service = get_youtube_search_service()

    offset = (page - 1) * limit

    # Build filters
    filters = {}
    if category:
        filters["categories"] = category
    if content_type:
        filters["content_type"] = content_type
    if language:
        filters["language"] = language

    try:
        # Build order_by clause based on sort parameter
        order_by = None
        if sort:
            sort_field_map = {
                "popular": "view_count",
                "likes": "like_count",
                "recent": "created_at",
            }
            if sort in sort_field_map:
                sort_field = sort_field_map[sort]
                sort_order = order if order in ("asc", "desc") else "desc"
                order_by = f"{sort_field} {sort_order}"

        result = await search_service.search(
            query=q or "*",
            top=limit,
            skip=offset,
            filters=filters if filters else None,
            facets=["categories", "level", "content_type"] if True else None,
            order_by=order_by,
        )

        # Transform search results to content response format
        items = []
        for hit in result.results:
            items.append({
                "id": hit.id,
                "video_id": hit.video_id,
                "analysis_request_id": hit.analysis_request_id,
                "source_url": hit.source_url,
                "thumbnail_url": hit.thumbnail_url,
                "channel_name": hit.channel_name,
                "title": hit.title,
                "title_en": hit.title,
                "title_kr": hit.title_kr,
                "description": hit.description,
                "description_en": hit.description,
                "description_kr": hit.description_kr,
                "content_type": hit.content_type,
                "categories": hit.categories or [],
                "technologies": hit.technologies or [],
                "level": hit.level,
                "duration_minutes": hit.duration_minutes,
                "duration_seconds": hit.duration_seconds or (hit.duration_minutes or 0) * 60,
                "view_count": hit.view_count,
                "like_count": hit.like_count,
                "search_score": hit.score,
            })

        has_more = (offset + len(items)) < result.total_count

        return APIResponse(
            success=True,
            data={
                "items": items,
                "total": result.total_count,
                "page": page,
                "limit": limit,
                "has_more": has_more,
                "facets": result.facets,
            },
        )
    except Exception as e:
        logger.error(f"YouTube search failed: {e}")
        # Fallback to CosmosDB if search fails
        content_service = get_youtube_content_service()
        contents = await content_service.list_published(
            limit=limit,
            offset=offset,
            category=category,
            search=q,
        )
        total = await content_service.count_published()
        items = [_to_content_response(c).model_dump() for c in contents]
        has_more = (page * limit) < total

        return APIResponse(
            success=True,
            data={
                "items": items,
                "total": total,
                "page": page,
                "limit": limit,
                "has_more": has_more,
                "facets": {},
            },
            meta=Meta.create(message="Fallback to CosmosDB due to search error"),
        )


# =============================================================================
# Content Endpoints
# =============================================================================


@router.get(
    "/contents",
    response_model=APIResponse,
    summary="List published YouTube content",
    description="Get a paginated list of published YouTube content.",
)
async def list_youtube_contents(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search term"),
):
    """List published YouTube content (public endpoint)."""
    content_service = get_youtube_content_service()

    offset = (page - 1) * limit
    contents = await content_service.list_published(
        limit=limit,
        offset=offset,
        category=category,
        search=search,
    )
    total = await content_service.count_published()

    items = [_to_content_response(c) for c in contents]
    has_more = (page * limit) < total

    response_data = YouTubeContentListResponse(
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
    "/contents/my",
    response_model=APIResponse,
    summary="List my YouTube content",
    description="Get a paginated list of YouTube content created by the current user.",
)
async def list_my_youtube_contents(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_contributor),
):
    """List YouTube content created by the current user."""
    content_service = get_youtube_content_service()

    offset = (page - 1) * limit
    contents = await content_service.list_by_contributor(
        contributor_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    items = [_to_content_response(c) for c in contents]

    return APIResponse(
        success=True,
        data={
            "items": [item.model_dump() for item in items],
            "page": page,
            "limit": limit,
        },
    )


@router.get(
    "/contents/{content_id}",
    response_model=APIResponse,
    summary="Get YouTube content details",
    description="Get detailed information about a specific YouTube content.",
)
async def get_youtube_content(
    content_id: str,
):
    """Get a specific YouTube content by ID."""
    content_service = get_youtube_content_service()

    content = await content_service.get_content(content_id)
    if not content:
        raise NotFoundError(f"YouTube content not found: {content_id}")

    return APIResponse(
        success=True,
        data=_to_content_response(content).model_dump(),
    )


@router.patch(
    "/contents/{content_id}",
    response_model=APIResponse,
    summary="Update YouTube content",
    description="Update YouTube content details.",
)
async def update_youtube_content(
    content_id: str,
    data: YouTubeContentUpdate,
    current_user: User = Depends(require_contributor),
):
    """Update YouTube content."""
    content_service = get_youtube_content_service()

    content = await content_service.get_content(content_id)
    if not content:
        raise NotFoundError(f"YouTube content not found: {content_id}")

    # Check ownership
    if content.contributor_id != current_user.id:
        raise ValidationError("You can only update your own content")

    # Update fields
    if data.title is not None:
        content.title = data.title
    if data.title_en is not None:
        content.title_en = data.title_en
    if data.title_kr is not None:
        content.title_kr = data.title_kr
    if data.description is not None:
        content.description = data.description
    if data.description_en is not None:
        content.description_en = data.description_en
    if data.description_kr is not None:
        content.description_kr = data.description_kr
    if data.script_summary_en is not None:
        content.script_summary_en = data.script_summary_en
    if data.script_summary_kr is not None:
        content.script_summary_kr = data.script_summary_kr
    if data.categories is not None:
        content.categories = data.categories
    if data.technologies is not None:
        content.technologies = data.technologies
    if data.level is not None:
        content.level = data.level

    content.contributor_update_email = current_user.email
    updated_content = await content_service.update_content(content)

    return APIResponse(
        success=True,
        data=_to_content_response(updated_content).model_dump(),
        meta=Meta.create(message="YouTube content updated"),
    )


@router.post(
    "/contents/{content_id}/publish",
    response_model=APIResponse,
    summary="Publish YouTube content",
    description="Publish YouTube content to make it publicly visible.",
)
async def publish_youtube_content(
    content_id: str,
    current_user: User = Depends(require_contributor),
):
    """Publish YouTube content."""
    content_service = get_youtube_content_service()

    content = await content_service.get_content(content_id)
    if not content:
        raise NotFoundError(f"YouTube content not found: {content_id}")

    # Check ownership
    if content.contributor_id != current_user.id:
        raise ValidationError("You can only publish your own content")

    published_content = await content_service.publish_content(
        content_id,
        contributor_email=current_user.email,
    )

    return APIResponse(
        success=True,
        data=_to_content_response(published_content).model_dump(),
        meta=Meta.create(message="YouTube content published"),
    )


@router.post(
    "/contents/{content_id}/unpublish",
    response_model=APIResponse,
    summary="Unpublish YouTube content",
    description="Unpublish YouTube content to hide it from public view.",
)
async def unpublish_youtube_content(
    content_id: str,
    current_user: User = Depends(require_contributor),
):
    """Unpublish YouTube content."""
    content_service = get_youtube_content_service()

    content = await content_service.get_content(content_id)
    if not content:
        raise NotFoundError(f"YouTube content not found: {content_id}")

    # Check ownership
    if content.contributor_id != current_user.id:
        raise ValidationError("You can only unpublish your own content")

    unpublished_content = await content_service.unpublish_content(content_id)

    return APIResponse(
        success=True,
        data=_to_content_response(unpublished_content).model_dump(),
        meta=Meta.create(message="YouTube content unpublished"),
    )


@router.delete(
    "/contents/{content_id}",
    response_model=APIResponse,
    summary="Delete YouTube content",
    description="Delete YouTube content.",
)
async def delete_youtube_content(
    content_id: str,
    current_user: User = Depends(require_contributor),
):
    """Delete YouTube content."""
    content_service = get_youtube_content_service()

    content = await content_service.get_content(content_id)
    if not content:
        raise NotFoundError(f"YouTube content not found: {content_id}")

    # Check ownership
    if content.contributor_id != current_user.id:
        raise ValidationError("You can only delete your own content")

    await content_service.delete_content(content_id)

    return APIResponse(
        success=True,
        data={"deleted": True},
        meta=Meta.create(message="YouTube content deleted"),
    )


# =============================================================================
# Script Retrieval Endpoints (Public)
# =============================================================================


class YouTubeScriptResponse(BaseModel):
    """Response schema for YouTube script retrieval."""

    video_id: str
    title: Optional[str] = None
    title_kr: Optional[str] = None
    script_original: Optional[str] = None
    script_original_kr: Optional[str] = None
    script_language: Optional[str] = None
    chapters: list[dict] = []


@router.get(
    "/script/{analysis_request_id}",
    response_model=APIResponse,
    summary="Get YouTube video script by analysis request ID",
    description="Retrieve the full script/transcript of a YouTube video using the analysis request ID.",
)
async def get_youtube_script(
    analysis_request_id: str,
):
    """
    Get the full script/transcript of a YouTube video.

    This is a public endpoint that allows retrieving scripts for search results.
    The analysis_request_id is returned in search results.

    Returns:
    - script_original: Full transcript in English (no timestamps)
    - script_original_kr: Full transcript in Korean (translated if original was English)
    - script_language: Language of the original script
    - chapters: List of video chapters
    """
    youtube_repo = get_youtube_repo()

    # Get the analysis request (contains the full script)
    request = await youtube_repo.get_by_id_no_auth(analysis_request_id)
    if not request:
        raise NotFoundError(f"Analysis request not found: {analysis_request_id}")

    if not request.result:
        raise NotFoundError("No analysis result available for this request")

    result = request.result
    script_response = YouTubeScriptResponse(
        video_id=result.video_id,
        title=result.title_en or result.title,
        title_kr=result.title_kr,
        script_original=result.script_original,
        script_original_kr=result.script_original_kr,
        script_language=result.script_language,
        chapters=[ch.to_dict() for ch in result.chapters],
    )

    return APIResponse(
        success=True,
        data=script_response.model_dump(),
    )


# =============================================================================
# Metadata Refresh Endpoints
# =============================================================================


class MetadataRefreshResponse(BaseModel):
    """Response schema for metadata refresh."""

    video_id: str
    view_count: int
    like_count: int
    comment_count: int
    duration_seconds: int
    updated_sources: list[str]  # ["youtube_analysis", "youtube_contents", "search_index"]


@router.post(
    "/refresh/{content_id}",
    response_model=APIResponse,
    summary="Refresh YouTube video metadata",
    description="Fetch latest view count, like count, and other metrics from YouTube and update all data stores.",
)
async def refresh_youtube_metadata(
    content_id: str,
    current_user: User = Depends(require_contributor),
):
    """
    Refresh YouTube video metadata (view_count, like_count, etc.).

    Updates in order:
    1. youtube_analysis container
    2. youtube_contents container
    3. Azure AI Search index

    Only the video owner can refresh metadata.
    """
    content_service = get_youtube_content_service()
    youtube_service = get_youtube_service()
    youtube_repo = get_youtube_repo()
    search_service = get_youtube_search_service()

    # Get the content
    content = await content_service.get_content(content_id)
    if not content:
        raise NotFoundError(f"YouTube content not found: {content_id}")

    # Check ownership
    if content.contributor_id != current_user.id:
        raise ValidationError("You can only refresh your own content")

    updated_sources = []

    try:
        # Fetch latest metadata from YouTube API
        video_info = await youtube_service.fetch_video_info(content.source_url)

        # 1. Update youtube_analysis container
        if content.analysis_request_id:
            analysis_request = await youtube_repo.get_by_id_no_auth(content.analysis_request_id)
            if analysis_request and analysis_request.result:
                analysis_request.result.view_count = video_info.view_count
                analysis_request.result.like_count = video_info.like_count
                analysis_request.result.comment_count = video_info.comment_count
                analysis_request.result.duration_seconds = video_info.duration_seconds
                await youtube_repo.update(analysis_request)
                updated_sources.append("youtube_analysis")
                logger.info(f"Updated youtube_analysis for {content_id}")

        # 2. Update youtube_contents container
        content.view_count = video_info.view_count
        content.like_count = video_info.like_count
        content.comment_count = video_info.comment_count
        content.duration_seconds = video_info.duration_seconds
        content.duration_minutes = video_info.duration_seconds // 60
        await content_service.update_content(content)
        updated_sources.append("youtube_contents")
        logger.info(f"Updated youtube_contents for {content_id}")

        # 3. Update Azure AI Search index (if content is published)
        if content.status.value == "published":
            await search_service.index_content(content)
            updated_sources.append("search_index")
            logger.info(f"Updated search index for {content_id}")

        response_data = MetadataRefreshResponse(
            video_id=content.video_id,
            view_count=video_info.view_count,
            like_count=video_info.like_count,
            comment_count=video_info.comment_count,
            duration_seconds=video_info.duration_seconds,
            updated_sources=updated_sources,
        )

        return APIResponse(
            success=True,
            data=response_data.model_dump(),
            meta=Meta.create(message=f"Metadata refreshed from YouTube ({len(updated_sources)} sources updated)"),
        )

    except Exception as e:
        logger.error(f"Failed to refresh metadata for {content_id}: {e}")
        raise ValidationError(f"Failed to refresh metadata: {str(e)}")


@router.post(
    "/requests/{request_id}/refresh",
    response_model=APIResponse,
    summary="Refresh YouTube video metadata for an analysis request",
    description="Fetch latest metrics from YouTube and update the analysis request result.",
)
async def refresh_request_metadata(
    request_id: str,
    current_user: User = Depends(require_contributor),
):
    """
    Refresh YouTube video metadata for an analysis request.

    This updates the result data in youtube_analysis container.
    If content was created from this request, it also updates youtube_contents and search index.
    """
    youtube_service = get_youtube_service()
    youtube_repo = get_youtube_repo()
    content_service = get_youtube_content_service()
    search_service = get_youtube_search_service()

    # Get the analysis request
    request = await youtube_repo.get_by_id(request_id, current_user.id)
    if not request:
        raise NotFoundError(f"Analysis request not found: {request_id}")

    if not request.result:
        raise ValidationError("No analysis result available to refresh")

    updated_sources = []

    try:
        # Fetch latest metadata from YouTube API
        video_info = await youtube_service.fetch_video_info(request.source_url)

        # 1. Update youtube_analysis container
        request.result.view_count = video_info.view_count
        request.result.like_count = video_info.like_count
        request.result.comment_count = video_info.comment_count
        request.result.duration_seconds = video_info.duration_seconds
        await youtube_repo.update(request)
        updated_sources.append("youtube_analysis")

        # 2. Update youtube_contents if exists
        if request.content_ids:
            for content_id in request.content_ids:
                content = await content_service.get_content(content_id)
                if content:
                    content.view_count = video_info.view_count
                    content.like_count = video_info.like_count
                    content.comment_count = video_info.comment_count
                    content.duration_seconds = video_info.duration_seconds
                    content.duration_minutes = video_info.duration_seconds // 60
                    await content_service.update_content(content)
                    updated_sources.append("youtube_contents")

                    # 3. Update search index if published
                    if content.status.value == "published":
                        await search_service.index_content(content)
                        updated_sources.append("search_index")

        response_data = MetadataRefreshResponse(
            video_id=request.video_id,
            view_count=video_info.view_count,
            like_count=video_info.like_count,
            comment_count=video_info.comment_count,
            duration_seconds=video_info.duration_seconds,
            updated_sources=list(set(updated_sources)),  # Remove duplicates
        )

        return APIResponse(
            success=True,
            data=response_data.model_dump(),
            meta=Meta.create(message=f"Metadata refreshed ({len(set(updated_sources))} sources updated)"),
        )

    except Exception as e:
        logger.error(f"Failed to refresh metadata for request {request_id}: {e}")
        raise ValidationError(f"Failed to refresh metadata: {str(e)}")
