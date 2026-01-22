"""Content API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.dependencies import require_contributor
from app.models.content import Content
from app.models.enums import ContentType
from app.models.user import UserPublic
from app.schemas import APIResponse, Meta
from app.schemas.content import (
    ContentCreateRequest,
    ContentResponse,
    ContentUpdateRequest,
)
from app.services.content_service import get_content_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])


def _content_to_response(c: Content) -> ContentResponse:
    """Convert Content model to ContentResponse with bilingual fields."""
    return ContentResponse(
        id=c.id,
        title=c.title,
        description=c.description,
        content_type=c.content_type.value if isinstance(c.content_type, ContentType) else c.content_type,
        categories=c.categories,
        level=c.level,
        duration_minutes=c.duration_minutes,
        thumbnail_url=c.thumbnail_url,
        icon=c.icon,
        source_url=c.source_url,
        view_count=c.view_count,
        bookmark_count=c.bookmark_count,
        published_at=c.published_at,
        # Bilingual fields (T502)
        title_kr=getattr(c, 'title_kr', None),
        description_kr=getattr(c, 'description_kr', None),
        summary_short=getattr(c, 'summary_short', None),
        summary_kr=getattr(c, 'summary_kr', None),
        prerequisites=getattr(c, 'prerequisites', []) or [],
        prerequisites_kr=getattr(c, 'prerequisites_kr', []) or [],
        learning_outcomes=getattr(c, 'learning_outcomes', []) or [],
        learning_outcomes_kr=getattr(c, 'learning_outcomes_kr', []) or [],
        difficulty_level=getattr(c, 'difficulty_level', None),
    )


@router.get(
    "",
    response_model=APIResponse,
    summary="List published content",
    description="Get paginated list of published content items",
)
async def list_content(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Filter by category"),
) -> JSONResponse:
    """
    List published content with pagination.

    - **page**: Page number (1-indexed)
    - **limit**: Items per page (max 100)
    - **category**: Optional category filter
    """
    service = get_content_service()
    result = await service.list_published(
        page=page,
        limit=limit,
        category=category,
    )

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=result.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


@router.get(
    "/search",
    response_model=APIResponse,
    summary="Search content",
    description="Search content by text query",
)
async def search_content(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
) -> JSONResponse:
    """
    Search content by text.

    - **q**: Search query (searches title, description, categories)
    - **page**: Page number (1-indexed)
    - **limit**: Items per page (max 100)
    """
    service = get_content_service()
    result = await service.search(
        query=q,
        page=page,
        limit=limit,
    )

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=result.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


@router.get(
    "/{content_id}",
    response_model=APIResponse,
    summary="Get content by ID",
    description="Get a single content item by its ID",
)
async def get_content(
    request: Request,
    content_id: str,
) -> JSONResponse:
    """
    Get content by ID.

    - **content_id**: Content unique identifier
    """
    service = get_content_service()
    content = await service.get_by_id(content_id)

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )

    # Convert to response model
    content_response = _content_to_response(content)

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=content_response.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


@router.post(
    "",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new content",
    description="Create new content item (contributor only)",
)
async def create_content(
    request: Request,
    body: ContentCreateRequest,
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    Create a new content item.

    - Requires contributor role
    - Content is created with draft status
    - Content is associated with the current user as contributor
    """
    service = get_content_service()

    content = await service.create(
        contributor_id=current_user.id,
        data=body,
    )

    content_response = _content_to_response(content)

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=content_response.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(
        content=response.model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
    )


@router.put(
    "/{content_id}",
    response_model=APIResponse,
    summary="Update content",
    description="Update content item (owner only)",
)
async def update_content(
    request: Request,
    content_id: str,
    body: ContentUpdateRequest,
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    Update an existing content item.

    - Requires contributor role
    - Only the content owner can update
    - **content_id**: Content unique identifier
    """
    service = get_content_service()

    # Get existing content
    content = await service.get_by_id(content_id)

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )

    # Check ownership
    if content.contributor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own content",
        )

    # Update content
    updated = await service.update(content_id, body)

    content_response = _content_to_response(updated)

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=content_response.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


class StatusUpdateRequest(BaseModel):
    """Request schema for status update."""
    status: str = Field(..., description="New status: 'published' or 'archived'")


@router.patch(
    "/{content_id}/status",
    response_model=APIResponse,
    summary="Update content status",
    description="Change content status (publish or archive)",
)
async def update_content_status(
    request: Request,
    content_id: str,
    body: StatusUpdateRequest,
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    Update content status (publish/archive).

    - Requires contributor role
    - Only the content owner can change status
    - Valid transitions: draft → published, published → archived
    - **content_id**: Content unique identifier
    - **status**: 'published' or 'archived'
    """
    service = get_content_service()

    # Validate status value
    valid_statuses = ["published", "archived"]
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
        )

    # Get existing content
    content = await service.get_by_id(content_id)

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )

    # Check ownership
    if content.contributor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update status of your own content",
        )

    # Update status
    updated = await service.update_status(content_id, body.status)

    content_response = _content_to_response(updated)

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=content_response.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


@router.delete(
    "/{content_id}",
    response_model=APIResponse,
    summary="Delete content (soft delete)",
    description="Soft delete content by setting status to archived",
)
async def delete_content(
    request: Request,
    content_id: str,
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    Soft delete content (set status to archived).

    - Requires contributor role
    - Only the content owner can delete
    - This is a soft delete (status → archived), not a hard delete
    - **content_id**: Content unique identifier
    """
    service = get_content_service()

    # Get existing content
    content = await service.get_by_id(content_id)

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )

    # Check ownership
    if content.contributor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own content",
        )

    # Soft delete (archive)
    await service.update_status(content_id, "archived")

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data={"message": "Content deleted (archived) successfully"},
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))
