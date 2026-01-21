"""Tests for Content model and repository."""

import pytest
from datetime import datetime

from app.models.content import Content, ContentPublic
from app.models.enums import ContentStatus, ContentType


class TestContentModel:
    """Tests for Content model."""
    
    def test_content_creation_with_defaults(self):
        """Content should be created with default values."""
        content = Content(
            contributor_id="user-123",
            title="Test Workshop",
            description="A test workshop for learning",
            source_url="https://github.com/test/repo",
        )
        
        assert content.id is not None
        assert content.contributor_id == "user-123"
        assert content.title == "Test Workshop"
        assert content.content_type == ContentType.WORKSHOP
        assert content.status == ContentStatus.DRAFT
        assert content.categories == []
        assert content.level == "beginner"
        assert content.view_count == 0
    
    def test_content_creation_with_all_fields(self):
        """Content should accept all fields."""
        content = Content(
            contributor_id="user-123",
            title="Advanced Kubernetes",
            description="Deep dive into K8s",
            source_url="https://github.com/test/k8s",
            content_type=ContentType.SOLUTION_IDEA,
            status=ContentStatus.PUBLISHED,
            categories=["Kubernetes", "DevOps"],
            level="advanced",
            duration_minutes=120,
            thumbnail_url="https://example.com/thumb.jpg",
            icon="🐳",
        )
        
        assert content.content_type == ContentType.SOLUTION_IDEA
        assert content.status == ContentStatus.PUBLISHED
        assert "Kubernetes" in content.categories
        assert content.level == "advanced"
        assert content.duration_minutes == 120
    
    def test_to_cosmos_item(self):
        """Content should convert to Cosmos DB format."""
        content = Content(
            contributor_id="user-123",
            title="Test",
            description="Test desc",
            source_url="https://github.com/test",
            categories=["Azure", "AI"],
        )
        
        item = content.to_cosmos_item()
        
        assert item["id"] == content.id
        assert item["contributor_id"] == "user-123"
        assert item["title"] == "Test"
        assert item["status"] == "draft"
        assert item["content_type"] == "workshop"
        assert item["categories"] == ["Azure", "AI"]
        assert "created_at" in item
    
    def test_from_cosmos_item(self):
        """Content should be created from Cosmos DB document."""
        item = {
            "id": "content-123",
            "contributor_id": "user-456",
            "title": "From Cosmos",
            "description": "Test description",
            "source_url": "https://github.com/test",
            "content_type": "solution_idea",
            "status": "published",
            "categories": ["Azure"],
            "level": "intermediate",
            "duration_minutes": 90,
            "view_count": 100,
            "bookmark_count": 10,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-02T00:00:00",
            "published_at": "2024-01-02T12:00:00",
        }
        
        content = Content.from_cosmos_item(item)
        
        assert content.id == "content-123"
        assert content.contributor_id == "user-456"
        assert content.content_type == ContentType.SOLUTION_IDEA
        assert content.status == ContentStatus.PUBLISHED
        assert content.view_count == 100
        assert content.published_at is not None
    
    def test_publish(self):
        """Content.publish() should update status and timestamp."""
        content = Content(
            contributor_id="user-123",
            title="Test",
            description="Test",
            source_url="https://github.com/test",
        )
        
        assert content.status == ContentStatus.DRAFT
        assert content.published_at is None
        
        content.publish()
        
        assert content.status == ContentStatus.PUBLISHED
        assert content.published_at is not None
    
    def test_increment_view(self):
        """Content.increment_view() should increase view count."""
        content = Content(
            contributor_id="user-123",
            title="Test",
            description="Test",
            source_url="https://github.com/test",
        )
        
        assert content.view_count == 0
        
        content.increment_view()
        content.increment_view()
        
        assert content.view_count == 2


class TestContentPublic:
    """Tests for ContentPublic model."""
    
    def test_from_content(self):
        """ContentPublic should be created from Content."""
        content = Content(
            contributor_id="user-123",
            title="Test Workshop",
            description="A great workshop",
            source_url="https://github.com/test",
            categories=["Azure", "AI"],
            level="beginner",
            duration_minutes=60,
            view_count=50,
            bookmark_count=5,
        )
        content.publish()
        
        public = ContentPublic.from_content(content)
        
        assert public.id == content.id
        assert public.title == "Test Workshop"
        assert public.content_type == "workshop"
        assert public.categories == ["Azure", "AI"]
        assert public.view_count == 50
        assert public.published_at is not None
    
    def test_public_excludes_contributor_id(self):
        """ContentPublic should not expose contributor_id."""
        content = Content(
            contributor_id="user-123",
            title="Test",
            description="Test",
            source_url="https://github.com/test",
        )
        
        public = ContentPublic.from_content(content)
        
        # Check that contributor_id is not in the model
        assert not hasattr(public, 'contributor_id')


class TestContentRepository:
    """Tests for ContentRepository (requires Cosmos DB)."""
    
    @pytest.mark.skip(reason="Requires Cosmos DB emulator")
    async def test_create_and_get_content(self):
        """Repository should create and retrieve content."""
        from app.repositories.content_repo import get_content_repo
        
        repo = get_content_repo()
        content = Content(
            contributor_id="test-user",
            title="Test Content",
            description="Test description",
            source_url="https://github.com/test",
        )
        
        created = await repo.create(content)
        assert created.id == content.id
        
        retrieved = await repo.get_by_id(content.id, "test-user")
        assert retrieved is not None
        assert retrieved.title == "Test Content"
        
        # Cleanup
        await repo.delete(content.id, "test-user")
    
    @pytest.mark.skip(reason="Requires Cosmos DB emulator")
    async def test_list_published(self):
        """Repository should list published content."""
        from app.repositories.content_repo import get_content_repo
        
        repo = get_content_repo()
        contents, total = await repo.list_published(limit=10)
        
        assert isinstance(contents, list)
        assert isinstance(total, int)
    
    @pytest.mark.skip(reason="Requires Cosmos DB emulator")
    async def test_search(self):
        """Repository should search content."""
        from app.repositories.content_repo import get_content_repo
        
        repo = get_content_repo()
        contents, total = await repo.search("azure", limit=10)
        
        assert isinstance(contents, list)
        assert isinstance(total, int)


class TestContentServiceCreateFromAnalysis:
    """Tests for ContentService.create_from_analysis method."""
    
    @pytest.fixture
    def mock_repo(self):
        """Create mock content repository."""
        from unittest.mock import MagicMock, AsyncMock
        repo = MagicMock()
        repo.create = AsyncMock(side_effect=lambda c: c)
        return repo
    
    @pytest.fixture
    def content_service(self, mock_repo):
        """Create content service with mock repository."""
        from app.services.content_service import ContentService
        service = ContentService(repo=mock_repo)
        return service
    
    @pytest.fixture
    def sample_analysis_result(self):
        """Create sample analysis result."""
        from app.models.analysis import AnalysisResult
        return AnalysisResult(
            title="Azure Kubernetes Workshop",
            description="Learn to deploy apps on AKS",
            content_type="workshop",
            categories=["Azure", "Kubernetes"],
            level="intermediate",
            duration_minutes=120,
            technologies=["Kubernetes", "Docker", "Azure"],
        )
    
    @pytest.mark.asyncio
    async def test_create_from_analysis_success(self, content_service, sample_analysis_result):
        """Test creating content from analysis result."""
        content = await content_service.create_from_analysis(
            contributor_id="user-123",
            source_url="https://github.com/Azure-Samples/aks-workshop",
            result=sample_analysis_result,
        )
        
        assert content.contributor_id == "user-123"
        assert content.title == "Azure Kubernetes Workshop"
        assert content.description == "Learn to deploy apps on AKS"
        assert content.source_url == "https://github.com/Azure-Samples/aks-workshop"
        assert content.content_type == ContentType.WORKSHOP
        assert content.status == ContentStatus.DRAFT
        assert "Azure" in content.categories
        assert "Kubernetes" in content.categories
        assert content.level == "intermediate"
        assert content.duration_minutes == 120
        assert content.analysis_status == "completed"
        assert content.analysis_result is not None
    
    @pytest.mark.asyncio
    async def test_create_from_analysis_with_defaults(self, content_service):
        """Test creating content with minimal analysis result."""
        from app.models.analysis import AnalysisResult
        minimal_result = AnalysisResult(
            title="Minimal Project",
        )
        
        content = await content_service.create_from_analysis(
            contributor_id="user-456",
            source_url="https://github.com/test/repo",
            result=minimal_result,
        )
        
        assert content.title == "Minimal Project"
        assert content.description == ""
        assert content.level == "beginner"
        assert content.duration_minutes == 60
        assert content.content_type == ContentType.TUTORIAL  # Default
    
    @pytest.mark.asyncio
    async def test_content_type_mapping(self, content_service):
        """Test different content types are mapped correctly."""
        from app.models.analysis import AnalysisResult
        
        type_mappings = [
            ("workshop", ContentType.WORKSHOP),
            ("tutorial", ContentType.TUTORIAL),
            ("sample", ContentType.SAMPLE),
            ("demo", ContentType.SAMPLE),  # demo maps to sample
            ("documentation", ContentType.OTHER),  # documentation maps to other
            ("tool", ContentType.OTHER),  # tool maps to other
            ("lab", ContentType.LAB),
            ("unknown", ContentType.TUTORIAL),  # Fallback
            (None, ContentType.TUTORIAL),  # None fallback
        ]
        
        for type_str, expected_type in type_mappings:
            result = AnalysisResult(title="Test", content_type=type_str)
            content = await content_service.create_from_analysis(
                contributor_id="user-123",
                source_url="https://github.com/test/repo",
                result=result,
            )
            assert content.content_type == expected_type, f"Failed for type: {type_str}"
    
    @pytest.mark.asyncio
    async def test_create_from_analysis_with_no_title(self, content_service):
        """Test creating content when title is None."""
        from app.models.analysis import AnalysisResult
        result = AnalysisResult(
            title=None,
            description="A description but no title",
        )
        
        content = await content_service.create_from_analysis(
            contributor_id="user-123",
            source_url="https://github.com/test/repo",
            result=result,
        )
        
        assert content.title == "Untitled Content"
