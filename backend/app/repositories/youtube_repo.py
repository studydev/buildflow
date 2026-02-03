"""YouTube repository for Cosmos DB operations."""

import logging
from datetime import datetime
from typing import Optional

from app.db.cosmos import Containers, get_container
from app.models.enums import YouTubeAnalysisStatus
from app.models.youtube import YouTubeAnalysisRequest, YouTubeContent

logger = logging.getLogger(__name__)


class YouTubeRepository:
    """Repository for YouTube analysis request CRUD operations in Cosmos DB."""

    def __init__(self):
        """Initialize repository."""
        self._container = None

    @property
    def container(self):
        """Lazy load container."""
        if self._container is None:
            self._container = get_container(
                Containers.YOUTUBE_ANALYSIS,
                partition_key_path="/id"
            )
        return self._container

    async def create(self, request: YouTubeAnalysisRequest) -> YouTubeAnalysisRequest:
        """
        Create a new YouTube analysis request.

        Args:
            request: YouTubeAnalysisRequest to create

        Returns:
            Created YouTubeAnalysisRequest
        """
        item = request.to_cosmos_item()
        self.container.create_item(body=item)
        logger.info(f"Created YouTube analysis request: {request.id} for user: {request.user_id}")
        return request

    async def get_by_id(self, request_id: str, user_id: str) -> Optional[YouTubeAnalysisRequest]:
        """
        Get a YouTube analysis request by ID.

        Args:
            request_id: Request ID
            user_id: User ID (for authorization check)

        Returns:
            YouTubeAnalysisRequest if found, None otherwise
        """
        try:
            item = self.container.read_item(
                item=request_id,
                partition_key=request_id,
            )
            # Verify user owns this request
            if item.get("user_id") != user_id:
                return None
            return YouTubeAnalysisRequest.from_cosmos_item(item)
        except Exception as e:
            if "NotFound" in str(e) or "404" in str(e):
                return None
            raise

    async def get_by_id_no_auth(self, request_id: str) -> Optional[YouTubeAnalysisRequest]:
        """
        Get a YouTube analysis request by ID without user check.
        Used for internal operations.

        Args:
            request_id: Request ID

        Returns:
            YouTubeAnalysisRequest if found, None otherwise
        """
        try:
            item = self.container.read_item(
                item=request_id,
                partition_key=request_id,
            )
            return YouTubeAnalysisRequest.from_cosmos_item(item)
        except Exception as e:
            if "NotFound" in str(e) or "404" in str(e):
                return None
            raise

    async def update(self, request: YouTubeAnalysisRequest) -> YouTubeAnalysisRequest:
        """
        Update a YouTube analysis request.

        Args:
            request: YouTubeAnalysisRequest to update

        Returns:
            Updated YouTubeAnalysisRequest
        """
        request.updated_at = datetime.utcnow()
        item = request.to_cosmos_item()
        self.container.upsert_item(body=item)
        logger.info(f"Updated YouTube analysis request: {request.id} status: {request.status.value}")
        return request

    async def delete(self, request_id: str) -> bool:
        """
        Delete a YouTube analysis request.

        Args:
            request_id: Request ID to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            self.container.delete_item(
                item=request_id,
                partition_key=request_id,
            )
            logger.info(f"Deleted YouTube analysis request: {request_id}")
            return True
        except Exception as e:
            if "NotFound" in str(e) or "404" in str(e):
                return False
            raise

    async def list_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[YouTubeAnalysisStatus] = None,
    ) -> list[YouTubeAnalysisRequest]:
        """
        List YouTube analysis requests for a user.

        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Number of results to skip
            status: Optional status filter

        Returns:
            List of YouTubeAnalysisRequest
        """
        query = "SELECT * FROM c WHERE c.user_id = @user_id AND c.type = 'youtube_analysis_request'"
        parameters = [{"name": "@user_id", "value": user_id}]

        if status:
            query += " AND c.status = @status"
            parameters.append({"name": "@status", "value": status.value})

        query += " ORDER BY c.created_at DESC"
        query += " OFFSET @offset LIMIT @limit"
        parameters.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ])

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        return [YouTubeAnalysisRequest.from_cosmos_item(item) for item in items]

    async def count_by_user(self, user_id: str) -> int:
        """
        Count YouTube analysis requests for a user.

        Args:
            user_id: User ID

        Returns:
            Number of requests
        """
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.user_id = @user_id AND c.type = 'youtube_analysis_request'"
        parameters = [{"name": "@user_id", "value": user_id}]

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        return items[0] if items else 0

    async def get_by_video_id(self, video_id: str, user_id: str) -> Optional[YouTubeAnalysisRequest]:
        """
        Get a YouTube analysis request by video ID for a specific user.

        Args:
            video_id: YouTube video ID
            user_id: User ID

        Returns:
            YouTubeAnalysisRequest if found, None otherwise
        """
        query = """
            SELECT * FROM c
            WHERE c.video_id = @video_id
            AND c.user_id = @user_id
            AND c.type = 'youtube_analysis_request'
        """
        parameters = [
            {"name": "@video_id", "value": video_id},
            {"name": "@user_id", "value": user_id},
        ]

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        if items:
            return YouTubeAnalysisRequest.from_cosmos_item(items[0])
        return None


class YouTubeContentRepository:
    """Repository for YouTubeContent CRUD operations in Cosmos DB."""

    def __init__(self):
        """Initialize repository."""
        self._container = None

    @property
    def container(self):
        """Lazy load container."""
        if self._container is None:
            self._container = get_container(
                Containers.YOUTUBE_CONTENTS,
                partition_key_path="/id"
            )
        return self._container

    async def create(self, content: YouTubeContent) -> YouTubeContent:
        """
        Create a new YouTube content.

        Args:
            content: YouTubeContent to create

        Returns:
            Created YouTubeContent
        """
        item = content.to_cosmos_item()
        self.container.create_item(body=item)
        logger.info(f"Created YouTube content: {content.id}")
        return content

    async def get_by_id(self, content_id: str) -> Optional[YouTubeContent]:
        """
        Get YouTube content by ID.

        Args:
            content_id: Content ID

        Returns:
            YouTubeContent if found, None otherwise
        """
        try:
            item = self.container.read_item(
                item=content_id,
                partition_key=content_id,
            )
            return YouTubeContent.from_cosmos_item(item)
        except Exception as e:
            if "NotFound" in str(e) or "404" in str(e):
                return None
            raise

    async def update(self, content: YouTubeContent) -> YouTubeContent:
        """
        Update YouTube content.

        Args:
            content: YouTubeContent to update

        Returns:
            Updated YouTubeContent
        """
        content.updated_at = datetime.utcnow()
        item = content.to_cosmos_item()
        self.container.upsert_item(body=item)
        logger.info(f"Updated YouTube content: {content.id}")
        return content

    async def delete(self, content_id: str) -> bool:
        """
        Delete YouTube content.

        Args:
            content_id: Content ID to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            self.container.delete_item(
                item=content_id,
                partition_key=content_id,
            )
            logger.info(f"Deleted YouTube content: {content_id}")
            return True
        except Exception as e:
            if "NotFound" in str(e) or "404" in str(e):
                return False
            raise

    async def list_by_contributor(
        self,
        contributor_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[YouTubeContent]:
        """
        List YouTube content by contributor.

        Args:
            contributor_id: Contributor ID
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of YouTubeContent
        """
        query = "SELECT * FROM c WHERE c.contributor_id = @contributor_id AND c.type = 'youtube_content'"
        parameters = [{"name": "@contributor_id", "value": contributor_id}]

        query += " ORDER BY c.created_at DESC"
        query += " OFFSET @offset LIMIT @limit"
        parameters.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ])

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        return [YouTubeContent.from_cosmos_item(item) for item in items]

    async def list_published(
        self,
        limit: int = 50,
        offset: int = 0,
        category: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[YouTubeContent]:
        """
        List published YouTube content.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            category: Optional category filter
            search: Optional search term

        Returns:
            List of published YouTubeContent
        """
        query = "SELECT * FROM c WHERE c.status = 'published' AND c.type = 'youtube_content'"
        parameters = []

        if category:
            query += " AND ARRAY_CONTAINS(c.categories, @category)"
            parameters.append({"name": "@category", "value": category})

        if search:
            query += " AND (CONTAINS(LOWER(c.title), LOWER(@search)) OR CONTAINS(LOWER(c.description), LOWER(@search)))"
            parameters.append({"name": "@search", "value": search})

        query += " ORDER BY c.created_at DESC"
        query += " OFFSET @offset LIMIT @limit"
        parameters.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ])

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        return [YouTubeContent.from_cosmos_item(item) for item in items]

    async def count_published(self) -> int:
        """Count published YouTube content."""
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.status = 'published' AND c.type = 'youtube_content'"

        items = list(self.container.query_items(
            query=query,
            parameters=[],
            enable_cross_partition_query=True,
        ))

        return items[0] if items else 0


# =============================================================================
# Singleton instances
# =============================================================================

_youtube_repo: Optional[YouTubeRepository] = None
_youtube_content_repo: Optional[YouTubeContentRepository] = None


def get_youtube_repo() -> YouTubeRepository:
    """Get YouTube repository singleton."""
    global _youtube_repo
    if _youtube_repo is None:
        _youtube_repo = YouTubeRepository()
    return _youtube_repo


def get_youtube_content_repo() -> YouTubeContentRepository:
    """Get YouTube content repository singleton."""
    global _youtube_content_repo
    if _youtube_content_repo is None:
        _youtube_content_repo = YouTubeContentRepository()
    return _youtube_content_repo
