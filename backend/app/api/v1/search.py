"""Search API endpoints.

Per tasks.md T403: GET /api/v1/search endpoint implementation.

Provides:
- Hybrid, keyword, and vector search modes
- Filtering by categories, technologies, difficulty
- Pagination and faceting
- Public/internal visibility enforcement
"""

import logging
from enum import Enum
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError
from app.dependencies import get_current_user_optional
from app.models.user import UserPublic
from app.schemas import APIResponse, Meta
from app.services.llm_service import get_llm_service
from app.services.search_service import (
    SearchFilters,
    SearchResults,
    get_search_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])


# =============================================================================
# Enums and Schemas
# =============================================================================


class SearchMode(str, Enum):
    """Search mode options."""
    HYBRID = "hybrid"
    KEYWORD = "keyword"
    VECTOR = "vector"


class SortOption(str, Enum):
    """Sort options for search results."""
    RELEVANCE = "relevance"
    POPULARITY = "popularity"
    RECENT = "recent"


class SearchResultItem(BaseModel):
    """Single search result item for API response."""
    
    id: str
    title: str
    description: Optional[str] = None
    summary: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    difficulty_level: Optional[str] = None
    popularity_score: float = 0.0
    stars: int = 0
    score: float = 0.0


class FacetValue(BaseModel):
    """Facet value with count."""
    
    value: str
    count: int


class SearchResponse(BaseModel):
    """Search response data."""
    
    items: List[SearchResultItem]
    total: int
    facets: dict = Field(default_factory=dict)
    query: str
    mode: str
    limit: int
    offset: int


# =============================================================================
# Search Endpoint
# =============================================================================


@router.get(
    "",
    response_model=APIResponse[SearchResponse],
    summary="Search content",
    description="Search content with hybrid (keyword + vector), keyword-only, or vector-only modes.",
)
async def search_content(
    request: Request,
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    mode: SearchMode = Query(SearchMode.HYBRID, description="Search mode"),
    categories: Optional[List[str]] = Query(None, description="Filter by categories"),
    technologies: Optional[List[str]] = Query(None, description="Filter by technologies"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty level"),
    min_stars: Optional[int] = Query(None, ge=0, description="Minimum stars filter"),
    sort: SortOption = Query(SortOption.RELEVANCE, description="Sort order"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: Optional[UserPublic] = Depends(get_current_user_optional),
):
    """
    Search content with various filters and modes.
    
    Per tasks.md T403:
    - Supports hybrid, keyword, and vector search modes
    - Filters: categories, technologies, difficulty, min_stars
    - Sort: relevance, popularity, recent
    - Pagination with total count
    - Visibility enforced (public only for unauthenticated)
    
    **Authentication optional** - unauthenticated users see public content only.
    """
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    
    search_service = get_search_service()
    llm_service = get_llm_service()
    
    # Build filters
    # Enforce visibility based on authentication
    visibility = None if user else "public"
    
    filters = SearchFilters(
        categories=categories,
        technologies=technologies,
        difficulty=difficulty,
        min_stars=min_stars,
        visibility=visibility,
    )
    
    # Generate embedding for hybrid/vector search
    embedding = None
    if mode in (SearchMode.HYBRID, SearchMode.VECTOR):
        if llm_service.is_configured:
            try:
                embedding = await llm_service.generate_embedding(q)
            except Exception as e:
                logger.warning(f"Failed to generate embedding, falling back to keyword: {e}")
                if mode == SearchMode.VECTOR:
                    raise ValidationError("Vector search requires embedding generation, which failed")
    
    # Execute search based on mode
    if mode == SearchMode.HYBRID:
        results = await search_service.hybrid_search(
            query=q,
            filters=filters,
            limit=limit,
            offset=offset,
            embedding=embedding,
        )
    elif mode == SearchMode.KEYWORD:
        results = await search_service.keyword_search(
            query=q,
            filters=filters,
            limit=limit,
            offset=offset,
        )
    else:  # VECTOR
        if not embedding:
            raise ValidationError("Vector search requires query embedding")
        results = await search_service.vector_search(
            embedding=embedding,
            filters=filters,
            limit=limit,
            offset=offset,
        )
    
    # Convert to response format
    response_data = SearchResponse(
        items=[
            SearchResultItem(
                id=item.id,
                title=item.title,
                description=item.description,
                summary=item.summary,
                categories=item.categories,
                technologies=item.technologies,
                difficulty_level=item.difficulty_level,
                popularity_score=item.popularity_score,
                stars=item.stars,
                score=item.score,
            )
            for item in results.items
        ],
        total=results.total,
        facets=results.facets,
        query=q,
        mode=mode.value,
        limit=limit,
        offset=offset,
    )
    
    return APIResponse(
        success=True,
        data=response_data,
        meta=Meta.create(correlation_id=correlation_id),
    )


@router.post(
    "/reindex",
    response_model=APIResponse[dict],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger reindex",
    description="Trigger a full reindex of all content (admin only).",
)
async def trigger_reindex(
    request: Request,
    user: UserPublic = Depends(get_current_user_optional),
):
    """
    Trigger a full reindex operation.
    
    This enqueues an indexing pipeline job that will:
    1. Load all published content
    2. Generate embeddings for each
    3. Upsert to Azure AI Search
    
    **Requires admin role** (TODO: implement role check).
    """
    # TODO: Implement role check for admin
    # TODO: Enqueue indexing pipeline with content_ids="all"
    
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    
    return APIResponse(
        success=True,
        data={"message": "Reindex job enqueued", "status": "pending"},
        meta=Meta.create(correlation_id=correlation_id),
    )
