"""
GeneratedAsset repository for asset CRUD operations.

Per tasks.md T107: Create asset_repo.py with CRUD operations.
Partition Key: content_id
Container: generated_assets
"""

import logging
from typing import Optional
from uuid import UUID

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.db.cosmos import get_container
from app.models.enums import AssetType
from app.models.generated_asset import GeneratedAsset

logger = logging.getLogger(__name__)

# Container name for generated assets
CONTAINER_NAME = "generated_assets"

# Type alias for Cosmos DB parameters
CosmosParams = list[dict[str, object]]


class AssetRepository:
    """
    Repository for GeneratedAsset documents in Cosmos DB.

    Methods:
    - create(): Create a new asset record
    - get_by_id(): Get asset by ID
    - list_by_content_id(): List all assets for a content item
    - list_by_type(): List assets by type for a content item
    - delete(): Delete an asset
    """

    def __init__(self):
        self._container = None

    @property
    def container(self):
        """Lazy initialization of container."""
        if self._container is None:
            self._container = get_container(CONTAINER_NAME)
        return self._container

    async def create(self, asset: GeneratedAsset) -> GeneratedAsset:
        """
        Create a new generated asset record.

        Args:
            asset: GeneratedAsset model to persist

        Returns:
            Created GeneratedAsset
        """
        doc = asset.to_cosmos_document()

        logger.info(
            "Creating generated asset",
            extra={
                "asset_id": str(asset.id),
                "content_id": str(asset.content_id),
                "asset_type": asset.asset_type,
                "run_id": str(asset.run_id),
            }
        )

        result = self.container.create_item(body=doc)
        return GeneratedAsset.from_cosmos_document(result)

    async def get_by_id(
        self,
        asset_id: UUID,
        content_id: Optional[UUID] = None
    ) -> Optional[GeneratedAsset]:
        """
        Get a generated asset by ID.

        Args:
            asset_id: Asset UUID
            content_id: Optional content ID (partition key) for efficient lookup

        Returns:
            GeneratedAsset if found, None otherwise
        """
        try:
            if content_id:
                result = self.container.read_item(
                    item=str(asset_id),
                    partition_key=str(content_id)
                )
                return GeneratedAsset.from_cosmos_document(result)
            else:
                # Cross-partition query
                query = "SELECT * FROM c WHERE c.id = @id"
                params: CosmosParams = [{"name": "@id", "value": str(asset_id)}]

                results = list(self.container.query_items(
                    query=query,
                    parameters=params,
                    enable_cross_partition_query=True
                ))

                if results:
                    return GeneratedAsset.from_cosmos_document(results[0])
                return None

        except CosmosResourceNotFoundError:
            return None

    async def list_by_content_id(
        self,
        content_id: UUID,
        limit: int = 50,
    ) -> list[GeneratedAsset]:
        """
        List all generated assets for a content item.

        Args:
            content_id: Content UUID
            limit: Maximum results

        Returns:
            List of GeneratedAssets
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.content_id = @content_id
            ORDER BY c.created_at DESC
        """
        params = [
            {"name": "@limit", "value": limit},
            {"name": "@content_id", "value": str(content_id)},
        ]

        results = list(self.container.query_items(
            query=query,
            parameters=params,
            partition_key=str(content_id)
        ))

        return [GeneratedAsset.from_cosmos_document(doc) for doc in results]

    async def list_by_type(
        self,
        content_id: UUID,
        asset_type: AssetType,
    ) -> list[GeneratedAsset]:
        """
        List assets of a specific type for a content item.

        Args:
            content_id: Content UUID
            asset_type: Type of asset (thumbnail, preview, etc.)

        Returns:
            List of GeneratedAssets
        """
        query = """
            SELECT * FROM c
            WHERE c.content_id = @content_id AND c.asset_type = @type
            ORDER BY c.created_at DESC
        """
        params: CosmosParams = [
            {"name": "@content_id", "value": str(content_id)},
            {"name": "@type", "value": asset_type.value},
        ]

        results = list(self.container.query_items(
            query=query,
            parameters=params,
            partition_key=str(content_id)
        ))

        return [GeneratedAsset.from_cosmos_document(doc) for doc in results]

    async def list_by_run_id(self, run_id: UUID) -> list[GeneratedAsset]:
        """
        List all assets created by a pipeline run.

        Args:
            run_id: Pipeline run UUID

        Returns:
            List of GeneratedAssets
        """
        query = "SELECT * FROM c WHERE c.run_id = @run_id"
        params: CosmosParams = [{"name": "@run_id", "value": str(run_id)}]

        results = list(self.container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True
        ))

        return [GeneratedAsset.from_cosmos_document(doc) for doc in results]

    async def delete(self, asset_id: UUID, content_id: UUID) -> bool:
        """
        Delete a generated asset.

        Args:
            asset_id: Asset UUID
            content_id: Content UUID (partition key)

        Returns:
            True if deleted, False if not found
        """
        try:
            self.container.delete_item(
                item=str(asset_id),
                partition_key=str(content_id)
            )

            logger.info(
                "Deleted generated asset",
                extra={
                    "asset_id": str(asset_id),
                    "content_id": str(content_id),
                }
            )

            return True
        except CosmosResourceNotFoundError:
            return False

    async def delete_by_content_id(self, content_id: UUID) -> int:
        """
        Delete all assets for a content item.

        Args:
            content_id: Content UUID

        Returns:
            Number of assets deleted
        """
        assets = await self.list_by_content_id(content_id, limit=1000)
        deleted_count = 0

        for asset in assets:
            if await self.delete(asset.id, content_id):
                deleted_count += 1

        logger.info(
            "Deleted all assets for content",
            extra={
                "content_id": str(content_id),
                "deleted_count": deleted_count,
            }
        )

        return deleted_count


# Singleton instance
_asset_repo: Optional[AssetRepository] = None


def get_asset_repository() -> AssetRepository:
    """Get or create the asset repository singleton."""
    global _asset_repo
    if _asset_repo is None:
        _asset_repo = AssetRepository()
    return _asset_repo
