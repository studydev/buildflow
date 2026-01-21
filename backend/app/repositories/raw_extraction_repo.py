"""
RawExtraction repository for IMMUTABLE raw extraction documents.

Per tasks.md T106: Create raw_extraction_repo.py (immutable - no update).
Partition Key: source_url_hash
Container: raw_extractions

IMPORTANT: This repository does NOT provide an update() method.
RawExtraction documents are immutable once created.
"""

import hashlib
import logging
from typing import Optional, cast
from uuid import UUID

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.db.cosmos import get_container
from app.models.raw_extraction import ImmutableRecordError, RawExtraction

logger = logging.getLogger(__name__)

# Container name for raw extractions
CONTAINER_NAME = "raw_extractions"

# Type alias for Cosmos DB parameters
CosmosParams = list[dict[str, object]]


def compute_source_url_hash(source_url: str) -> str:
    """
    Compute SHA256 hash of source URL for partition key and deduplication.
    
    Args:
        source_url: GitHub repository URL
        
    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(source_url.encode("utf-8")).hexdigest()


class RawExtractionRepository:
    """
    Repository for RawExtraction documents in Cosmos DB.
    
    IMMUTABLE: This repository does NOT provide update() method.
    
    Methods:
    - create(): Create a new extraction record
    - get_by_id(): Get extraction by ID
    - get_by_source_url_hash(): Get by URL hash
    - get_by_source_url(): Get by source URL (convenience method)
    - exists(): Check if extraction exists for URL
    """
    
    def __init__(self):
        self._container = None
    
    @property
    def container(self):
        """Lazy initialization of container."""
        if self._container is None:
            self._container = get_container(CONTAINER_NAME)
        return self._container
    
    async def create(self, extraction: RawExtraction) -> RawExtraction:
        """
        Create a new raw extraction record.
        
        Args:
            extraction: RawExtraction model to persist
            
        Returns:
            Created RawExtraction
        """
        doc = extraction.to_cosmos_document()
        
        logger.info(
            "Creating raw extraction",
            extra={
                "extraction_id": str(extraction.id),
                "source_url_hash": extraction.source_url_hash,
                "run_id": str(extraction.run_id),
            }
        )
        
        result = self.container.create_item(body=doc)
        return RawExtraction.from_cosmos_document(result)
    
    async def get_by_id(
        self,
        extraction_id: UUID,
        source_url_hash: Optional[str] = None
    ) -> Optional[RawExtraction]:
        """
        Get a raw extraction by ID.
        
        Args:
            extraction_id: Extraction UUID
            source_url_hash: Optional partition key for efficient lookup
            
        Returns:
            RawExtraction if found, None otherwise
        """
        try:
            if source_url_hash:
                result = self.container.read_item(
                    item=str(extraction_id),
                    partition_key=source_url_hash
                )
                return RawExtraction.from_cosmos_document(result)
            else:
                # Cross-partition query
                query = "SELECT * FROM c WHERE c.id = @id"
                params: CosmosParams = [{"name": "@id", "value": str(extraction_id)}]
                
                results = list(self.container.query_items(
                    query=query,
                    parameters=params,
                    enable_cross_partition_query=True
                ))
                
                if results:
                    return RawExtraction.from_cosmos_document(results[0])
                return None
                
        except CosmosResourceNotFoundError:
            return None
    
    async def get_by_source_url_hash(
        self,
        source_url_hash: str
    ) -> Optional[RawExtraction]:
        """
        Get the most recent extraction for a source URL hash.
        
        Args:
            source_url_hash: SHA256 hash of source URL
            
        Returns:
            Most recent RawExtraction if found, None otherwise
        """
        query = """
            SELECT TOP 1 * FROM c 
            WHERE c.source_url_hash = @hash 
            ORDER BY c.extracted_at DESC
        """
        params: CosmosParams = [{"name": "@hash", "value": source_url_hash}]
        
        results = list(self.container.query_items(
            query=query,
            parameters=params,
            partition_key=source_url_hash
        ))
        
        if results:
            return RawExtraction.from_cosmos_document(results[0])
        return None
    
    async def get_by_source_url(self, source_url: str) -> Optional[RawExtraction]:
        """
        Get the most recent extraction for a source URL.
        
        Convenience method that computes the hash internally.
        
        Args:
            source_url: GitHub repository URL
            
        Returns:
            Most recent RawExtraction if found, None otherwise
        """
        url_hash = compute_source_url_hash(source_url)
        return await self.get_by_source_url_hash(url_hash)
    
    async def exists(self, source_url: str) -> bool:
        """
        Check if an extraction exists for the given source URL.
        
        Args:
            source_url: GitHub repository URL
            
        Returns:
            True if extraction exists, False otherwise
        """
        url_hash = compute_source_url_hash(source_url)
        
        query = "SELECT VALUE COUNT(1) FROM c WHERE c.source_url_hash = @hash"
        params: CosmosParams = [{"name": "@hash", "value": url_hash}]
        
        results = list(self.container.query_items(
            query=query,
            parameters=params,
            partition_key=url_hash
        ))
        
        # SELECT VALUE COUNT returns int directly, not a dict
        count: int = cast(int, results[0]) if results else 0
        return count > 0
    
    async def list_by_run_id(self, run_id: UUID) -> list[RawExtraction]:
        """
        List all extractions created by a pipeline run.
        
        Args:
            run_id: Pipeline run UUID
            
        Returns:
            List of RawExtraction documents
        """
        query = "SELECT * FROM c WHERE c.run_id = @run_id"
        params: CosmosParams = [{"name": "@run_id", "value": str(run_id)}]
        
        results = list(self.container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True
        ))
        
        return [RawExtraction.from_cosmos_document(doc) for doc in results]
    
    # =========================================================================
    # IMMUTABILITY ENFORCEMENT
    # =========================================================================
    
    async def update(self, *args, **kwargs):
        """
        UPDATE IS NOT ALLOWED.
        
        RawExtraction records are immutable per design.md §5.
        To get new data, create a new extraction.
        
        Raises:
            ImmutableRecordError: Always
        """
        raise ImmutableRecordError("RawExtraction", "N/A")
    
    async def delete(self, *args, **kwargs):
        """
        DELETE IS NOT ALLOWED.
        
        RawExtraction records are part of the audit trail.
        
        Raises:
            ImmutableRecordError: Always
        """
        raise ImmutableRecordError("RawExtraction", "N/A")


# Singleton instance
_raw_extraction_repo: Optional[RawExtractionRepository] = None


def get_raw_extraction_repository() -> RawExtractionRepository:
    """Get or create the raw extraction repository singleton."""
    global _raw_extraction_repo
    if _raw_extraction_repo is None:
        _raw_extraction_repo = RawExtractionRepository()
    return _raw_extraction_repo
