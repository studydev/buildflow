"""Repository for GeneratedAsset operations.

Per tasks.md T601: CRUD operations for generated assets.
"""

import logging
from typing import List, Optional
from uuid import UUID

from app.db.cosmos import get_cosmos_client
from app.models.enums import AssetType
from app.models.generated_asset import GeneratedAsset

logger = logging.getLogger(__name__)

CONTAINER_NAME = "generated_assets"


class GeneratedAssetRepository:
    """
    Repository for GeneratedAsset documents in Cosmos DB.
    
    Container: generated_assets
    Partition Key: content_id
    """
    
    def __init__(self):
        """Initialize repository."""
        self._container = None
    
    @property
    def container(self):
        """Get container client, lazy loaded."""
        if self._container is None:
            client = get_cosmos_client()
            database = client.get_database_client("buildflow")
            self._container = database.get_container_client(CONTAINER_NAME)
        return self._container
    
    async def create(self, asset: GeneratedAsset) -> GeneratedAsset:
        """
        Create a new generated asset record.
        
        Args:
            asset: GeneratedAsset model
            
        Returns:
            Created asset
        """
        document = asset.to_cosmos_document()
        
        self.container.create_item(body=document)
        
        logger.info(
            f"Created GeneratedAsset: {asset.id} for content {asset.content_id}",
            extra={"asset_type": asset.asset_type.value}
        )
        
        return asset
    
    async def get_by_id(
        self,
        asset_id: UUID,
        content_id: UUID,
    ) -> Optional[GeneratedAsset]:
        """
        Get asset by ID.
        
        Args:
            asset_id: Asset UUID
            content_id: Content UUID (partition key)
            
        Returns:
            GeneratedAsset or None
        """
        try:
            document = self.container.read_item(
                item=str(asset_id),
                partition_key=str(content_id),
            )
            return GeneratedAsset.from_cosmos_document(document)
        except Exception as e:
            if "NotFound" in str(e):
                return None
            raise
    
    async def get_by_content_id(
        self,
        content_id: UUID,
    ) -> List[GeneratedAsset]:
        """
        Get all assets for a content item.
        
        Args:
            content_id: Content UUID
            
        Returns:
            List of GeneratedAsset
        """
        query = "SELECT * FROM c WHERE c.content_id = @content_id"
        params = [{"name": "@content_id", "value": str(content_id)}]
        
        items = list(self.container.query_items(
            query=query,
            parameters=params,
            partition_key=str(content_id),
        ))
        
        return [GeneratedAsset.from_cosmos_document(item) for item in items]
    
    async def get_by_content_and_type(
        self,
        content_id: UUID,
        asset_type: AssetType,
    ) -> Optional[GeneratedAsset]:
        """
        Get a specific asset type for a content item.
        
        Args:
            content_id: Content UUID
            asset_type: Asset type
            
        Returns:
            GeneratedAsset or None
        """
        query = """
            SELECT * FROM c 
            WHERE c.content_id = @content_id 
            AND c.asset_type = @asset_type
        """
        params = [
            {"name": "@content_id", "value": str(content_id)},
            {"name": "@asset_type", "value": asset_type.value},
        ]
        
        items = list(self.container.query_items(
            query=query,
            parameters=params,
            partition_key=str(content_id),
        ))
        
        if items:
            return GeneratedAsset.from_cosmos_document(items[0])
        return None
    
    async def update(self, asset: GeneratedAsset) -> GeneratedAsset:
        """
        Update an existing asset.
        
        Args:
            asset: GeneratedAsset with updated fields
            
        Returns:
            Updated asset
        """
        document = asset.to_cosmos_document()
        
        self.container.upsert_item(body=document)
        
        logger.info(f"Updated GeneratedAsset: {asset.id}")
        
        return asset
    
    async def delete(
        self,
        asset_id: UUID,
        content_id: UUID,
    ) -> bool:
        """
        Delete an asset.
        
        Args:
            asset_id: Asset UUID
            content_id: Content UUID (partition key)
            
        Returns:
            True if deleted
        """
        try:
            self.container.delete_item(
                item=str(asset_id),
                partition_key=str(content_id),
            )
            logger.info(f"Deleted GeneratedAsset: {asset_id}")
            return True
        except Exception as e:
            if "NotFound" in str(e):
                return False
            raise
    
    async def delete_by_content_id(self, content_id: UUID) -> int:
        """
        Delete all assets for a content item.
        
        Args:
            content_id: Content UUID
            
        Returns:
            Number of deleted assets
        """
        assets = await self.get_by_content_id(content_id)
        
        deleted = 0
        for asset in assets:
            if await self.delete(asset.id, content_id):
                deleted += 1
        
        logger.info(f"Deleted {deleted} assets for content {content_id}")
        return deleted


# Singleton
_repo: Optional[GeneratedAssetRepository] = None


def get_generated_asset_repo() -> GeneratedAssetRepository:
    """Get the generated asset repository singleton."""
    global _repo
    if _repo is None:
        _repo = GeneratedAssetRepository()
    return _repo
