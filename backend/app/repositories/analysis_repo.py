"""AnalysisRequest repository for Cosmos DB operations."""

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.db.cosmos import Containers, get_container
from app.models.analysis import AnalysisRequest
from app.models.enums import AnalysisStatus

logger = logging.getLogger(__name__)


class AnalysisRequestRepository:
    """Repository for AnalysisRequest CRUD operations in Cosmos DB."""

    def __init__(self):
        """Initialize repository with analysis_requests container."""
        self._container = None

    @property
    def container(self):
        """Lazy load container."""
        if self._container is None:
            # Note: Container was created with /id as partition key
            self._container = get_container(
                Containers.ANALYSIS_REQUESTS,
                partition_key_path="/id"
            )
        return self._container

    async def create(self, request: AnalysisRequest) -> AnalysisRequest:
        """
        Create a new analysis request.

        Args:
            request: AnalysisRequest to create

        Returns:
            Created AnalysisRequest
        """
        item = request.to_cosmos_item()
        self.container.create_item(body=item)
        logger.info(f"Created analysis request: {request.id} for user: {request.user_id}")
        return request

    async def get_by_id(self, request_id: str, user_id: str) -> Optional[AnalysisRequest]:
        """
        Get an analysis request by ID.

        Args:
            request_id: Request ID
            user_id: User ID (for authorization check, not partition key)

        Returns:
            AnalysisRequest if found, None otherwise
        """
        try:
            # Note: Container uses /id as partition key, not /user_id
            item = self.container.read_item(
                item=request_id,
                partition_key=request_id,  # Use request_id as partition key
            )
            # Verify user owns this request
            if item.get("user_id") != user_id:
                return None
            return AnalysisRequest.from_cosmos_item(item)
        except Exception as e:
            if "NotFound" in str(e) or "404" in str(e):
                return None
            raise

    async def get_by_id_cross_partition(self, request_id: str) -> Optional[AnalysisRequest]:
        """
        Get an analysis request by ID across all partitions.

        Note: This is less efficient than get_by_id with partition key.
        Use only when user_id is unknown.

        Args:
            request_id: Request ID

        Returns:
            AnalysisRequest if found, None otherwise
        """
        query = "SELECT * FROM c WHERE c.id = @id AND c.type = 'analysis_request'"
        parameters = [{"name": "@id", "value": request_id}]

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        if items:
            return AnalysisRequest.from_cosmos_item(items[0])
        return None

    async def list_all(
        self,
        page: int = 1,
        limit: int = 20,
        status: Optional[AnalysisStatus] = None,
    ) -> tuple[list[AnalysisRequest], int]:
        """
        List all analysis requests (for all users).

        Args:
            page: Page number (1-indexed)
            limit: Max items to return
            status: Optional status filter

        Returns:
            Tuple of (requests list, total count)
        """
        offset = (page - 1) * limit

        # Build WHERE clause
        where_clause = "c.type = 'analysis_request'"
        parameters: list = []

        if status:
            where_clause += " AND c.status = @status"
            parameters.append({"name": "@status", "value": status.value})

        # Count query
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_result = list(self.container.query_items(
            query=count_query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))
        total = count_result[0] if count_result else 0

        # Data query with pagination
        query = f"""
            SELECT * FROM c
            WHERE {where_clause}
            ORDER BY c.created_at DESC
            OFFSET @offset LIMIT @limit
        """
        parameters.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ])

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        requests = [AnalysisRequest.from_cosmos_item(item) for item in items]
        return requests, total

    async def list_by_user(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[AnalysisStatus] = None,
    ) -> tuple[list[AnalysisRequest], int]:
        """
        List analysis requests for a user.

        Args:
            user_id: User ID (partition key)
            page: Page number (1-indexed)
            limit: Max items to return
            status: Optional status filter

        Returns:
            Tuple of (requests list, total count)
        """
        offset = (page - 1) * limit

        # Build WHERE clause
        where_clause = "c.user_id = @user_id AND c.type = 'analysis_request'"
        parameters = [{"name": "@user_id", "value": user_id}]

        if status:
            where_clause += " AND c.status = @status"
            parameters.append({"name": "@status", "value": status.value})

        # Count query (cross-partition since container uses /id as partition key)
        count_query = f"SELECT VALUE COUNT(1) FROM c WHERE {where_clause}"
        count_result = list(self.container.query_items(
            query=count_query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))
        total = count_result[0] if count_result else 0

        # Data query with pagination
        query = f"""
            SELECT * FROM c
            WHERE {where_clause}
            ORDER BY c.created_at DESC
            OFFSET @offset LIMIT @limit
        """
        parameters.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ])

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        requests = [AnalysisRequest.from_cosmos_item(item) for item in items]
        return requests, total

    async def update(self, request: AnalysisRequest) -> AnalysisRequest:
        """
        Update an analysis request.

        Args:
            request: AnalysisRequest with updated values

        Returns:
            Updated AnalysisRequest
        """
        request.updated_at = datetime.utcnow()
        item = request.to_cosmos_item()

        self.container.upsert_item(body=item)
        logger.info(f"Updated analysis request: {request.id}, status: {request.status.value}")
        return request

    async def remove_content_id(
        self,
        request_id: str,
        user_id: str,
        content_id: str,
    ) -> Optional[AnalysisRequest]:
        """
        Remove a content ID from an analysis request's content_ids list.

        Args:
            request_id: Analysis request ID
            user_id: User ID (partition key)
            content_id: Content ID to remove

        Returns:
            Updated AnalysisRequest if found and updated
        """
        request = await self.get_by_id(request_id, user_id)
        if not request:
            return None

        if content_id in request.content_ids:
            request.content_ids.remove(content_id)
            return await self.update(request)

        return request

    async def update_status(
        self,
        request_id: str,
        user_id: str,
        new_status: AnalysisStatus,
        message: Optional[str] = None,
        progress: Optional[int] = None,
    ) -> Optional[AnalysisRequest]:
        """
        Update the status of an analysis request.

        Args:
            request_id: Request ID
            user_id: User ID (partition key)
            new_status: New status
            message: Optional status message
            progress: Optional progress percentage

        Returns:
            Updated AnalysisRequest if found
        """
        request = await self.get_by_id(request_id, user_id)
        if not request:
            return None

        request.update_status(new_status, message, progress)
        return await self.update(request)

    async def find_duplicate(
        self,
        user_id: str,
        source_url: str,
        within_hours: int = 24,
    ) -> Optional[AnalysisRequest]:
        """
        Find a duplicate analysis request (same URL within time window).

        Args:
            user_id: User ID
            source_url: Source URL to check
            within_hours: Time window in hours

        Returns:
            Existing AnalysisRequest if found
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=within_hours)

        query = """
            SELECT * FROM c
            WHERE c.user_id = @user_id
            AND c.source_url = @source_url
            AND c.created_at >= @cutoff
            AND c.type = 'analysis_request'
            ORDER BY c.created_at DESC
        """
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@source_url", "value": source_url},
            {"name": "@cutoff", "value": cutoff_time.isoformat()},
        ]

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        if items:
            return AnalysisRequest.from_cosmos_item(items[0])
        return None

    async def get_pending_requests(
        self,
        limit: int = 10,
    ) -> list[AnalysisRequest]:
        """
        Get pending analysis requests for processing.

        Args:
            limit: Max items to return

        Returns:
            List of pending requests
        """
        query = """
            SELECT * FROM c
            WHERE c.status IN ('pending', 'queued')
            AND c.type = 'analysis_request'
            ORDER BY c.created_at ASC
            OFFSET 0 LIMIT @limit
        """
        parameters = [{"name": "@limit", "value": limit}]

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))

        return [AnalysisRequest.from_cosmos_item(item) for item in items]

    async def delete(self, request_id: str, user_id: str) -> bool:
        """
        Delete an analysis request.

        Args:
            request_id: Request ID
            user_id: User ID (for authorization check)

        Returns:
            True if deleted, False if not found
        """
        try:
            # First verify user owns this request
            request = await self.get_by_id(request_id, user_id)
            if not request:
                return False

            # Container uses /id as partition key
            self.container.delete_item(
                item=request_id,
                partition_key=request_id,
            )
            logger.info(f"Deleted analysis request: {request_id}")
            return True
        except Exception as e:
            if "NotFound" in str(e) or "404" in str(e):
                return False
            raise

    async def delete_by_id(self, request_id: str) -> bool:
        """
        Delete an analysis request by ID without user verification.

        Note: Use this only when ownership has already been verified
        at a higher level (e.g., through content ownership).

        Args:
            request_id: Request ID

        Returns:
            True if deleted, False if not found
        """
        try:
            # Container uses /id as partition key
            self.container.delete_item(
                item=request_id,
                partition_key=request_id,
            )
            logger.info(f"Deleted analysis request: {request_id}")
            return True
        except Exception as e:
            if "NotFound" in str(e) or "404" in str(e):
                logger.warning(f"Analysis request not found for deletion: {request_id}")
                return False
            logger.error(f"Error deleting analysis request {request_id}: {e}")
            raise


# Singleton instance
_analysis_repo: Optional[AnalysisRequestRepository] = None


def get_analysis_repo() -> AnalysisRequestRepository:
    """Get analysis request repository singleton."""
    global _analysis_repo
    if _analysis_repo is None:
        _analysis_repo = AnalysisRequestRepository()
    return _analysis_repo
