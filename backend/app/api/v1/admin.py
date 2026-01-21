"""Admin API endpoints.

Per tasks.md T805: Dev → Prod promotion workflow.

Provides:
- Content promotion from Dev to Prod
- Promotion validation
- Bulk promotion
- Admin-only access controls
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import get_current_user_required
from app.models.user import UserPublic
from app.schemas import APIResponse, Meta
from app.services.promotion_service import (
    PromotionService,
    PromotionError,
    PromotionConfigError,
    PromotionValidationError,
    get_promotion_service,
)
from app.repositories import get_content_repo

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class PromoteContentRequest(BaseModel):
    """Request to promote a single content item."""
    
    content_id: str = Field(..., description="Content ID to promote")
    force: bool = Field(
        False,
        description="Force promotion even if validation fails",
    )


class BulkPromoteRequest(BaseModel):
    """Request to promote multiple content items."""
    
    content_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Content IDs to promote",
    )
    force: bool = Field(
        False,
        description="Force promotion even if validation fails",
    )


class ValidationError(BaseModel):
    """Validation error detail."""
    
    field: str
    message: str


class ValidationResultResponse(BaseModel):
    """Validation result for promotion."""
    
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class PromotionResultResponse(BaseModel):
    """Result of content promotion."""
    
    success: bool
    content_id: str
    prod_content_id: Optional[str] = None
    promoted_at: str
    assets_copied: int = 0
    indexed: bool = False
    errors: List[str] = Field(default_factory=list)


class BulkPromotionResultResponse(BaseModel):
    """Result of bulk promotion."""
    
    total: int
    successful: int
    failed: int
    results: List[PromotionResultResponse]


# =============================================================================
# Dependencies
# =============================================================================


async def get_promotion() -> PromotionService:
    """Get promotion service dependency."""
    return get_promotion_service()


def require_admin(user: UserPublic) -> UserPublic:
    """Verify user has admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for this operation",
        )
    return user


# =============================================================================
# Validation Endpoints
# =============================================================================


@router.post(
    "/promotion/validate/{content_id}",
    response_model=APIResponse[ValidationResultResponse],
    status_code=status.HTTP_200_OK,
    summary="Validate content for promotion",
    description="""
    Validate that a content item is ready for promotion to Production.
    
    Checks:
    - Content status (must be PUBLISHED or APPROVED)
    - Enrichment completed
    - Required fields present
    - Recommended fields (warnings only)
    
    **Admin access required.**
    """,
)
async def validate_content_for_promotion(
    content_id: str,
    user: UserPublic = Depends(get_current_user_required),
    promotion: PromotionService = Depends(get_promotion),
) -> APIResponse[ValidationResultResponse]:
    """Validate content for promotion."""
    
    require_admin(user)
    
    # Get content
    content_repo = get_content_repo()
    content = await content_repo.get_by_id(content_id)
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )
    
    # Validate
    result = await promotion.validate_content(content)
    
    return APIResponse(
        success=True,
        data=ValidationResultResponse(
            is_valid=result.is_valid,
            errors=result.errors,
            warnings=result.warnings,
        ),
        meta=Meta(request_id=""),
    )


# =============================================================================
# Promotion Endpoints
# =============================================================================


@router.post(
    "/promotion/promote",
    response_model=APIResponse[PromotionResultResponse],
    status_code=status.HTTP_200_OK,
    summary="Promote content to Production",
    description="""
    Promote a single content item from Dev to Production.
    
    Steps:
    1. Validate content (unless force=true)
    2. Copy content to Prod Cosmos DB
    3. Copy assets to Prod Blob Storage
    4. Trigger indexing in Prod Search
    
    **Admin access required.**
    """,
    responses={
        403: {"description": "Admin access required"},
        404: {"description": "Content not found"},
        422: {"description": "Content validation failed"},
        503: {"description": "Promotion service not configured"},
    },
)
async def promote_content(
    request: PromoteContentRequest,
    user: UserPublic = Depends(get_current_user_required),
    promotion: PromotionService = Depends(get_promotion),
) -> APIResponse[PromotionResultResponse]:
    """Promote content to Production."""
    
    require_admin(user)
    
    if not promotion.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Promotion service is not configured. Prod credentials required.",
        )
    
    try:
        result = await promotion.promote_content(
            content_id=request.content_id,
            force=request.force,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Content promotion failed",
                    "errors": result.errors,
                },
            )
        
        return APIResponse(
            success=True,
            data=PromotionResultResponse(
                success=result.success,
                content_id=result.content_id,
                prod_content_id=result.prod_content_id,
                promoted_at=result.promoted_at.isoformat(),
                assets_copied=result.assets_copied,
                indexed=result.indexed,
                errors=result.errors,
            ),
            meta=Meta(request_id=""),
        )
        
    except PromotionConfigError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except PromotionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/promotion/promote-bulk",
    response_model=APIResponse[BulkPromotionResultResponse],
    status_code=status.HTTP_200_OK,
    summary="Bulk promote content to Production",
    description="""
    Promote multiple content items from Dev to Production.
    
    Each content item is processed independently. Failed items do not
    prevent other items from being promoted.
    
    **Admin access required.**
    """,
)
async def promote_content_bulk(
    request: BulkPromoteRequest,
    user: UserPublic = Depends(get_current_user_required),
    promotion: PromotionService = Depends(get_promotion),
) -> APIResponse[BulkPromotionResultResponse]:
    """Bulk promote content to Production."""
    
    require_admin(user)
    
    if not promotion.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Promotion service is not configured. Prod credentials required.",
        )
    
    try:
        result = await promotion.promote_bulk(
            content_ids=request.content_ids,
            force=request.force,
        )
        
        return APIResponse(
            success=True,
            data=BulkPromotionResultResponse(
                total=result.total,
                successful=result.successful,
                failed=result.failed,
                results=[
                    PromotionResultResponse(
                        success=r.success,
                        content_id=r.content_id,
                        prod_content_id=r.prod_content_id,
                        promoted_at=r.promoted_at.isoformat(),
                        assets_copied=r.assets_copied,
                        indexed=r.indexed,
                        errors=r.errors,
                    )
                    for r in result.results
                ],
            ),
            meta=Meta(request_id=""),
        )
        
    except PromotionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# =============================================================================
# Content Listing for Promotion
# =============================================================================


class PromotableContentItem(BaseModel):
    """Content item ready for promotion."""
    
    id: str
    title: str
    status: str
    enrichment_version: Optional[int] = None
    last_enriched_at: Optional[str] = None
    has_localization: bool = False
    validation_status: Optional[str] = None  # valid, has_warnings, has_errors


class PromotableContentListResponse(BaseModel):
    """List of content ready for promotion."""
    
    items: List[PromotableContentItem]
    total: int


@router.get(
    "/promotion/candidates",
    response_model=APIResponse[PromotableContentListResponse],
    status_code=status.HTTP_200_OK,
    summary="List content candidates for promotion",
    description="""
    List all content items that are candidates for promotion to Production.
    
    Returns content that is:
    - Published or Approved status
    - Has been enriched
    
    Each item includes validation status (valid, has_warnings, has_errors).
    
    **Admin access required.**
    """,
)
async def list_promotable_content(
    limit: int = 50,
    offset: int = 0,
    user: UserPublic = Depends(get_current_user_required),
    promotion: PromotionService = Depends(get_promotion),
) -> APIResponse[PromotableContentListResponse]:
    """List content candidates for promotion."""
    
    require_admin(user)
    
    content_repo = get_content_repo()
    
    # Get published/approved content
    # This is a simplified query - in production would use proper filtering
    all_content = await content_repo.get_all(limit=limit, offset=offset)
    
    promotable_items: List[PromotableContentItem] = []
    
    for content in all_content:
        # Check if eligible for promotion
        if content.status.value not in ["published", "approved"]:
            continue
        if not content.enrichment_version:
            continue
        
        # Validate
        validation = await promotion.validate_content(content)
        
        if validation.is_valid:
            validation_status = "valid"
        elif validation.warnings and not validation.errors:
            validation_status = "has_warnings"
        else:
            validation_status = "has_errors"
        
        promotable_items.append(PromotableContentItem(
            id=content.id,
            title=content.title,
            status=content.status.value,
            enrichment_version=content.enrichment_version,
            last_enriched_at=content.last_enriched_at.isoformat() if content.last_enriched_at else None,
            has_localization=bool(content.title_kr),
            validation_status=validation_status,
        ))
    
    return APIResponse(
        success=True,
        data=PromotableContentListResponse(
            items=promotable_items,
            total=len(promotable_items),
        ),
        meta=Meta(request_id=""),
    )
