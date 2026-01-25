"""Content repository for Cosmos DB operations."""

import logging
from typing import Optional

from app.db.cosmos import Containers, get_container
from app.models.content import Content
from app.models.enums import ContentStatus

logger = logging.getLogger(__name__)


class ContentRepository:
    """Repository for Content CRUD operations in Cosmos DB."""

    def __init__(self):
        """Initialize repository with contents container."""
        self._container = None

    @property
    def container(self):
        """Lazy load container."""
        if self._container is None:
            self._container = get_container(Containers.CONTENTS)
        return self._container

    async def create(self, content: Content) -> Content:
        """
        Create a new content item.

        Args:
            content: Content model to create

        Returns:
            Created content with ID
        """
        item = content.to_cosmos_item()
        self.container.create_item(body=item)
        logger.info(f"Created content: {content.id}")
        return content

    async def get_by_id(self, content_id: str, contributor_id: str) -> Optional[Content]:
        """
        Get content by ID.

        Args:
            content_id: Content ID
            contributor_id: Contributor ID (partition key)

        Returns:
            Content if found, None otherwise
        """
        try:
            item = self.container.read_item(
                item=content_id,
                partition_key=contributor_id,
            )
            return Content.from_cosmos_item(item)
        except Exception as e:
            if "NotFound" in str(e):
                return None
            raise

    async def get_by_id_cross_partition(self, content_id: str) -> Optional[Content]:
        """
        Get content by ID (cross-partition query).

        Use this when contributor_id is unknown.
        Less efficient than partition-key query.

        Args:
            content_id: Content ID

        Returns:
            Content if found, None otherwise
        """
        query = "SELECT * FROM c WHERE c.id = @id"
        parameters = [{"name": "@id", "value": content_id}]

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        if items:
            return Content.from_cosmos_item(items[0])
        return None

    async def update(self, content: Content) -> Content:
        """
        Update existing content.

        Args:
            content: Content to update

        Returns:
            Updated content
        """
        item = content.to_cosmos_item()
        self.container.replace_item(
            item=content.id,
            body=item,
        )
        logger.info(f"Updated content: {content.id}")
        return content

    async def delete(self, content_id: str, contributor_id: str) -> bool:
        """
        Delete content by ID.

        Args:
            content_id: Content ID
            contributor_id: Contributor ID (partition key)

        Returns:
            True if deleted, False if not found
        """
        try:
            logger.info(f"Attempting to delete content: {content_id} with partition key: {contributor_id}")
            self.container.delete_item(
                item=content_id,
                partition_key=contributor_id,
            )
            logger.info(f"Successfully deleted content: {content_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting content {content_id}: {e}")
            if "NotFound" in str(e) or "404" in str(e):
                logger.warning(f"Content not found for deletion: {content_id}")
                return False
            raise

    async def delete_cross_partition(self, content_id: str) -> bool:
        """
        Delete content by ID.

        Note: Container uses /id as partition key (default), so content_id is the partition key.

        Args:
            content_id: Content ID (also the partition key)

        Returns:
            True if deleted, False if not found
        """
        try:
            logger.info(f"Attempting to delete content: {content_id}")
            # Container uses /id as partition key, so content_id IS the partition key
            self.container.delete_item(
                item=content_id,
                partition_key=content_id,
            )
            logger.info(f"Successfully deleted content: {content_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting content {content_id}: {e}")
            if "NotFound" in str(e) or "404" in str(e):
                logger.warning(f"Content not found for deletion: {content_id}")
                return False
            raise

    async def list_by_contributor(
        self,
        contributor_id: str,
        status: Optional[ContentStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Content], int]:
        """
        List content by contributor.

        Args:
            contributor_id: Contributor ID (partition key)
            status: Filter by status (optional)
            limit: Max items to return
            offset: Number of items to skip

        Returns:
            Tuple of (content list, total count)
        """
        # Build query with pagination
        if status:
            query = f"SELECT * FROM c WHERE c.contributor_id = @contributor_id AND c.status = @status ORDER BY c.created_at DESC OFFSET {offset} LIMIT {limit}"
            count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.contributor_id = @contributor_id AND c.status = @status"
            parameters = [
                {"name": "@contributor_id", "value": contributor_id},
                {"name": "@status", "value": status.value},
            ]
        else:
            query = f"SELECT * FROM c WHERE c.contributor_id = @contributor_id ORDER BY c.created_at DESC OFFSET {offset} LIMIT {limit}"
            count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.contributor_id = @contributor_id"
            parameters = [{"name": "@contributor_id", "value": contributor_id}]

        # Get total count
        count_result = list(self.container.query_items(
            query=count_query,
            parameters=parameters,
            partition_key=contributor_id,
        ))
        total = count_result[0] if count_result else 0

        # Get items with pagination
        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            partition_key=contributor_id,
        ))

        contents = [Content.from_cosmos_item(item) for item in items]
        return contents, total

    async def list_all(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> tuple[list[Content], int]:
        """
        List all content across all contributors (cross-partition).

        Args:
            limit: Max items to return
            offset: Number of items to skip
            status: Optional status filter

        Returns:
            Tuple of (content list, total count)
        """
        # Build query with optional status filter
        if status:
            query = f"""
                SELECT * FROM c
                WHERE c.status = @status
                ORDER BY c.created_at DESC
                OFFSET {offset} LIMIT {limit}
            """
            count_query = """
                SELECT VALUE COUNT(1) FROM c
                WHERE c.status = @status
            """
            parameters = [{"name": "@status", "value": status}]

            # Get total count
            count_result = list(self.container.query_items(
                query=count_query,
                parameters=parameters,
                enable_cross_partition_query=True,
            ))
            total = count_result[0] if count_result else 0

            # Get items with pagination
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            ))
        else:
            # No parameters needed
            query = f"SELECT * FROM c ORDER BY c.created_at DESC OFFSET {offset} LIMIT {limit}"
            count_query = "SELECT VALUE COUNT(1) FROM c"

            # Get total count
            count_result = list(self.container.query_items(
                query=count_query,
                enable_cross_partition_query=True,
            ))
            total = count_result[0] if count_result else 0

            # Get items with pagination
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True,
            ))

        contents = [Content.from_cosmos_item(item) for item in items]
        return contents, total

    async def list_published(
        self,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
    ) -> tuple[list[Content], int]:
        """
        List all published content (cross-partition).

        Args:
            limit: Max items to return
            offset: Number of items to skip
            category: Filter by category (optional)

        Returns:
            Tuple of (content list, total count)
        """
        # Build query with pagination
        if category:
            query = f"""
                SELECT * FROM c
                WHERE c.status = @status
                AND ARRAY_CONTAINS(c.categories, @category)
                ORDER BY c.published_at DESC
                OFFSET {offset} LIMIT {limit}
            """
            count_query = """
                SELECT VALUE COUNT(1) FROM c
                WHERE c.status = @status
                AND ARRAY_CONTAINS(c.categories, @category)
            """
            parameters = [
                {"name": "@status", "value": ContentStatus.PUBLISHED.value},
                {"name": "@category", "value": category},
            ]
        else:
            query = f"SELECT * FROM c WHERE c.status = @status ORDER BY c.published_at DESC OFFSET {offset} LIMIT {limit}"
            count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.status = @status"
            parameters = [{"name": "@status", "value": ContentStatus.PUBLISHED.value}]

        # Get total count
        count_result = list(self.container.query_items(
            query=count_query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))
        total = count_result[0] if count_result else 0

        # Get items with pagination
        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        contents = [Content.from_cosmos_item(item) for item in items]
        return contents, total

    async def search(
        self,
        query_text: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Content], int]:
        """
        Search content by title, description, or categories.

        Uses Cosmos SQL CONTAINS for text search.

        Args:
            query_text: Search query
            limit: Max items to return
            offset: Number of items to skip

        Returns:
            Tuple of (content list, total count)
        """
        # Build search query with pagination
        search_lower = query_text.lower()
        query = f"""
            SELECT * FROM c
            WHERE c.status = @status
            AND (
                CONTAINS(LOWER(c.title), @search)
                OR CONTAINS(LOWER(c.description), @search)
            )
            ORDER BY c.published_at DESC
            OFFSET {offset} LIMIT {limit}
        """
        count_query = """
            SELECT VALUE COUNT(1) FROM c
            WHERE c.status = @status
            AND (
                CONTAINS(LOWER(c.title), @search)
                OR CONTAINS(LOWER(c.description), @search)
            )
        """
        parameters = [
            {"name": "@status", "value": ContentStatus.PUBLISHED.value},
            {"name": "@search", "value": search_lower},
        ]

        # Get total count
        count_result = list(self.container.query_items(
            query=count_query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))
        total = count_result[0] if count_result else 0

        # Get items
        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        contents = [Content.from_cosmos_item(item) for item in items]
        return contents, total


# Singleton instance
_content_repo: Optional[ContentRepository] = None


def get_content_repo() -> ContentRepository:
    """Get content repository singleton."""
    global _content_repo
    if _content_repo is None:
        _content_repo = ContentRepository()
    return _content_repo
