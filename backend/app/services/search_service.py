"""Azure AI Search Service for content discovery.

Per tasks.md T400-T401: Search infrastructure and service implementation.

Provides:
- Index management (create, update schema)
- Document operations (upsert, delete)
- Search modes (hybrid, keyword, vector)
- Filtering and faceting
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx

from app.config import get_settings
from app.models.content import Content

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# Search Constants
# =============================================================================

INDEX_NAME = "buildflow-content"

# Index schema per design.md §6
INDEX_SCHEMA = {
    "name": INDEX_NAME,
    "fields": [
        # Identifiers
        {"name": "id", "type": "Edm.String", "key": True, "searchable": False},
        
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
            "name": "summary",
            "type": "Edm.String",
            "searchable": True,
            "filterable": False,
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
        
        # Filterable strings
        {
            "name": "difficulty_level",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
            "facetable": True,
        },
        {
            "name": "visibility",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
        },
        {
            "name": "content_type",
            "type": "Edm.String",
            "searchable": False,
            "filterable": True,
            "facetable": True,
        },
        
        # Sortable metrics
        {
            "name": "popularity_score",
            "type": "Edm.Double",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        },
        {
            "name": "stars",
            "type": "Edm.Int32",
            "searchable": False,
            "filterable": True,
            "sortable": True,
        },
        {
            "name": "last_commit_date",
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
        
        # Vector field for semantic search
        {
            "name": "content_vector",
            "type": "Collection(Edm.Single)",
            "searchable": True,
            "dimensions": 1536,
            "vectorSearchProfile": "default-profile",
        },
    ],
    "vectorSearch": {
        "algorithms": [
            {
                "name": "hnsw-algorithm",
                "kind": "hnsw",
                "hnswParameters": {
                    "metric": "cosine",
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                },
            }
        ],
        "profiles": [
            {
                "name": "default-profile",
                "algorithm": "hnsw-algorithm",
            }
        ],
    },
    "scoringProfiles": [
        {
            "name": "popularity-boost",
            "functions": [
                {
                    "type": "magnitude",
                    "fieldName": "popularity_score",
                    "boost": 2.0,
                    "interpolation": "linear",
                    "magnitude": {"boostingRangeStart": 0, "boostingRangeEnd": 1},
                },
                {
                    "type": "freshness",
                    "fieldName": "last_commit_date",
                    "boost": 1.5,
                    "interpolation": "linear",
                    "freshness": {"boostingDuration": "P180D"},
                },
            ],
        }
    ],
    "defaultScoringProfile": "popularity-boost",
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SearchFilters:
    """Filters for search queries."""
    
    categories: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    difficulty: Optional[str] = None
    min_stars: Optional[int] = None
    visibility: Optional[str] = None
    content_type: Optional[str] = None
    
    def to_odata_filter(self) -> Optional[str]:
        """Convert to OData filter string."""
        conditions = []
        
        if self.categories:
            cat_conditions = " or ".join(
                f"categories/any(c: c eq '{cat}')" for cat in self.categories
            )
            conditions.append(f"({cat_conditions})")
        
        if self.technologies:
            tech_conditions = " or ".join(
                f"technologies/any(t: t eq '{tech}')" for tech in self.technologies
            )
            conditions.append(f"({tech_conditions})")
        
        if self.difficulty:
            conditions.append(f"difficulty_level eq '{self.difficulty}'")
        
        if self.min_stars is not None:
            conditions.append(f"stars ge {self.min_stars}")
        
        if self.visibility:
            conditions.append(f"visibility eq '{self.visibility}'")
        
        if self.content_type:
            conditions.append(f"content_type eq '{self.content_type}'")
        
        if conditions:
            return " and ".join(conditions)
        return None


@dataclass
class SearchResult:
    """Single search result item."""
    
    id: str
    title: str
    description: Optional[str] = None
    summary: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    difficulty_level: Optional[str] = None
    popularity_score: float = 0.0
    stars: int = 0
    score: float = 0.0
    
    @classmethod
    def from_document(cls, doc: Dict[str, Any]) -> "SearchResult":
        """Create from Azure AI Search document."""
        return cls(
            id=doc.get("id", ""),
            title=doc.get("title", ""),
            description=doc.get("description"),
            summary=doc.get("summary"),
            categories=doc.get("categories", []),
            technologies=doc.get("technologies", []),
            difficulty_level=doc.get("difficulty_level"),
            popularity_score=doc.get("popularity_score", 0.0),
            stars=doc.get("stars", 0),
            score=doc.get("@search.score", 0.0),
        )


@dataclass
class SearchResults:
    """Search results with pagination and facets."""
    
    items: List[SearchResult]
    total: int
    facets: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "summary": item.summary,
                    "categories": item.categories,
                    "technologies": item.technologies,
                    "difficulty_level": item.difficulty_level,
                    "popularity_score": item.popularity_score,
                    "stars": item.stars,
                    "score": item.score,
                }
                for item in self.items
            ],
            "total": self.total,
            "facets": self.facets,
        }


# =============================================================================
# Search Service Error Classes
# =============================================================================


class SearchError(Exception):
    """Base exception for search service errors."""
    pass


class SearchConfigError(SearchError):
    """Search configuration error."""
    pass


class SearchIndexError(SearchError):
    """Search index operation error."""
    pass


class SearchQueryError(SearchError):
    """Search query error."""
    pass


# =============================================================================
# Search Service
# =============================================================================


class SearchService:
    """Azure AI Search service for content discovery.
    
    Per tasks.md T401: Implements hybrid, keyword, and vector search.
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: str = INDEX_NAME,
    ):
        """
        Initialize search service.
        
        Args:
            endpoint: Azure AI Search endpoint URL
            api_key: Admin or query API key
            index_name: Name of the search index
        """
        self.endpoint = endpoint or getattr(settings, 'azure_search_endpoint', None)
        self.api_key = api_key or getattr(settings, 'azure_search_api_key', None)
        self.index_name = index_name
        self.api_version = "2024-07-01"
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def is_configured(self) -> bool:
        """Check if search service is configured."""
        return bool(self.endpoint and self.api_key)
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Content-Type": "application/json",
            "api-key": self.api_key or "",
        }
    
    # =========================================================================
    # Index Management
    # =========================================================================
    
    async def create_or_update_index(self) -> bool:
        """
        Create or update the search index.
        
        Per tasks.md T400: Create index with schema from design.md §6.
        
        Returns:
            True if successful
            
        Raises:
            SearchConfigError: If not configured
            SearchIndexError: If operation fails
        """
        if not self.is_configured:
            raise SearchConfigError("Azure AI Search is not configured")
        
        url = f"{self.endpoint}/indexes/{self.index_name}?api-version={self.api_version}"
        
        try:
            client = await self.get_client()
            response = await client.put(
                url,
                json=INDEX_SCHEMA,
                headers=self._get_headers(),
            )
            
            if response.status_code in (200, 201):
                logger.info(f"Search index '{self.index_name}' created/updated successfully")
                return True
            else:
                error_msg = f"Failed to create/update index: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise SearchIndexError(error_msg)
                
        except httpx.RequestError as e:
            raise SearchIndexError(f"Index operation failed: {e}")
    
    async def delete_index(self) -> bool:
        """Delete the search index."""
        if not self.is_configured:
            raise SearchConfigError("Azure AI Search is not configured")
        
        url = f"{self.endpoint}/indexes/{self.index_name}?api-version={self.api_version}"
        
        try:
            client = await self.get_client()
            response = await client.delete(url, headers=self._get_headers())
            
            if response.status_code in (200, 204, 404):
                logger.info(f"Search index '{self.index_name}' deleted")
                return True
            else:
                raise SearchIndexError(f"Failed to delete index: {response.status_code}")
                
        except httpx.RequestError as e:
            raise SearchIndexError(f"Delete index failed: {e}")
    
    # =========================================================================
    # Document Operations
    # =========================================================================
    
    async def upsert_document(
        self,
        content: Content,
        embedding: Optional[List[float]] = None,
    ) -> None:
        """
        Upsert a content document to the search index.
        
        Args:
            content: Content model to index
            embedding: Pre-computed embedding vector (optional)
            
        Raises:
            SearchConfigError: If not configured
            SearchIndexError: If operation fails
        """
        if not self.is_configured:
            raise SearchConfigError("Azure AI Search is not configured")
        
        # Build document from Content
        doc = self._content_to_document(content, embedding)
        
        await self._batch_upload([{"@search.action": "mergeOrUpload", **doc}])
    
    async def upsert_documents(
        self,
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Batch upsert documents to the search index.
        
        Args:
            documents: List of documents with @search.action
            
        Returns:
            Batch result summary
        """
        if not self.is_configured:
            raise SearchConfigError("Azure AI Search is not configured")
        
        return await self._batch_upload(documents)
    
    async def delete_document(self, content_id: UUID) -> None:
        """
        Delete a document from the search index.
        
        Args:
            content_id: Content UUID to delete
        """
        if not self.is_configured:
            raise SearchConfigError("Azure AI Search is not configured")
        
        doc = {"@search.action": "delete", "id": str(content_id)}
        await self._batch_upload([doc])
    
    async def _batch_upload(
        self,
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Perform batch document upload."""
        url = f"{self.endpoint}/indexes/{self.index_name}/docs/index?api-version={self.api_version}"
        
        payload = {"value": documents}
        
        try:
            client = await self.get_client()
            response = await client.post(
                url,
                json=payload,
                headers=self._get_headers(),
            )
            
            if response.status_code in (200, 207):
                result = response.json()
                logger.info(f"Indexed {len(documents)} documents")
                return result
            else:
                error_msg = f"Batch upload failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise SearchIndexError(error_msg)
                
        except httpx.RequestError as e:
            raise SearchIndexError(f"Batch upload failed: {e}")
    
    def _content_to_document(
        self,
        content: Content,
        embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """Convert Content model to search document."""
        doc = {
            "id": str(content.id),
            "title": content.title,
            "title_kr": getattr(content, "title_kr", None),
            "description": content.description,
            "summary": content.summary_short or content.summary_long,
            "categories": content.categories or [],
            "technologies": content.technologies or [],
            "difficulty_level": content.difficulty_level,
            "visibility": content.visibility.value if content.visibility else "internal",
            "content_type": content.content_type.value if content.content_type else None,
            "popularity_score": content.popularity_score or 0.0,
            "stars": content.stars or 0,
            "last_commit_date": (
                content.last_commit_date.isoformat() 
                if content.last_commit_date else None
            ),
            "created_at": (
                content.created_at.isoformat() 
                if content.created_at else None
            ),
        }
        
        if embedding:
            doc["content_vector"] = embedding
        
        # Remove None values
        return {k: v for k, v in doc.items() if v is not None}
    
    # =========================================================================
    # Search Operations
    # =========================================================================
    
    async def hybrid_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        offset: int = 0,
        embedding: Optional[List[float]] = None,
    ) -> SearchResults:
        """
        Perform hybrid search (keyword + vector).
        
        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum results
            offset: Pagination offset
            embedding: Query embedding for vector search
            
        Returns:
            SearchResults with items, total, and facets
        """
        search_body: Dict[str, Any] = {
            "search": query,
            "searchMode": "any",
            "queryType": "full",
            "top": limit,
            "skip": offset,
            "count": True,
            "facets": ["categories,count:20", "technologies,count:20", "difficulty_level"],
            "select": "id,title,description,summary,categories,technologies,difficulty_level,popularity_score,stars",
        }
        
        # Add filter
        if filters:
            odata_filter = filters.to_odata_filter()
            if odata_filter:
                search_body["filter"] = odata_filter
        
        # Add vector search if embedding provided
        if embedding:
            search_body["vectorQueries"] = [
                {
                    "kind": "vector",
                    "vector": embedding,
                    "fields": "content_vector",
                    "k": limit,
                }
            ]
        
        return await self._execute_search(search_body)
    
    async def keyword_search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResults:
        """
        Perform keyword-only search.
        
        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            SearchResults with items, total, and facets
        """
        search_body: Dict[str, Any] = {
            "search": query,
            "searchMode": "any",
            "queryType": "full",
            "top": limit,
            "skip": offset,
            "count": True,
            "facets": ["categories,count:20", "technologies,count:20", "difficulty_level"],
            "select": "id,title,description,summary,categories,technologies,difficulty_level,popularity_score,stars",
        }
        
        if filters:
            odata_filter = filters.to_odata_filter()
            if odata_filter:
                search_body["filter"] = odata_filter
        
        return await self._execute_search(search_body)
    
    async def vector_search(
        self,
        embedding: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResults:
        """
        Perform vector-only search.
        
        Args:
            embedding: Query embedding vector
            filters: Optional search filters
            limit: Maximum results
            offset: Pagination offset
            
        Returns:
            SearchResults with items, total, and facets
        """
        search_body: Dict[str, Any] = {
            "search": "*",  # Required for vector search
            "top": limit,
            "skip": offset,
            "count": True,
            "facets": ["categories,count:20", "technologies,count:20", "difficulty_level"],
            "select": "id,title,description,summary,categories,technologies,difficulty_level,popularity_score,stars",
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": embedding,
                    "fields": "content_vector",
                    "k": limit,
                }
            ],
        }
        
        if filters:
            odata_filter = filters.to_odata_filter()
            if odata_filter:
                search_body["filter"] = odata_filter
        
        return await self._execute_search(search_body)
    
    async def _execute_search(
        self,
        search_body: Dict[str, Any],
    ) -> SearchResults:
        """Execute search request."""
        if not self.is_configured:
            raise SearchConfigError("Azure AI Search is not configured")
        
        url = f"{self.endpoint}/indexes/{self.index_name}/docs/search?api-version={self.api_version}"
        
        try:
            client = await self.get_client()
            response = await client.post(
                url,
                json=search_body,
                headers=self._get_headers(),
            )
            
            if response.status_code != 200:
                error_msg = f"Search failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise SearchQueryError(error_msg)
            
            result = response.json()
            
            # Parse results
            items = [
                SearchResult.from_document(doc)
                for doc in result.get("value", [])
            ]
            
            total = result.get("@odata.count", len(items))
            
            # Parse facets
            facets = {}
            for facet_name, facet_values in result.get("@search.facets", {}).items():
                facets[facet_name] = [
                    {"value": fv.get("value"), "count": fv.get("count", 0)}
                    for fv in facet_values
                ]
            
            return SearchResults(items=items, total=total, facets=facets)
            
        except httpx.RequestError as e:
            raise SearchQueryError(f"Search request failed: {e}")


# =============================================================================
# Singleton
# =============================================================================

_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get the search service singleton."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
