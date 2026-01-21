"""
Pipeline repository for PipelineRun CRUD operations.

Per tasks.md T105: Create pipeline_repo.py with CRUD operations.
Partition Key: content_id (or triggered_by for orphan runs)
Container: pipeline_runs
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, cast
from uuid import UUID

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.db.cosmos import get_container
from app.models.enums import PipelineStatus, PipelineType
from app.models.pipeline_run import InvalidStatusTransitionError, PipelineRun

logger = logging.getLogger(__name__)

# Container name for pipeline runs
CONTAINER_NAME = "pipeline_runs"

# Type alias for Cosmos DB parameters
CosmosParams = list[dict[str, object]]


class PipelineRepository:
    """
    Repository for PipelineRun documents in Cosmos DB.

    Methods:
    - create(): Create a new pipeline run
    - get_by_id(): Get a pipeline run by ID
    - update_status(): Update pipeline status with validation
    - list_by_content_id(): List all runs for a content item
    - list_by_type(): List runs by pipeline type
    - list_by_user(): List runs triggered by a user
    """

    def __init__(self):
        self._container = None

    @property
    def container(self):
        """Lazy initialization of container."""
        if self._container is None:
            self._container = get_container(CONTAINER_NAME)
        return self._container

    async def create(self, run: PipelineRun) -> PipelineRun:
        """
        Create a new pipeline run in Cosmos DB.

        Args:
            run: PipelineRun model to persist

        Returns:
            Created PipelineRun with any server-side modifications
        """
        doc = run.to_cosmos_document()

        logger.info(
            "Creating pipeline run",
            extra={
                "run_id": str(run.id),
                "pipeline_type": run.pipeline_type,
                "correlation_id": run.correlation_id,
            }
        )

        result = self.container.create_item(body=doc)
        return PipelineRun.from_cosmos_document(result)

    async def get_by_id(
        self,
        run_id: UUID,
        partition_key: Optional[str] = None
    ) -> Optional[PipelineRun]:
        """
        Get a pipeline run by ID.

        Args:
            run_id: Pipeline run UUID
            partition_key: Optional partition key for efficient lookup

        Returns:
            PipelineRun if found, None otherwise
        """
        try:
            # If partition key not provided, query across partitions
            if partition_key:
                result = self.container.read_item(
                    item=str(run_id),
                    partition_key=partition_key
                )
                return PipelineRun.from_cosmos_document(result)
            else:
                # Cross-partition query
                query = "SELECT * FROM c WHERE c.id = @run_id"
                params: CosmosParams = [{"name": "@run_id", "value": str(run_id)}]

                results = list(self.container.query_items(
                    query=query,
                    parameters=params,
                    enable_cross_partition_query=True
                ))

                if results:
                    return PipelineRun.from_cosmos_document(results[0])
                return None

        except CosmosResourceNotFoundError:
            return None

    async def update_status(
        self,
        run_id: UUID,
        new_status: PipelineStatus,
        partition_key: Optional[str] = None,
        output_summary: Optional[dict[str, Any]] = None,
        error_details: Optional[dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> PipelineRun:
        """
        Update pipeline run status with state machine validation.

        Args:
            run_id: Pipeline run UUID
            new_status: Target status
            partition_key: Partition key for lookup
            output_summary: Results summary (for completed status)
            error_details: Error information (for failed status)
            job_id: Azure Container Apps Job ID

        Returns:
            Updated PipelineRun

        Raises:
            InvalidStatusTransitionError: If transition is not valid
            ValueError: If run not found
        """
        run = await self.get_by_id(run_id, partition_key)
        if not run:
            raise ValueError(f"Pipeline run not found: {run_id}")

        # Validate state transition
        if not run.can_transition_to(new_status):
            raise InvalidStatusTransitionError(run.status, new_status)

        # Build update
        now = datetime.now(timezone.utc)
        update_doc = run.to_cosmos_document()
        update_doc["status"] = new_status.value

        # Update timestamps based on status
        if new_status == PipelineStatus.RUNNING:
            update_doc["started_at"] = now.isoformat()
            if job_id:
                update_doc["job_id"] = job_id
        elif new_status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED):
            update_doc["completed_at"] = now.isoformat()
            if output_summary:
                update_doc["output_summary"] = output_summary
            if error_details:
                update_doc["error_details"] = error_details

        logger.info(
            "Updating pipeline status",
            extra={
                "run_id": str(run_id),
                "old_status": run.status,
                "new_status": new_status.value,
                "correlation_id": run.correlation_id,
            }
        )

        result = self.container.upsert_item(body=update_doc)
        return PipelineRun.from_cosmos_document(result)

    async def increment_attempt(self, run_id: UUID, partition_key: Optional[str] = None) -> PipelineRun:
        """
        Increment attempt number for retry and reset status to pending.

        Args:
            run_id: Pipeline run UUID
            partition_key: Partition key for lookup

        Returns:
            Updated PipelineRun with incremented attempt
        """
        run = await self.get_by_id(run_id, partition_key)
        if not run:
            raise ValueError(f"Pipeline run not found: {run_id}")

        # Only failed runs can be retried
        if run.status != PipelineStatus.FAILED:
            raise InvalidStatusTransitionError(run.status, PipelineStatus.PENDING)

        update_doc = run.to_cosmos_document()
        update_doc["status"] = PipelineStatus.PENDING.value
        update_doc["attempt_number"] = run.attempt_number + 1
        update_doc["started_at"] = None
        update_doc["completed_at"] = None
        update_doc["error_details"] = None

        logger.info(
            "Retrying pipeline",
            extra={
                "run_id": str(run_id),
                "attempt_number": update_doc["attempt_number"],
                "correlation_id": run.correlation_id,
            }
        )

        result = self.container.upsert_item(body=update_doc)
        return PipelineRun.from_cosmos_document(result)

    async def list_by_content_id(
        self,
        content_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PipelineRun], int]:
        """
        List all pipeline runs for a content item.

        Args:
            content_id: Content UUID
            limit: Maximum results to return
            offset: Number of results to skip

        Returns:
            Tuple of (list of PipelineRuns, total count)
        """
        # Count query - SELECT VALUE returns scalar directly
        count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.content_id = @content_id"
        count_params: CosmosParams = [{"name": "@content_id", "value": str(content_id)}]

        count_results = list(self.container.query_items(
            query=count_query,
            parameters=count_params,
            partition_key=str(content_id)
        ))
        # SELECT VALUE COUNT returns int directly, not a dict
        total_count: int = cast(int, count_results[0]) if count_results else 0

        # Data query with pagination
        query = """
            SELECT * FROM c
            WHERE c.content_id = @content_id
            ORDER BY c.created_at DESC
            OFFSET @offset LIMIT @limit
        """
        params: CosmosParams = [
            {"name": "@content_id", "value": str(content_id)},
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]

        results = list(self.container.query_items(
            query=query,
            parameters=params,
            partition_key=str(content_id)
        ))

        runs = [PipelineRun.from_cosmos_document(doc) for doc in results]
        return runs, total_count

    async def list_by_type(
        self,
        pipeline_type: PipelineType,
        status: Optional[PipelineStatus] = None,
        limit: int = 50,
    ) -> list[PipelineRun]:
        """
        List pipeline runs by type, optionally filtered by status.

        Args:
            pipeline_type: Type of pipeline
            status: Optional status filter
            limit: Maximum results

        Returns:
            List of PipelineRuns
        """
        query = "SELECT TOP @limit * FROM c WHERE c.pipeline_type = @type"
        params = [
            {"name": "@limit", "value": limit},
            {"name": "@type", "value": pipeline_type.value},
        ]

        if status:
            query += " AND c.status = @status"
            params.append({"name": "@status", "value": status.value})

        query += " ORDER BY c.created_at DESC"

        results = list(self.container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True
        ))

        return [PipelineRun.from_cosmos_document(doc) for doc in results]

    async def list_by_user(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PipelineRun]:
        """
        List pipeline runs triggered by a user.

        Args:
            user_id: User UUID
            limit: Maximum results
            offset: Number to skip

        Returns:
            List of PipelineRuns
        """
        query = """
            SELECT * FROM c
            WHERE c.triggered_by = @user_id
            ORDER BY c.created_at DESC
            OFFSET @offset LIMIT @limit
        """
        params = [
            {"name": "@user_id", "value": str(user_id)},
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]

        results = list(self.container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True
        ))

        return [PipelineRun.from_cosmos_document(doc) for doc in results]


# Singleton instance
_pipeline_repo: Optional[PipelineRepository] = None


def get_pipeline_repository() -> PipelineRepository:
    """Get or create the pipeline repository singleton."""
    global _pipeline_repo
    if _pipeline_repo is None:
        _pipeline_repo = PipelineRepository()
    return _pipeline_repo
