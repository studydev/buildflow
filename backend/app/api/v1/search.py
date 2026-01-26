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

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError
from app.dependencies import get_current_user_optional
from app.models.user import UserPublic
from app.schemas import APIResponse, Meta
from app.services.llm_service import get_llm_service
from app.services.search_service import (
    SearchFilters,
    get_search_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Search"])


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
    STARS = "stars"


class SortOrder(str, Enum):
    """Sort order direction."""
    DESC = "desc"
    ASC = "asc"


class SearchResultItem(BaseModel):
    """Single search result item for API response."""

    id: str
    title: str
    title_kr: Optional[str] = None
    description: Optional[str] = None
    description_kr: Optional[str] = None
    summary: Optional[str] = None
    summary_kr: Optional[str] = None
    summary_short: Optional[str] = None  # Alias for frontend compatibility
    categories: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    difficulty_level: Optional[str] = None
    level: Optional[str] = None  # Alias for frontend compatibility
    popularity_score: float = 0.0
    stars: int = 0
    score: float = 0.0
    # UI display fields
    source_url: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    icon: Optional[str] = None
    duration_minutes: Optional[int] = None
    view_count: int = 0
    last_commit_date: Optional[str] = None
    learning_outcomes: List[str] = Field(default_factory=list)
    learning_outcomes_kr: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    prerequisites_kr: List[str] = Field(default_factory=list)


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
    q: str = Query("", max_length=500, description="Search query (empty for all content)"),
    mode: SearchMode = Query(SearchMode.HYBRID, description="Search mode"),
    categories: Optional[List[str]] = Query(None, description="Filter by categories"),
    technologies: Optional[List[str]] = Query(None, description="Filter by technologies"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty level"),
    min_stars: Optional[int] = Query(None, ge=0, description="Minimum stars filter"),
    sort: SortOption = Query(SortOption.RELEVANCE, description="Sort field"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order (asc or desc)"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user: Optional[UserPublic] = Depends(get_current_user_optional),
):
    """
    Search content with various filters and modes.

    Empty query returns all content (equivalent to q=*).

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

    # Normalize query - empty query means "get all"
    search_query = q.strip() if q else "*"
    if not search_query:
        search_query = "*"

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

    # Build orderby expression for Azure AI Search
    # relevance = no explicit orderby (use search score)
    orderby = None
    if sort != SortOption.RELEVANCE:
        sort_field_map = {
            SortOption.POPULARITY: "popularity_score",
            SortOption.RECENT: "last_commit_date",
            SortOption.STARS: "stars",
        }
        sort_field = sort_field_map.get(sort)
        if sort_field:
            orderby = f"{sort_field} {sort_order.value}"

    # Generate embedding for hybrid/vector search
    # Skip embedding for wildcard queries
    embedding = None
    if mode in (SearchMode.HYBRID, SearchMode.VECTOR) and search_query != "*":
        if llm_service.is_configured:
            try:
                embedding = await llm_service.generate_embedding(search_query)
            except Exception as e:
                logger.warning(f"Failed to generate embedding, falling back to keyword: {e}")
                if mode == SearchMode.VECTOR:
                    raise ValidationError("Vector search requires embedding generation, which failed")

    # Execute search based on mode
    if mode == SearchMode.HYBRID:
        results = await search_service.hybrid_search(
            query=search_query,
            filters=filters,
            limit=limit,
            offset=offset,
            embedding=embedding,
            orderby=orderby,
        )
    elif mode == SearchMode.KEYWORD:
        results = await search_service.keyword_search(
            query=search_query,
            filters=filters,
            limit=limit,
            offset=offset,
            orderby=orderby,
        )
    else:  # VECTOR
        if not embedding:
            raise ValidationError("Vector search requires query embedding")
        results = await search_service.vector_search(
            embedding=embedding,
            filters=filters,
            limit=limit,
            offset=offset,
            orderby=orderby,
        )

    # Convert to response format
    response_data = SearchResponse(
        items=[
            SearchResultItem(
                id=item.id,
                title=item.title,
                title_kr=item.title_kr,
                description=item.description,
                description_kr=item.description_kr,
                summary=item.summary,
                summary_kr=item.summary_kr,
                summary_short=item.summary,  # Alias
                categories=item.categories,
                technologies=item.technologies,
                difficulty_level=item.difficulty_level,
                level=item.difficulty_level,  # Alias
                popularity_score=item.popularity_score,
                stars=item.stars,
                score=item.score,
                source_url=item.source_url,
                video_url=item.video_url,
                thumbnail_url=item.thumbnail_url,
                icon=item.icon,
                duration_minutes=item.duration_minutes,
                view_count=item.view_count,
                last_commit_date=item.last_commit_date,
                learning_outcomes=item.learning_outcomes,
                learning_outcomes_kr=item.learning_outcomes_kr,
                prerequisites=item.prerequisites,
                prerequisites_kr=item.prerequisites_kr,
            )
            for item in results.items
        ],
        total=results.total,
        facets=results.facets,
        query=search_query,
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
