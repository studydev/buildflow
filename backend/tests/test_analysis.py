"""Tests for AnalysisRequest model and repository."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.models.analysis import (
    AnalysisRequest,
    AnalysisRequestPublic,
    AnalysisResult,
    StatusHistoryEntry,
)
from app.models.enums import AnalysisStatus


class TestStatusHistoryEntry:
    """Tests for StatusHistoryEntry."""

    def test_create_entry(self):
        """Test creating a status history entry."""
        entry = StatusHistoryEntry(
            status=AnalysisStatus.PENDING,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            message="Request created",
        )

        assert entry.status == AnalysisStatus.PENDING
        assert entry.timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert entry.message == "Request created"

    def test_to_dict(self):
        """Test converting to dictionary."""
        entry = StatusHistoryEntry(
            status=AnalysisStatus.FETCHING,
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            message="Fetching repository",
        )

        data = entry.to_dict()

        assert data["status"] == "fetching"
        assert data["timestamp"] == "2024-01-01T12:00:00"
        assert data["message"] == "Fetching repository"

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "status": "parsing",
            "timestamp": "2024-01-01T12:00:00",
            "message": "Parsing README",
        }

        entry = StatusHistoryEntry.from_dict(data)

        assert entry.status == AnalysisStatus.PARSING
        assert entry.timestamp == datetime(2024, 1, 1, 12, 0, 0)
        assert entry.message == "Parsing README"


class TestAnalysisResult:
    """Tests for AnalysisResult."""

    def test_create_result(self):
        """Test creating an analysis result."""
        result = AnalysisResult(
            title="Azure Functions Workshop",
            description="Learn serverless development",
            content_type="workshop",
            categories=["Azure", "Serverless"],
            level="beginner",
            duration_minutes=90,
        )

        assert result.title == "Azure Functions Workshop"
        assert result.categories == ["Azure", "Serverless"]
        assert result.duration_minutes == 90

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = AnalysisResult(
            title="Test",
            categories=["AI"],
            technologies=["Python", "FastAPI"],
        )

        data = result.to_dict()

        assert data["title"] == "Test"
        assert data["categories"] == ["AI"]
        assert data["technologies"] == ["Python", "FastAPI"]
        assert data["level"] is None

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "title": "Test Workshop",
            "description": "Description",
            "content_type": "workshop",
            "categories": ["Azure"],
            "level": "intermediate",
            "duration_minutes": 120,
            "technologies": ["C#"],
            "prerequisites": ["Basic C#"],
            "learning_objectives": ["Build apps"],
            "raw_metadata": {"stars": 100},
        }

        result = AnalysisResult.from_dict(data)

        assert result.title == "Test Workshop"
        assert result.level == "intermediate"
        assert result.technologies == ["C#"]
        assert result.raw_metadata == {"stars": 100}


class TestAnalysisRequest:
    """Tests for AnalysisRequest model."""

    def test_create_request_with_defaults(self):
        """Test creating a request with defaults."""
        request = AnalysisRequest(
            user_id="user-123",
            source_url="https://github.com/Azure-Samples/test",
        )

        assert request.id is not None
        assert request.user_id == "user-123"
        assert request.source_url == "https://github.com/Azure-Samples/test"
        assert request.status == AnalysisStatus.PENDING
        assert request.progress == 0
        assert len(request.status_history) == 1
        assert request.status_history[0].status == AnalysisStatus.PENDING

    def test_update_status(self):
        """Test updating request status."""
        request = AnalysisRequest(
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )

        request.update_status(
            AnalysisStatus.FETCHING,
            message="Fetching repository",
            progress=25,
        )

        assert request.status == AnalysisStatus.FETCHING
        assert request.progress == 25
        assert len(request.status_history) == 2
        assert request.status_history[-1].message == "Fetching repository"

    def test_update_status_to_completed(self):
        """Test updating status to completed."""
        request = AnalysisRequest(
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )

        request.update_status(AnalysisStatus.COMPLETED)

        assert request.status == AnalysisStatus.COMPLETED
        assert request.progress == 100
        assert request.completed_at is not None

    def test_set_result(self):
        """Test setting analysis result."""
        request = AnalysisRequest(
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )

        result = AnalysisResult(
            title="Test",
            categories=["Azure"],
        )

        request.set_result(result)

        assert request.result == result
        assert request.status == AnalysisStatus.COMPLETED
        assert request.progress == 100

    def test_set_error(self):
        """Test setting error."""
        request = AnalysisRequest(
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )

        request.set_error("Failed to fetch repository")

        assert request.error_message == "Failed to fetch repository"
        assert request.status == AnalysisStatus.FAILED
        assert request.completed_at is not None

    def test_to_cosmos_item(self):
        """Test converting to Cosmos DB item."""
        request = AnalysisRequest(
            id="req-123",
            user_id="user-456",
            source_url="https://github.com/test/repo",
        )

        item = request.to_cosmos_item()

        assert item["id"] == "req-123"
        assert item["user_id"] == "user-456"
        assert item["source_url"] == "https://github.com/test/repo"
        assert item["status"] == "pending"
        assert item["type"] == "analysis_request"
        assert item["partition_key"] == "user-456"
        assert "status_history" in item

    def test_from_cosmos_item(self):
        """Test creating from Cosmos DB item."""
        item = {
            "id": "req-123",
            "user_id": "user-456",
            "source_url": "https://github.com/test/repo",
            "status": "fetching",
            "status_history": [
                {
                    "status": "pending",
                    "timestamp": "2024-01-01T12:00:00",
                    "message": "Created",
                },
                {
                    "status": "fetching",
                    "timestamp": "2024-01-01T12:01:00",
                    "message": "Fetching",
                },
            ],
            "result": None,
            "error_message": None,
            "progress": 25,
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:01:00",
            "completed_at": None,
        }

        request = AnalysisRequest.from_cosmos_item(item)

        assert request.id == "req-123"
        assert request.user_id == "user-456"
        assert request.status == AnalysisStatus.FETCHING
        assert request.progress == 25
        assert len(request.status_history) == 2

    def test_from_cosmos_item_with_result(self):
        """Test creating from Cosmos item with result."""
        item = {
            "id": "req-123",
            "user_id": "user-456",
            "source_url": "https://github.com/test/repo",
            "status": "completed",
            "status_history": [],
            "result": {
                "title": "Test Workshop",
                "description": "A test",
                "content_type": "workshop",
                "categories": ["Azure"],
            },
            "error_message": None,
            "progress": 100,
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:05:00",
            "completed_at": "2024-01-01T12:05:00",
        }

        request = AnalysisRequest.from_cosmos_item(item)

        assert request.result is not None
        assert request.result.title == "Test Workshop"
        assert request.completed_at is not None


class TestAnalysisRequestPublic:
    """Tests for AnalysisRequestPublic."""

    def test_from_request(self):
        """Test creating public view from request."""
        request = AnalysisRequest(
            id="req-123",
            user_id="user-456",
            source_url="https://github.com/test/repo",
        )
        request.update_status(AnalysisStatus.FETCHING, progress=25)

        public = AnalysisRequestPublic.from_request(request)

        assert public.id == "req-123"
        assert public.source_url == "https://github.com/test/repo"
        assert public.status == "fetching"
        assert public.progress == 25
        # user_id should not be in public view
        assert not hasattr(public, 'user_id') or public.__dict__.get('user_id') is None


class TestAnalysisRequestRepository:
    """Tests for AnalysisRequestRepository (mock tests)."""

    @pytest.fixture
    def mock_container(self):
        """Create a mock container."""
        return MagicMock()

    @pytest.fixture
    def repo(self, mock_container):
        """Create repository with mock container."""
        from app.repositories.analysis_repo import AnalysisRequestRepository

        repo = AnalysisRequestRepository()
        repo._container = mock_container
        return repo

    @pytest.mark.asyncio
    async def test_create(self, repo, mock_container):
        """Test creating an analysis request."""
        request = AnalysisRequest(
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )

        result = await repo.create(request)

        mock_container.create_item.assert_called_once()
        assert result.id == request.id

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, mock_container):
        """Test getting by ID."""
        mock_container.read_item.return_value = {
            "id": "req-123",
            "user_id": "user-456",
            "source_url": "https://github.com/test/repo",
            "status": "pending",
            "status_history": [],
            "progress": 0,
            "created_at": "2024-01-01T12:00:00",
            "updated_at": "2024-01-01T12:00:00",
            "completed_at": None,
        }

        result = await repo.get_by_id("req-123", "user-456")

        assert result is not None
        assert result.id == "req-123"
        # Partition key is now request_id (the container uses /id as partition key)
        mock_container.read_item.assert_called_with(
            item="req-123",
            partition_key="req-123",
        )

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo, mock_container):
        """Test getting by ID when not found."""
        mock_container.read_item.side_effect = Exception("NotFound")

        result = await repo.get_by_id("nonexistent", "user-456")

        assert result is None


# Integration tests with Cosmos emulator
@pytest.mark.skip(reason="Requires Cosmos DB emulator")
class TestAnalysisRequestRepositoryIntegration:
    """Integration tests for AnalysisRequestRepository."""

    @pytest.fixture
    async def repo(self):
        """Get real repository."""
        from app.repositories.analysis_repo import get_analysis_repo
        return get_analysis_repo()

    @pytest.mark.asyncio
    async def test_create_and_get(self, repo):
        """Test creating and getting a request."""
        request = AnalysisRequest(
            user_id="test-user",
            source_url="https://github.com/test/integration-test",
        )

        created = await repo.create(request)
        fetched = await repo.get_by_id(created.id, created.user_id)

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.source_url == created.source_url

        # Cleanup
        await repo.delete(created.id, created.user_id)

    @pytest.mark.asyncio
    async def test_update_status(self, repo):
        """Test updating request status."""
        request = AnalysisRequest(
            user_id="test-user",
            source_url="https://github.com/test/status-test",
        )

        created = await repo.create(request)
        updated = await repo.update_status(
            created.id,
            created.user_id,
            AnalysisStatus.FETCHING,
            message="Fetching repo",
            progress=25,
        )

        assert updated is not None
        assert updated.status == AnalysisStatus.FETCHING
        assert updated.progress == 25

        # Cleanup
        await repo.delete(created.id, created.user_id)

    @pytest.mark.asyncio
    async def test_find_duplicate(self, repo):
        """Test finding duplicate requests."""
        request = AnalysisRequest(
            user_id="test-user",
            source_url="https://github.com/test/duplicate-test",
        )

        created = await repo.create(request)

        # Should find duplicate
        duplicate = await repo.find_duplicate(
            "test-user",
            "https://github.com/test/duplicate-test",
            within_hours=24,
        )

        assert duplicate is not None
        assert duplicate.id == created.id

        # Cleanup
        await repo.delete(created.id, created.user_id)
