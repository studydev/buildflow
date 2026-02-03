"""Azure AI Search Service for YouTube content discovery.

Provides:
- Index management for YouTube content
- Document operations (upsert, delete)
- Search modes (hybrid, keyword, vector)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

import httpx

from app.config import get_settings
from app.models.youtube import YouTubeContent

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# Search Constants
# =============================================================================

YOUTUBE_INDEX_NAME = "buildflow-youtube"

# Index schema for YouTube content
YOUTUBE_INDEX_SCHEMA = {
    "name": YOUTUBE_INDEX_NAME,
    "fields": [
        # Identifiers
        {"name": "id", "type": "Edm.String", "key": True, "searchable": False},

        # Reference to analysis request (for script lookup)
        {
            "name": "analysis_request_id",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
        },

        # Video info
        {
            "name": "video_id",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
        },
        {
            "name": "channel_name",
            "type": "Edm.String",
            "searchable": True,
            "filterable": True,
            "facetable": True,
        },

        # Searchable text - English
        {
            "name": "title",
            "type": "Edm.String",
            "searchable": True,
            "filterable": True,
            "sortable": True,
            "analyzer": "en.microsoft",
        },
        {
            "name": "title_kr",
            "type": "Edm.String",
            "searchable": True,
            "filterable": False,
            "analyzer": "ko.microsoft",
        },
        {
            "name": "description",
            "type": "Edm.String",
            "searchable": True,
            "filterable": False,
        },
        {
            "name": "description_kr",
            "type": "Edm.String",
            "searchable": True,
            "filterable": False,
            "analyzer": "ko.microsoft",
        },
        {
            "name": "script_summary",
            "type": "Edm.String",
            "searchable": True,
            "filterable": False,
        },
        {
            "name": "script_summary_kr",
            "type": "Edm.String",
            "searchable": True,
            "filterable": False,
            "analyzer": "ko.microsoft",
        },

        # Filterable/Facetable collections
        {
            "name": "categories",
            "type": "Collection(Edm.String)",
            "searchable": True,
            "filterable": True,
            "facetable": True,
        },
        {
            "name": "technologies",
            "type": "Collection(Edm.String)",
            "searchable": True,
            "filterable": True,
            "facetable": True,
        },
        {
            "name": "tags",
            "type": "Collection(Edm.String)",
            "searchable": True,
            "filterable": True,
        },

        # Filterable strings
        {
            "name": "level",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
            "facetable": True,
        },
        {
            "name": "content_type",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
            "facetable": True,
        },

        # URLs
        {
            "name": "source_url",
            "type": "Edm.String",
            "searchable": False,
            "filterable": False,
        },
        {
            "name": "thumbnail_url",
            "type": "Edm.String",
            "searchable": False,
            "filterable": False,
        },

        # Metrics
        {
            "name": "duration_minutes",
            "type": "Edm.Int32",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        },
        {
            "name": "duration_seconds",
            "type": "Edm.Int32",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        },
        {
            "name": "view_count",
            "type": "Edm.Int64",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        },
        {
            "name": "like_count",
            "type": "Edm.Int64",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        },

        # Timestamps
        {
            "name": "upload_date",
            "type": "Edm.DateTimeOffset",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        },
        {
            "name": "created_at",
            "type": "Edm.DateTimeOffset",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        },

        # Vector search
        {
            "name": "content_vector",
            "type": "Collection(Edm.Single)",
            "searchable": True,
            "dimensions": 1536,
            "vectorSearchProfile": "youtube-vector-profile",
        },
    ],
    "vectorSearch": {
        "profiles": [
            {
                "name": "youtube-vector-profile",
                "algorithm": "youtube-hnsw-algorithm",
            }
        ],
        "algorithms": [
            {
                "name": "youtube-hnsw-algorithm",
                "kind": "hnsw",
                "hnswParameters": {
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine",
                },
            }
        ],
    },
}


@dataclass
class YouTubeSearchResult:
    """Search result item for YouTube content."""

    id: str
    video_id: str
    title: str
    analysis_request_id: Optional[str] = None  # For script lookup
    title_kr: Optional[str] = None
    description: str = ""
    description_kr: Optional[str] = None
    channel_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    source_url: Optional[str] = None
    duration_minutes: int = 0
    duration_seconds: int = 0
    view_count: int = 0
    like_count: int = 0
    categories: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    level: Optional[str] = None
    content_type: Optional[str] = None
    score: float = 0.0


@dataclass
class YouTubeSearchResponse:
    """Search response with results and metadata."""

    results: list[YouTubeSearchResult]
    total_count: int
    facets: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


class YouTubeSearchService:
    """Service for searching YouTube content using Azure AI Search."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: str = YOUTUBE_INDEX_NAME,
    ):
        """Initialize search service."""
        self.endpoint = endpoint or getattr(settings, "azure_search_endpoint", None)
        self.api_key = api_key or getattr(settings, "azure_search_api_key", None)
        self.index_name = index_name
        self._client: Optional[httpx.AsyncClient] = None
        self._llm_service = None  # Lazy load to avoid circular imports

    @property
    def is_configured(self) -> bool:
        """Check if search service is configured."""
        return bool(self.endpoint and self.api_key)

    def _get_llm_service(self):
        """Get LLM service for embedding generation (lazy load)."""
        if self._llm_service is None:
            from app.services.llm_service import get_llm_service
            self._llm_service = get_llm_service()
        return self._llm_service

    async def _generate_embedding(self, content: YouTubeContent) -> Optional[List[float]]:
        """Generate embedding vector for YouTube content."""
        try:
            llm = self._get_llm_service()
            if not llm.is_configured:
                logger.warning("LLM service not configured, skipping embedding generation")
                return None

            # Combine text fields for embedding (title + description + script_summary)
            text_parts = []
            if content.title_en or content.title:
                text_parts.append(content.title_en or content.title)
            if content.description_en or content.description:
                text_parts.append(content.description_en or content.description)
            if content.script_summary_en:
                text_parts.append(content.script_summary_en)

            text = " ".join(text_parts)
            if not text.strip():
                logger.warning(f"No text content for embedding: {content.id}")
                return None

            embedding = await llm.generate_embedding(text)
            logger.info(f"Generated embedding for YouTube content: {content.id} ({len(embedding)} dimensions)")
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for {content.id}: {e}")
            return None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _build_url(self, path: str) -> str:
        """Build Azure Search API URL."""
        base = self.endpoint.rstrip("/")
        return f"{base}/{path}?api-version=2024-07-01"

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[dict] = None,
    ) -> dict:
        """Make authenticated request to Azure Search."""
        if not self.is_configured:
            raise RuntimeError("YouTube Search service not configured")

        client = await self._get_client()
        url = self._build_url(path)

        response = await client.request(
            method=method,
            url=url,
            headers={
                "Content-Type": "application/json",
                "api-key": self.api_key,
            },
            json=json_data,
        )

        if response.status_code >= 400:
            logger.error(f"Search API error: {response.status_code} - {response.text}")
            response.raise_for_status()

        if response.status_code == 204:
            return {}

        return response.json()

    async def create_index(self) -> dict:
        """Create or update the YouTube search index."""
        logger.info(f"Creating/updating index: {self.index_name}")

        try:
            # Try to create new index
            result = await self._request(
                "PUT",
                f"indexes/{self.index_name}",
                YOUTUBE_INDEX_SCHEMA,
            )
            logger.info(f"Index created/updated: {self.index_name}")
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create index: {e}")
            raise

    async def index_content(self, content: YouTubeContent) -> dict:
        """Index a YouTube content document with embedding."""
        if not self.is_configured:
            logger.warning("YouTube Search not configured, skipping indexing")
            return {}

        document = self._content_to_document(content)

        # Generate embedding for vector search
        embedding = await self._generate_embedding(content)
        if embedding:
            document["content_vector"] = embedding

        result = await self._request(
            "POST",
            f"indexes/{self.index_name}/docs/index",
            {
                "value": [
                    {
                        "@search.action": "mergeOrUpload",
                        **document,
                    }
                ]
            },
        )

        logger.info(f"Indexed YouTube content: {content.id} (with vector: {embedding is not None})")
        return result

    async def delete_content(self, content_id: str) -> dict:
        """Delete a YouTube content document from the index."""
        if not self.is_configured:
            logger.warning("YouTube Search not configured, skipping delete")
            return {}

        result = await self._request(
            "POST",
            f"indexes/{self.index_name}/docs/index",
            {
                "value": [
                    {
                        "@search.action": "delete",
                        "id": content_id,
                    }
                ]
            },
        )

        logger.info(f"Deleted YouTube content from index: {content_id}")
        return result

    def _content_to_document(self, content: YouTubeContent) -> dict:
        """Convert YouTubeContent to search document."""

        def format_date(dt) -> Optional[str]:
            """Format datetime for Azure Search (Edm.DateTimeOffset requires Z suffix)."""
            if dt is None:
                return None
            # Azure Search requires ISO format with Z timezone suffix
            if isinstance(dt, str):
                # If it's already a string, try to parse and reformat
                try:
                    from datetime import datetime
                    parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    return None
            # If it's a datetime object
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        return {
            "id": content.id,
            "analysis_request_id": content.analysis_request_id,
            "video_id": content.video_id,
            "channel_name": content.channel_name,
            "title": content.title_en or content.title,
            "title_kr": content.title_kr,
            "description": content.description_en or content.description,
            "description_kr": content.description_kr,
            "script_summary": content.script_summary_en,
            "script_summary_kr": content.script_summary_kr,
            "categories": content.categories or [],
            "technologies": content.technologies or [],
            "tags": content.tags or [],
            "level": content.level,
            "content_type": content.content_type.value if hasattr(content.content_type, 'value') else content.content_type,
            "source_url": content.source_url,
            "thumbnail_url": content.thumbnail_url,
            "duration_minutes": content.duration_minutes,
            "duration_seconds": content.duration_seconds,
            "view_count": content.view_count,
            "like_count": content.like_count,
            "upload_date": format_date(content.upload_date),
            "created_at": format_date(content.created_at),
        }

    async def search(
        self,
        query: str,
        filters: Optional[dict] = None,
        top: int = 20,
        skip: int = 0,
        facets: Optional[list[str]] = None,
        order_by: Optional[str] = None,
        use_vector: bool = True,
    ) -> YouTubeSearchResponse:
        """
        Search YouTube content using hybrid search (keyword + vector).

        Args:
            query: Search query text
            filters: Filter criteria
            top: Number of results to return
            skip: Number of results to skip
            facets: List of fields to return facets for
            order_by: Sort order (e.g., "view_count desc", "created_at desc")
            use_vector: Whether to use vector search (default: True)

        Returns:
            YouTubeSearchResponse with results and metadata
        """
        if not self.is_configured:
            logger.warning("YouTube Search not configured")
            return YouTubeSearchResponse(results=[], total_count=0)

        search_body = {
            "search": query,
            "searchMode": "any",  # Changed from "all" to match partial queries
            "queryType": "simple",
            "top": top,
            "skip": skip,
            "count": True,
            "searchFields": "title,title_kr,description,description_kr,script_summary,script_summary_kr,channel_name,categories,technologies,tags",
            "select": "id,analysis_request_id,video_id,title,title_kr,description,description_kr,channel_name,thumbnail_url,source_url,duration_minutes,duration_seconds,view_count,like_count,categories,technologies,level,content_type",
        }

        # Add vector search for hybrid search
        if use_vector and query != "*":
            try:
                llm = self._get_llm_service()
                if llm.is_configured:
                    query_embedding = await llm.generate_embedding(query)
                    if query_embedding:
                        search_body["vectorQueries"] = [
                            {
                                "kind": "vector",
                                "vector": query_embedding,
                                "fields": "content_vector",
                                "k": top,
                            }
                        ]
                        logger.debug(f"Added vector query for YouTube search: {query[:50]}...")
            except Exception as e:
                logger.warning(f"Failed to generate query embedding, falling back to keyword search: {e}")

        # Add sort order
        if order_by:
            search_body["orderby"] = order_by

        # Build filter string
        filter_parts = []
        if filters:
            if filters.get("category"):
                filter_parts.append(f"categories/any(c: c eq '{filters['category']}')")
            if filters.get("level"):
                filter_parts.append(f"level eq '{filters['level']}'")
            if filters.get("content_type"):
                filter_parts.append(f"content_type eq '{filters['content_type']}'")
            if filters.get("channel_name"):
                filter_parts.append(f"channel_name eq '{filters['channel_name']}'")

        if filter_parts:
            search_body["filter"] = " and ".join(filter_parts)

        # Add facets
        if facets:
            search_body["facets"] = facets

        result = await self._request(
            "POST",
            f"indexes/{self.index_name}/docs/search",
            search_body,
        )

        # Parse results
        results = []
        for doc in result.get("value", []):
            results.append(
                YouTubeSearchResult(
                    id=doc.get("id", ""),
                    video_id=doc.get("video_id", ""),
                    title=doc.get("title", ""),
                    analysis_request_id=doc.get("analysis_request_id"),
                    title_kr=doc.get("title_kr"),
                    description=doc.get("description", ""),
                    description_kr=doc.get("description_kr"),
                    channel_name=doc.get("channel_name"),
                    thumbnail_url=doc.get("thumbnail_url"),
                    source_url=doc.get("source_url"),
                    duration_minutes=doc.get("duration_minutes", 0),
                    duration_seconds=doc.get("duration_seconds", 0),
                    view_count=doc.get("view_count", 0),
                    like_count=doc.get("like_count", 0),
                    categories=doc.get("categories", []),
                    technologies=doc.get("technologies", []),
                    level=doc.get("level"),
                    content_type=doc.get("content_type"),
                    score=doc.get("@search.score", 0.0),
                )
            )

        # Parse facets
        parsed_facets = {}
        for facet_name, facet_values in result.get("@search.facets", {}).items():
            parsed_facets[facet_name] = [
                {"value": fv.get("value"), "count": fv.get("count")}
                for fv in facet_values
            ]

        return YouTubeSearchResponse(
            results=results,
            total_count=result.get("@odata.count", len(results)),
            facets=parsed_facets,
        )


# =============================================================================
# Singleton
# =============================================================================

_youtube_search_service: Optional[YouTubeSearchService] = None


def get_youtube_search_service() -> YouTubeSearchService:
    """Get YouTube search service singleton."""
    global _youtube_search_service
    if _youtube_search_service is None:
        _youtube_search_service = YouTubeSearchService()
    return _youtube_search_service
