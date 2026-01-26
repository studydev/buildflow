"""Content service for business logic."""

import logging
from typing import Optional

from app.models.analysis import AnalysisResult
from app.models.content import Content
from app.models.enums import ContentStatus, ContentType
from app.repositories.analysis_repo import AnalysisRequestRepository
from app.repositories.content_repo import ContentRepository, get_content_repo
from app.schemas.content import (
    ContentCreateRequest,
    ContentListResponse,
    ContentResponse,
    ContentUpdateRequest,
)

logger = logging.getLogger(__name__)


class ContentService:
    """Service for content-related business logic."""

    def __init__(self, repo: Optional[ContentRepository] = None):
        """Initialize with content repository."""
        self._repo = repo

    @property
    def repo(self) -> ContentRepository:
        """Lazy load repository."""
        if self._repo is None:
            self._repo = get_content_repo()
        return self._repo

    async def create_from_analysis(
        self,
        contributor_id: str,
        source_url: str,
        result: AnalysisResult,
        analysis_request_id: Optional[str] = None,
    ) -> Content:
        """
        Create Content from analysis result.

        Args:
            contributor_id: User ID of the contributor
            source_url: GitHub repository URL
            result: Extracted metadata from analysis
            analysis_request_id: ID of the analysis request that created this content

        Returns:
            Created Content
        """
        from datetime import datetime

        # Map content type from analysis result
        content_type = self._map_content_type(result.content_type)

        # Store both English (title) and Korean (title_kr) versions
        # title should be English, title_kr should be Korean
        title = result.title or result.title_kr or "Untitled Content"
        title_kr = result.title_kr or None
        description = result.description or result.description_kr or ""
        description_kr = result.description_kr or None

        # Determine icon based on content type
        icon_map = {
            ContentType.WORKSHOP: "🎓",
            ContentType.TUTORIAL: "📚",
            ContentType.LAB: "🔬",
            ContentType.SAMPLE: "💻",
            ContentType.TEMPLATE: "📋",
            ContentType.SOLUTION_IDEA: "💡",
            ContentType.OTHER: "📄",
        }
        icon = icon_map.get(content_type, "📄")

        # Create content with PUBLISHED status so it shows immediately
        content = Content(
            contributor_id=contributor_id,
            analysis_request_id=analysis_request_id,
            title=title,
            title_kr=title_kr,
            description=description,
            description_kr=description_kr,
            content_type=content_type,
            status=ContentStatus.PUBLISHED,
            source_url=source_url,
            source_type="github",
            categories=result.categories,
            level=result.level or "beginner",
            duration_minutes=result.duration_minutes or 60,
            icon=icon,
            analysis_status="completed",
            analysis_result=result.to_dict(),
            published_at=datetime.utcnow(),
            # Additional bilingual fields from analysis
            prerequisites=result.prerequisites or [],
            learning_outcomes=result.learning_objectives or [],
            technologies=result.technologies or [],
            # GitHub repository metadata
            stars=result.stars if result.stars else None,
            forks=result.forks if result.forks else None,
        )

        # Persist to database
        created = await self.repo.create(content)
        logger.info(f"Created content {created.id} from analysis for {source_url}")

        return created

    async def create(
        self,
        contributor_id: str,
        data: ContentCreateRequest,
    ) -> Content:
        """
        Create new content manually.

        Args:
            contributor_id: User ID of the contributor
            data: Content creation data

        Returns:
            Created Content
        """
        content_type = self._map_content_type(data.content_type)

        content = Content(
            contributor_id=contributor_id,
            title=data.title,
            description=data.description,
            content_type=content_type,
            status=ContentStatus.DRAFT,
            source_url=data.source_url,
            source_type="github",
            categories=data.categories,
            level=data.level,
            duration_minutes=data.duration_minutes,
            thumbnail_url=data.thumbnail_url,
            icon=data.icon,
        )

        try:
            created = await self.repo.create(content)
            logger.info(f"Created content {created.id} for contributor {contributor_id}")
            return created
        except Exception as e:
            logger.warning(f"Failed to persist content to Cosmos, returning unpersisted: {e}")
            # For development without Cosmos
            return content

    async def update(
        self,
        content_id: str,
        data: ContentUpdateRequest,
    ) -> Content:
        """
        Update existing content.

        Args:
            content_id: Content unique identifier
            data: Content update data

        Returns:
            Updated Content
        """
        # Get existing content (cross-partition query since we don't know contributor_id)
        existing = await self.repo.get_by_id_cross_partition(content_id)
        if existing is None:
            raise ValueError(f"Content {content_id} not found")

        # Update fields if provided
        if data.title is not None:
            existing.title = data.title
        if data.description is not None:
            existing.description = data.description
        if data.categories is not None:
            existing.categories = data.categories
        if data.level is not None:
            existing.level = data.level
        if data.duration_minutes is not None:
            existing.duration_minutes = data.duration_minutes
        if data.thumbnail_url is not None:
            existing.thumbnail_url = data.thumbnail_url
        if data.icon is not None:
            existing.icon = data.icon
        # Bilingual fields
        if data.title_kr is not None:
            existing.title_kr = data.title_kr
        if data.description_kr is not None:
            existing.description_kr = data.description_kr
        # Resource links
        if data.youtube_url is not None:
            existing.youtube_url = data.youtube_url
        if data.pdf_url is not None:
            existing.pdf_url = data.pdf_url
        if data.pptx_url is not None:
            existing.pptx_url = data.pptx_url

        try:
            updated = await self.repo.update(existing)
            logger.info(f"Updated content {content_id}")
            return updated
        except Exception as e:
            logger.warning(f"Failed to persist content update to Cosmos: {e}")
            return existing

    async def update_status(
        self,
        content_id: str,
        new_status: str,
    ) -> Content:
        """
        Update content status (publish/archive).

        Args:
            content_id: Content unique identifier
            new_status: New status value ('published' or 'archived')

        Returns:
            Updated Content
        """
        from datetime import datetime

        # Get existing content (cross-partition query since we don't know contributor_id)
        existing = await self.repo.get_by_id_cross_partition(content_id)
        if existing is None:
            raise ValueError(f"Content {content_id} not found")

        # Map status string to enum
        status_mapping = {
            "published": ContentStatus.PUBLISHED,
            "archived": ContentStatus.ARCHIVED,
        }

        existing.status = status_mapping[new_status]

        # Set published_at timestamp when publishing
        if new_status == "published" and existing.published_at is None:
            existing.published_at = datetime.utcnow()

        try:
            updated = await self.repo.update(existing)
            logger.info(f"Updated content {content_id} status to {new_status}")
            return updated
        except Exception as e:
            logger.warning(f"Failed to persist status update to Cosmos: {e}")
            return existing

    def _map_content_type(self, type_str: Optional[str]) -> ContentType:
        """
        Map analysis result content type to ContentType enum.

        Args:
            type_str: Content type string from analysis

        Returns:
            ContentType enum value
        """
        if not type_str:
            return ContentType.TUTORIAL

        type_lower = type_str.lower()

        mapping = {
            "workshop": ContentType.WORKSHOP,
            "tutorial": ContentType.TUTORIAL,
            "sample": ContentType.SAMPLE,
            "demo": ContentType.SAMPLE,  # Map demo to sample
            "documentation": ContentType.OTHER,  # Map documentation to other
            "tool": ContentType.OTHER,  # Map tool to other
            "lab": ContentType.LAB,
            "template": ContentType.TEMPLATE,
            "solution_idea": ContentType.SOLUTION_IDEA,
        }

        return mapping.get(type_lower, ContentType.TUTORIAL)

    async def list_by_contributor(
        self,
        contributor_id: str,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> ContentListResponse:
        """
        List all content for a contributor (all statuses).

        Args:
            contributor_id: Contributor user ID
            page: Page number (1-indexed)
            limit: Items per page
            status: Optional status filter (draft, published, archived)

        Returns:
            Paginated content list response
        """
        offset = (page - 1) * limit

        try:
            contents, total = await self.repo.list_by_contributor(
                contributor_id=contributor_id,
                limit=limit,
                offset=offset,
                status=status,
            )
        except Exception as e:
            logger.error(f"Failed to fetch contributor content: {e}")
            contents, total = [], 0

        items = [
            ContentResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                content_type=c.content_type.value if isinstance(c.content_type, ContentType) else c.content_type,
                status=c.status.value if hasattr(c.status, 'value') else str(c.status),
                categories=c.categories,
                level=c.level,
                duration_minutes=c.duration_minutes,
                thumbnail_url=c.thumbnail_url,
                icon=c.icon,
                source_url=c.source_url,
                view_count=c.view_count,
                bookmark_count=c.bookmark_count,
                published_at=c.published_at,
                # Bilingual fields
                title_kr=getattr(c, 'title_kr', None),
                description_kr=getattr(c, 'description_kr', None),
                summary_short=getattr(c, 'summary_short', None),
                summary_kr=getattr(c, 'summary_kr', None),
                prerequisites=getattr(c, 'prerequisites', []) or [],
                prerequisites_kr=getattr(c, 'prerequisites_kr', []) or [],
                learning_outcomes=getattr(c, 'learning_outcomes', []) or [],
                learning_outcomes_kr=getattr(c, 'learning_outcomes_kr', []) or [],
                difficulty_level=getattr(c, 'difficulty_level', None),
                analysis_request_id=getattr(c, 'analysis_request_id', None),
            )
            for c in contents
        ]

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )

    async def list_published(
        self,
        page: int = 1,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> ContentListResponse:
        """
        List published content with pagination.

        Args:
            page: Page number (1-indexed)
            limit: Items per page
            category: Filter by category

        Returns:
            Paginated content list response
        """
        offset = (page - 1) * limit

        contents, total = await self.repo.list_published(
            limit=limit,
            offset=offset,
            category=category,
        )

        items = [
            ContentResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                content_type=c.content_type.value if isinstance(c.content_type, ContentType) else c.content_type,
                categories=c.categories,
                level=c.level,
                duration_minutes=c.duration_minutes,
                thumbnail_url=c.thumbnail_url,
                icon=c.icon,
                source_url=c.source_url,
                view_count=c.view_count,
                bookmark_count=c.bookmark_count,
                published_at=c.published_at,
                # Bilingual fields (T502)
                title_kr=getattr(c, 'title_kr', None),
                description_kr=getattr(c, 'description_kr', None),
                summary_short=getattr(c, 'summary_short', None),
                summary_kr=getattr(c, 'summary_kr', None),
                prerequisites=getattr(c, 'prerequisites', []) or [],
                prerequisites_kr=getattr(c, 'prerequisites_kr', []) or [],
                learning_outcomes=getattr(c, 'learning_outcomes', []) or [],
                learning_outcomes_kr=getattr(c, 'learning_outcomes_kr', []) or [],
                difficulty_level=getattr(c, 'difficulty_level', None),
                analysis_request_id=getattr(c, 'analysis_request_id', None),
            )
            for c in contents
        ]

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )

    async def list_all(
        self,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> ContentListResponse:
        """
        List all content across all contributors (all statuses).

        Args:
            page: Page number (1-indexed)
            limit: Items per page
            status: Optional status filter

        Returns:
            Paginated content list response
        """
        offset = (page - 1) * limit

        contents, total = await self.repo.list_all(
            limit=limit,
            offset=offset,
            status=status,
        )

        items = [
            ContentResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                content_type=c.content_type.value if isinstance(c.content_type, ContentType) else c.content_type,
                status=c.status.value if hasattr(c.status, 'value') else str(c.status),
                categories=c.categories,
                level=c.level,
                duration_minutes=c.duration_minutes,
                thumbnail_url=c.thumbnail_url,
                icon=c.icon,
                source_url=c.source_url,
                view_count=c.view_count,
                bookmark_count=c.bookmark_count,
                published_at=c.published_at,
                # Bilingual fields
                title_kr=getattr(c, 'title_kr', None),
                description_kr=getattr(c, 'description_kr', None),
                summary_short=getattr(c, 'summary_short', None),
                summary_kr=getattr(c, 'summary_kr', None),
                prerequisites=getattr(c, 'prerequisites', []) or [],
                prerequisites_kr=getattr(c, 'prerequisites_kr', []) or [],
                learning_outcomes=getattr(c, 'learning_outcomes', []) or [],
                learning_outcomes_kr=getattr(c, 'learning_outcomes_kr', []) or [],
                difficulty_level=getattr(c, 'difficulty_level', None),
                analysis_request_id=getattr(c, 'analysis_request_id', None),
            )
            for c in contents
        ]

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )

    async def search(
        self,
        query: str,
        page: int = 1,
        limit: int = 20,
    ) -> ContentListResponse:
        """
        Search content by text.

        Args:
            query: Search query
            page: Page number
            limit: Items per page

        Returns:
            Paginated search results
        """
        offset = (page - 1) * limit

        contents, total = await self.repo.search(
            query_text=query,
            limit=limit,
            offset=offset,
        )

        items = [
            ContentResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                content_type=c.content_type.value if isinstance(c.content_type, ContentType) else c.content_type,
                categories=c.categories,
                level=c.level,
                duration_minutes=c.duration_minutes,
                thumbnail_url=c.thumbnail_url,
                icon=c.icon,
                source_url=c.source_url,
                view_count=c.view_count,
                bookmark_count=c.bookmark_count,
                published_at=c.published_at,
                # Bilingual fields (T502)
                title_kr=getattr(c, 'title_kr', None),
                description_kr=getattr(c, 'description_kr', None),
                summary_short=getattr(c, 'summary_short', None),
                summary_kr=getattr(c, 'summary_kr', None),
                prerequisites=getattr(c, 'prerequisites', []) or [],
                prerequisites_kr=getattr(c, 'prerequisites_kr', []) or [],
                learning_outcomes=getattr(c, 'learning_outcomes', []) or [],
                learning_outcomes_kr=getattr(c, 'learning_outcomes_kr', []) or [],
                difficulty_level=getattr(c, 'difficulty_level', None),
                analysis_request_id=getattr(c, 'analysis_request_id', None),
            )
            for c in contents
        ]

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )

    async def get_by_id(self, content_id: str) -> Optional[Content]:
        """
        Get content by ID.

        Args:
            content_id: Content ID

        Returns:
            Content if found
        """
        return await self.repo.get_by_id_cross_partition(content_id)

    # =========================================================================
    # Pipeline Integration Methods (Milestone 2)
    # =========================================================================

    async def update_raw_extraction_ref(
        self,
        content_id: str,
        raw_extraction_id,
    ) -> Content:
        """
        Update content with reference to RawExtraction.

        Used by Analysis Pipeline (T201) to link content to its raw extraction.

        Args:
            content_id: Content unique identifier
            raw_extraction_id: ID of the RawExtraction document

        Returns:
            Updated Content
        """
        # Get existing content (cross-partition query since we don't know contributor_id)
        existing = await self.repo.get_by_id_cross_partition(str(content_id))
        if existing is None:
            raise ValueError(f"Content {content_id} not found")

        # Update raw_extraction_id reference
        existing.raw_extraction_id = raw_extraction_id

        try:
            updated = await self.repo.update(existing)
            logger.info(
                f"Updated content {content_id} with raw_extraction_id {raw_extraction_id}"
            )
            return updated
        except Exception as e:
            logger.warning(f"Failed to update raw_extraction_id: {e}")
            return existing

    async def create_skeleton(self, content: Content) -> Content:
        """
        Create a minimal content skeleton.

        Used by Analysis Pipeline (T201) to create initial content
        before enrichment.

        Args:
            content: Pre-populated Content model

        Returns:
            Created Content
        """
        try:
            created = await self.repo.create(content)
            logger.info(
                f"Created content skeleton {created.id} for {content.source_url}"
            )
            return created
        except Exception as e:
            logger.warning(f"Failed to create content skeleton: {e}")
            # Return the original content for development without Cosmos
            return content

    async def get_by_source_url(self, source_url: str) -> Optional[Content]:
        """
        Get content by source URL.

        Used to check if content already exists for a URL.

        Args:
            source_url: GitHub repository URL

        Returns:
            Content if found, None otherwise
        """
        try:
            return await self.repo.get_by_source_url(source_url)
        except Exception as e:
            logger.warning(f"Error fetching content by source_url: {e}")
            return None

    async def sync_from_analysis(self, content_id: str) -> Optional[Content]:
        """
        Sync content fields from the linked analysis request.

        Fetches the original analysis_request by analysis_request_id
        and updates the content with the latest result data.

        Args:
            content_id: Content ID to sync

        Returns:
            Updated Content if successful, None otherwise
        """
        try:
            # Get the content
            content = await self.repo.get_by_id(content_id)
            if not content:
                logger.warning(f"Content not found: {content_id}")
                return None

            # Check if content has linked analysis_request_id
            analysis_request_id = getattr(content, 'analysis_request_id', None)
            if not analysis_request_id:
                logger.warning(f"Content {content_id} has no linked analysis_request_id")
                return None

            # Fetch the analysis request
            analysis_repo = AnalysisRequestRepository()
            analysis_request = await analysis_repo.get_by_id_cross_partition(analysis_request_id)
            if not analysis_request:
                logger.warning(f"Analysis request not found: {analysis_request_id}")
                return None

            # Check if analysis has result
            if not analysis_request.result:
                logger.warning(f"Analysis request {analysis_request_id} has no result")
                return None

            result = analysis_request.result

            # Update content fields from analysis result
            content.title = result.title or content.title
            content.title_kr = result.title_kr or getattr(content, 'title_kr', None)
            content.description = result.description or content.description
            content.description_kr = result.description_kr or getattr(content, 'description_kr', None)
            content.source_url = result.source_url or content.source_url

            if result.content_type:
                try:
                    content.content_type = ContentType(result.content_type)
                except ValueError:
                    pass  # Keep existing content_type if invalid

            content.categories = result.categories or content.categories
            content.level = result.level or content.level
            content.duration_minutes = result.duration_minutes or content.duration_minutes

            # Update bilingual fields
            if hasattr(content, 'prerequisites'):
                content.prerequisites = result.prerequisites or getattr(content, 'prerequisites', [])
            if hasattr(content, 'learning_outcomes'):
                content.learning_outcomes = result.learning_objectives or getattr(content, 'learning_outcomes', [])

            # Save the updated content
            updated_content = await self.repo.update(content)
            logger.info(f"Synced content {content_id} from analysis request {analysis_request_id}")
            return updated_content

        except Exception as e:
            logger.error(f"Error syncing content from analysis: {e}")
            return None


# Singleton instance
_content_service: Optional[ContentService] = None


def get_content_service() -> ContentService:
    """Get content service singleton."""
    global _content_service
    if _content_service is None:
        _content_service = ContentService()
    return _content_service
