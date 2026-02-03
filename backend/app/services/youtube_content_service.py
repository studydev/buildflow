"""YouTube content service for managing YouTube content lifecycle."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from app.models.enums import ContentStatus
from app.models.youtube import YouTubeContent
from app.repositories.youtube_repo import (
    YouTubeContentRepository,
    get_youtube_content_repo,
)

if TYPE_CHECKING:
    from app.services.youtube_search_service import YouTubeSearchService

logger = logging.getLogger(__name__)


class YouTubeContentService:
    """Service for managing YouTube content lifecycle."""

    def __init__(
        self,
        content_repo: Optional[YouTubeContentRepository] = None,
        search_service: Optional["YouTubeSearchService"] = None,
    ):
        """
        Initialize service.

        Args:
            content_repo: YouTube content repository
            search_service: YouTube search service for indexing
        """
        self._content_repo = content_repo
        self._search_service = search_service

    @property
    def content_repo(self) -> YouTubeContentRepository:
        """Get content repository."""
        if self._content_repo is None:
            self._content_repo = get_youtube_content_repo()
        return self._content_repo

    @property
    def search_service(self) -> "YouTubeSearchService":
        """Get search service."""
        if self._search_service is None:
            from app.services.youtube_search_service import get_youtube_search_service
            self._search_service = get_youtube_search_service()
        return self._search_service

    async def create_content(self, content: YouTubeContent) -> YouTubeContent:
        """
        Create new YouTube content.

        Args:
            content: YouTubeContent to create

        Returns:
            Created YouTubeContent
        """
        content.created_at = datetime.utcnow()
        content.updated_at = datetime.utcnow()
        content.status = ContentStatus.DRAFT

        saved_content = await self.content_repo.create(content)
        logger.info(f"Created YouTube content: {saved_content.id}")

        return saved_content

    async def get_content(self, content_id: str) -> Optional[YouTubeContent]:
        """
        Get YouTube content by ID.

        Args:
            content_id: Content ID

        Returns:
            YouTubeContent if found, None otherwise
        """
        return await self.content_repo.get_by_id(content_id)

    async def update_content(self, content: YouTubeContent) -> YouTubeContent:
        """
        Update YouTube content.

        Args:
            content: YouTubeContent to update

        Returns:
            Updated YouTubeContent
        """
        content.updated_at = datetime.utcnow()
        updated_content = await self.content_repo.update(content)

        # If published, update search index
        if updated_content.status == ContentStatus.PUBLISHED:
            try:
                await self.search_service.index_content(updated_content)
            except Exception as e:
                logger.error(f"Failed to update search index: {e}")

        return updated_content

    async def publish_content(
        self,
        content_id: str,
        contributor_email: Optional[str] = None,
    ) -> Optional[YouTubeContent]:
        """
        Publish YouTube content (change status to PUBLISHED).

        Args:
            content_id: Content ID to publish
            contributor_email: Email of user publishing the content

        Returns:
            Published YouTubeContent if found, None otherwise
        """
        content = await self.content_repo.get_by_id(content_id)
        if not content:
            return None

        content.status = ContentStatus.PUBLISHED
        content.published_at = datetime.utcnow()
        content.updated_at = datetime.utcnow()

        if contributor_email:
            content.contributor_update_email = contributor_email

        updated_content = await self.content_repo.update(content)

        # Index in search
        try:
            await self.search_service.index_content(updated_content)
            logger.info(f"Indexed YouTube content: {content_id}")
        except Exception as e:
            logger.error(f"Failed to index content in search: {e}")

        return updated_content

    async def unpublish_content(self, content_id: str) -> Optional[YouTubeContent]:
        """
        Unpublish YouTube content (change status back to DRAFT).

        Args:
            content_id: Content ID to unpublish

        Returns:
            Updated YouTubeContent if found, None otherwise
        """
        content = await self.content_repo.get_by_id(content_id)
        if not content:
            return None

        content.status = ContentStatus.DRAFT
        content.updated_at = datetime.utcnow()

        updated_content = await self.content_repo.update(content)

        # Remove from search index
        try:
            await self.search_service.delete_content(content_id)
            logger.info(f"Removed YouTube content from search: {content_id}")
        except Exception as e:
            logger.error(f"Failed to remove content from search: {e}")

        return updated_content

    async def delete_content(self, content_id: str) -> bool:
        """
        Delete YouTube content.

        Args:
            content_id: Content ID to delete

        Returns:
            True if deleted, False if not found
        """
        # Remove from search index first
        try:
            await self.search_service.delete_content(content_id)
        except Exception as e:
            logger.warning(f"Failed to remove from search (may not exist): {e}")

        deleted = await self.content_repo.delete(content_id)
        if deleted:
            logger.info(f"Deleted YouTube content: {content_id}")

        return deleted

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
        return await self.content_repo.list_by_contributor(
            contributor_id=contributor_id,
            limit=limit,
            offset=offset,
        )

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
        return await self.content_repo.list_published(
            limit=limit,
            offset=offset,
            category=category,
            search=search,
        )

    async def count_published(self) -> int:
        """Count published YouTube content."""
        return await self.content_repo.count_published()


# =============================================================================
# Singleton
# =============================================================================

_youtube_content_service: Optional[YouTubeContentService] = None


def get_youtube_content_service() -> YouTubeContentService:
    """Get YouTube content service singleton."""
    global _youtube_content_service
    if _youtube_content_service is None:
        _youtube_content_service = YouTubeContentService()
    return _youtube_content_service
