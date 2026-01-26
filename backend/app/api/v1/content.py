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
from app.services.search_service import get_search_service

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
        # Resource links
        video_url=getattr(c, 'video_url', None),
        docs_url=getattr(c, 'docs_url', None),
        pptx_url=getattr(c, 'pptx_url', None),
        # Analysis request reference
        analysis_request_id=getattr(c, 'analysis_request_id', None),
    )


@router.get(
    "/my",
    response_model=APIResponse,
    summary="List my content",
    description="Get paginated list of contributor's own content (all statuses)",
)
async def list_my_content(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (draft, published, archived)"),
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    List current user's content with pagination (all statuses).

    - Requires contributor role
    - Returns all content owned by the current user
    - **page**: Page number (1-indexed)
    - **limit**: Items per page (max 100)
    - **status**: Optional status filter
    """
    service = get_content_service()
    result = await service.list_by_contributor(
        contributor_id=current_user.id,
        page=page,
        limit=limit,
        status=status,
    )

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=result.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


@router.get(
    "/all",
    response_model=APIResponse,
    summary="List all content",
    description="Get paginated list of all content items (all statuses, all contributors)",
)
async def list_all_content(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (draft, published, archived)"),
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    List all content with pagination (all statuses, all contributors).

    - Requires contributor role
    - Returns all content from all contributors
    - **page**: Page number (1-indexed)
    - **limit**: Items per page (max 100)
    - **status**: Optional status filter
    """
    service = get_content_service()
    result = await service.list_all(
        page=page,
        limit=limit,
        status=status,
    )

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=result.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


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
    - All contributors can update any content (internal employees)
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

    # All contributors can edit content (internal employees)

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
    - All contributors can change status (internal employees)
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

    # All contributors can change status (internal employees)

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


@router.post(
    "/{content_id}/sync-from-analysis",
    response_model=APIResponse,
    summary="Sync content from analysis request",
    description="Update content fields from the linked analysis request result",
)
async def sync_from_analysis(
    request: Request,
    content_id: str,
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    Sync content fields from the linked analysis request.

    - Requires contributor role
    - All contributors can sync (internal employees)
    - Updates content with latest data from analysis_request.result
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

    # All contributors can sync content (internal employees)

    # Check if content has linked analysis_request_id
    if not content.analysis_request_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content has no linked analysis request",
        )

    # Perform sync
    updated = await service.sync_from_analysis(content_id)

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync from analysis request",
        )

    content_response = _content_to_response(updated)

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data=content_response.model_dump(mode="json"),
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


@router.delete(
    "/{content_id}/permanent",
    response_model=APIResponse,
    summary="Permanently delete content and linked analysis request",
    description="Hard delete content and its linked analysis request from the database",
)
async def permanent_delete_content(
    request: Request,
    content_id: str,
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    Permanently delete content and linked analysis request.

    - Requires contributor role
    - Only the content owner or bypass user can permanently delete
    - This is a HARD delete - content will be permanently removed
    - Also deletes the linked analysis_request if exists
    - **content_id**: Content unique identifier
    """
    from app.config import get_settings
    from app.repositories.analysis_repo import get_analysis_repo

    settings = get_settings()
    service = get_content_service()

    # Get existing content
    content = await service.get_by_id(content_id)

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )

    # Check ownership or bypass permission for permanent delete
    is_owner = content.contributor_id == current_user.id
    is_bypass = (
        settings.dev_bypass_email
        and current_user.email.lower() == settings.dev_bypass_email.lower()
    )

    if not is_owner and not is_bypass:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the content owner or authorized users can permanently delete content",
        )

    # Delete linked analysis_request first (if any)
    deleted_analysis = False
    if content.analysis_request_id:
        analysis_repo = get_analysis_repo()
        # Use delete_by_id since we already verified content ownership
        deleted_analysis = await analysis_repo.delete_by_id(
            request_id=content.analysis_request_id,
        )

    # Delete thumbnail from blob storage if exists
    thumbnail_deleted = False
    if content.thumbnail_url:
        try:
            from app.services.storage_service import REPO_IMAGES_CONTAINER, StorageService
            storage_service = StorageService()
            # Blob path format: {content_id}/thumbnail.png
            blob_path = f"{content_id}/thumbnail.png"
            await storage_service.delete_blob(REPO_IMAGES_CONTAINER, blob_path)
            thumbnail_deleted = True
            logger.info(f"Deleted thumbnail for content: {content_id}")
        except Exception as e:
            logger.warning(f"Failed to delete thumbnail for {content_id}: {e}")

    # Delete from AI Search index
    search_deleted = False
    try:
        search_service = get_search_service()
        if search_service.is_configured:
            await search_service.delete_document(content_id)
            search_deleted = True
            logger.info(f"Deleted content {content_id} from search index")
    except Exception as e:
        logger.warning(f"Failed to delete {content_id} from search index: {e}")

    # Hard delete the content using cross-partition delete
    try:
        deleted_content = await service.repo.delete_cross_partition(
            content_id=content_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete content: {str(e)}",
        )

    if not deleted_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content not found or already deleted (id={content_id}, contributor={content.contributor_id})",
        )

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data={
            "message": "Content permanently deleted",
            "content_deleted": deleted_content,
            "analysis_request_deleted": deleted_analysis,
            "thumbnail_deleted": thumbnail_deleted,
            "search_index_deleted": search_deleted,
        },
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
    - All contributors can archive content (internal employees)
    - This is a soft delete (status → archived), not a hard delete
    - Also removes the content ID from the linked analysis request
    - **content_id**: Content unique identifier
    """
    from app.repositories.analysis_repo import get_analysis_repo

    service = get_content_service()

    # Get existing content
    content = await service.get_by_id(content_id)

    if content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )

    # All contributors can archive content (internal employees)

    # Soft delete (archive)
    await service.update_status(content_id, "archived")

    # Remove content_id from linked analysis_request (if any)
    if content.analysis_request_id:
        analysis_repo = get_analysis_repo()
        await analysis_repo.remove_content_id(
            request_id=content.analysis_request_id,
            user_id=current_user.id,
            content_id=content_id,
        )

    correlation_id = getattr(request.state, "correlation_id", "")

    response = APIResponse(
        success=True,
        data={"message": "Content deleted (archived) successfully"},
        meta=Meta.create(correlation_id),
    )

    return JSONResponse(content=response.model_dump(mode="json"))


@router.post(
    "/{content_id}/regenerate-thumbnail",
    response_model=APIResponse,
    summary="Regenerate thumbnail image",
    description="Regenerate AI-generated thumbnail for content using DALL-E",
)
async def regenerate_thumbnail(
    request: Request,
    content_id: str,
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    Regenerate thumbnail image for content.

    - Requires contributor role
    - Uses DALL-E to generate a new professional thumbnail
    - Uploads to Azure Storage and updates content.thumbnail_url
    """
    from app.services.image_generation_service import (
        ImageGenerationError,
        get_image_generation_service,
    )

    service = get_content_service()
    correlation_id = getattr(request.state, "correlation_id", "")

    try:
        # Get content
        content = await service.get_by_id(content_id)
        if content is None:
            return JSONResponse(
                status_code=404,
                content=APIResponse(
                    success=False,
                    error={"code": "NOT_FOUND", "message": "Content not found"},
                    meta=Meta.create(correlation_id),
                ).model_dump(mode="json"),
            )

        # Generate thumbnail
        image_service = get_image_generation_service()

        thumbnail_url = await image_service.generate_and_upload_thumbnail(
            content_id=content_id,
            title=content.title,
            description=content.description,
            technologies=content.technologies or [],
            categories=content.categories or [],
        )

        # Update content with new thumbnail URL
        update_data = ContentUpdateRequest(thumbnail_url=thumbnail_url)
        updated_content = await service.update(content_id, update_data)

        response = APIResponse(
            success=True,
            data={
                "content_id": content_id,
                "thumbnail_url": thumbnail_url,
                "message": "Thumbnail regenerated successfully",
            },
            meta=Meta.create(correlation_id),
        )
        return JSONResponse(content=response.model_dump(mode="json"))

    except ImageGenerationError as e:
        logger.error(f"Thumbnail regeneration failed: {e}")
        return JSONResponse(
            status_code=500,
            content=APIResponse(
                success=False,
                error={"code": "IMAGE_GENERATION_ERROR", "message": str(e)},
                meta=Meta.create(correlation_id),
            ).model_dump(mode="json"),
        )
    except Exception as e:
        logger.error(f"Unexpected error regenerating thumbnail: {e}")
        return JSONResponse(
            status_code=500,
            content=APIResponse(
                success=False,
                error={"code": "INTERNAL_ERROR", "message": "Failed to regenerate thumbnail"},
                meta=Meta.create(correlation_id),
            ).model_dump(mode="json"),
        )


@router.post(
    "/{content_id}/refresh-repo",
    response_model=APIResponse,
    summary="Refresh repository metadata",
    description="Refresh stars, forks, and last_commit_date from GitHub",
)
async def refresh_repo_metadata(
    request: Request,
    content_id: str,
    current_user: UserPublic = Depends(require_contributor),
) -> JSONResponse:
    """
    Refresh repository metadata from GitHub.

    - Requires contributor role
    - Fetches latest stars, forks, last_commit_date from GitHub
    - Updates content document with fresh data
    """
    from datetime import datetime

    from app.services.github_service import GitHubError, get_github_service

    service = get_content_service()
    correlation_id = getattr(request.state, "correlation_id", "")

    try:
        # Get content
        content = await service.get_by_id(content_id)
        if content is None:
            return JSONResponse(
                status_code=404,
                content=APIResponse(
                    success=False,
                    error={"code": "NOT_FOUND", "message": "Content not found"},
                    meta=Meta.create(correlation_id),
                ).model_dump(mode="json"),
            )

        # Check if source_url exists
        if not content.source_url:
            return JSONResponse(
                status_code=400,
                content=APIResponse(
                    success=False,
                    error={"code": "NO_SOURCE_URL", "message": "Content has no source URL"},
                    meta=Meta.create(correlation_id),
                ).model_dump(mode="json"),
            )

        # Fetch latest repo info from GitHub
        github_service = get_github_service()
        owner, repo = github_service.parse_github_url(content.source_url)
        repo_info = await github_service.fetch_repo_info(owner, repo)

        # Parse last_commit_date from pushed_at
        last_commit_date = None
        if repo_info.pushed_at:
            last_commit_date = datetime.fromisoformat(
                repo_info.pushed_at.replace("Z", "+00:00")
            )

        # Update content with new metadata
        update_data = ContentUpdateRequest(
            stars=repo_info.stars,
            forks=repo_info.forks,
            last_commit_date=last_commit_date,
        )
        updated_content = await service.update(content_id, update_data)

        response = APIResponse(
            success=True,
            data={
                "content_id": content_id,
                "stars": repo_info.stars,
                "forks": repo_info.forks,
                "last_commit_date": last_commit_date.isoformat() if last_commit_date else None,
                "message": "Repository metadata refreshed successfully",
            },
            meta=Meta.create(correlation_id),
        )
        return JSONResponse(content=response.model_dump(mode="json"))

    except GitHubError as e:
        logger.error(f"GitHub API error refreshing repo metadata: {e}")
        return JSONResponse(
            status_code=502,
            content=APIResponse(
                success=False,
                error={"code": "GITHUB_ERROR", "message": str(e)},
                meta=Meta.create(correlation_id),
            ).model_dump(mode="json"),
        )
    except Exception as e:
        logger.error(f"Unexpected error refreshing repo metadata: {e}")
        return JSONResponse(
            status_code=500,
            content=APIResponse(
                success=False,
                error={"code": "INTERNAL_ERROR", "message": "Failed to refresh repository metadata"},
                meta=Meta.create(correlation_id),
            ).model_dump(mode="json"),
        )
