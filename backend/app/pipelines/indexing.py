"""Indexing Pipeline - Search index updates.

Per design.md §3.5: Build and update search indexes.

Pipeline Type: indexing
Trigger: enrichment_completed | manual_trigger | full_reindex
Execution: Azure Container Apps Job
Depends on: enrichment (content must have enriched data)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.content import Content
from app.models.enums import ContentStatus, PipelineType
from app.pipelines.base import BasePipeline
from app.repositories.content_repo import ContentRepository
from app.repositories.pipeline_repo import PipelineRepository
from app.schemas.pipeline import PipelineMessage
from app.services.llm_service import LLMService, get_llm_service
from app.services.search_service import SearchService, get_search_service

logger = logging.getLogger(__name__)


# Batch size for indexing operations
BATCH_SIZE = 100


class IndexingPipeline(BasePipeline):
    """Search indexing pipeline.

    Per design.md §3.5:
    - Load Content(s) with enriched data
    - Generate embedding for each content
    - Upsert to Azure AI Search
    - Update last_indexed_at on Content
    """

    pipeline_type = PipelineType.INDEXING

    def __init__(
        self,
        content_repo: Optional[ContentRepository] = None,
        pipeline_repo: Optional[PipelineRepository] = None,
        search_service: Optional[SearchService] = None,
        llm_service: Optional[LLMService] = None,
    ):
        """Initialize IndexingPipeline.

        Args:
            content_repo: Content repository
            pipeline_repo: Pipeline repository
            search_service: Azure AI Search service
            llm_service: LLM service for embeddings
        """
        super().__init__()
        self.content_repo = content_repo or ContentRepository()
        self.pipeline_repo = pipeline_repo
        self.search_service = search_service or get_search_service()
        self.llm_service = llm_service or get_llm_service()

        # Pipeline state
        self.processed_count = 0
        self.failed_count = 0
        self.failed_ids: List[str] = []

    async def validate_input(self, input_params: Dict[str, Any]) -> bool:
        """Validate input parameters.

        Required:
        - content_ids: List of UUIDs or "all" for full reindex

        Optional:
        - batch_size: Override default batch size
        """
        content_ids = input_params.get("content_ids")
        if not content_ids:
            self.error_message = "content_ids is required (list of UUIDs or 'all')"
            return False

        if content_ids != "all" and not isinstance(content_ids, list):
            self.error_message = "content_ids must be a list of UUIDs or 'all'"
            return False

        return True

    async def execute(self, message: PipelineMessage) -> Dict[str, Any]:
        """Execute indexing pipeline.

        Steps per design.md §3.5:
        1. Load Content(s) with enriched data
        2. Generate embedding for each content
        3. Upsert to Azure AI Search
        4. Update last_indexed_at on Content

        Args:
            message: PipelineMessage with input parameters containing:
                - content_ids: List of UUIDs or "all"
                - batch_size: Optional batch size override

        Returns:
            Output summary dict
        """
        input_params = message.input_params
        content_ids = input_params.get("content_ids", [])
        batch_size = input_params.get("batch_size", BATCH_SIZE)

        # Reset counters
        self.processed_count = 0
        self.failed_count = 0
        self.failed_ids = []

        # Ensure index exists
        try:
            await self.search_service.create_or_update_index()
        except Exception as e:
            logger.error(f"Failed to create/update search index: {e}")
            raise

        # Get content items to index
        if content_ids == "all":
            contents = await self._get_all_published_content()
        else:
            contents = await self._get_contents_by_ids(content_ids)

        if not contents:
            logger.info("No content to index")
            return {
                "status": "completed",
                "processed": 0,
                "failed": 0,
                "message": "No content to index",
            }

        logger.info(f"Indexing {len(contents)} content items")

        # Process in batches
        for i in range(0, len(contents), batch_size):
            batch = contents[i:i + batch_size]
            await self._process_batch(batch)

        return {
            "status": "completed",
            "processed": self.processed_count,
            "failed": self.failed_count,
            "failed_ids": self.failed_ids,
            "total": len(contents),
        }

    async def _get_all_published_content(self) -> List[Content]:
        """Get all published content for full reindex."""
        # Get all published content
        contents, _ = await self.content_repo.list_all(
            status=ContentStatus.PUBLISHED,
            limit=10000,  # Max for full reindex
        )
        return contents

    async def _get_contents_by_ids(
        self,
        content_ids: List[str],
    ) -> List[Content]:
        """Get content items by IDs."""
        contents = []
        for content_id in content_ids:
            try:
                content = await self.content_repo.get_by_id_cross_partition(content_id)
                if content:
                    contents.append(content)
                else:
                    logger.warning(f"Content not found: {content_id}")
            except Exception as e:
                logger.error(f"Failed to get content {content_id}: {e}")
        return contents

    async def _process_batch(self, batch: List[Content]) -> None:
        """Process a batch of content items."""
        documents = []

        for content in batch:
            try:
                # Generate embedding
                embedding = await self._generate_embedding(content)

                # Convert to search document
                doc = self.search_service._content_to_document(content, embedding)
                doc["@search.action"] = "mergeOrUpload"
                documents.append(doc)

            except Exception as e:
                logger.error(f"Failed to prepare content {content.id}: {e}")
                self.failed_count += 1
                self.failed_ids.append(str(content.id))

        # Batch upload to search
        if documents:
            try:
                await self.search_service.upsert_documents(documents)

                # Update last_indexed_at for successful items
                for content in batch:
                    if str(content.id) not in self.failed_ids:
                        await self._update_indexed_timestamp(content)
                        self.processed_count += 1

            except Exception as e:
                logger.error(f"Batch upload failed: {e}")
                for content in batch:
                    if str(content.id) not in self.failed_ids:
                        self.failed_count += 1
                        self.failed_ids.append(str(content.id))

    async def _generate_embedding(self, content: Content) -> Optional[List[float]]:
        """Generate embedding for content."""
        if not self.llm_service.is_configured:
            logger.warning("LLM not configured, skipping embedding generation")
            return None

        # Build text for embedding
        text = self.llm_service.generate_embedding_text(
            title=content.title,
            description=content.description,
            summary=content.summary_short or content.summary_long,
        )

        try:
            return await self.llm_service.generate_embedding(text)
        except Exception as e:
            logger.warning(f"Failed to generate embedding for {content.id}: {e}")
            return None

    async def _update_indexed_timestamp(self, content: Content) -> None:
        """Update last_indexed_at timestamp on content."""
        try:
            content.last_indexed_at = datetime.now(timezone.utc)
            await self.content_repo.update(content)
        except Exception as e:
            logger.warning(f"Failed to update last_indexed_at for {content.id}: {e}")

    async def on_success(self, message: PipelineMessage, output: Dict[str, Any]) -> None:
        """Handle successful completion."""
        logger.info(
            f"Indexing completed: {output.get('processed', 0)} processed, "
            f"{output.get('failed', 0)} failed"
        )
        await super().on_success(message, output)

    async def on_failure(self, message: PipelineMessage, error: Exception) -> None:
        """Handle pipeline failure."""
        logger.error(f"Indexing pipeline failed: {error}")
        await super().on_failure(message, error)
