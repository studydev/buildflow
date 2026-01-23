"""Tests for Analysis Requests API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import require_contributor
from app.main import create_app
from app.models.analysis import AnalysisRequest
from app.models.enums import AnalysisStatus, UserRole
from app.models.user import User
from app.services.analysis_service import AnalysisService, get_analysis_service


@pytest.fixture
def mock_contributor():
    """Create a mock contributor user."""
    return User(
        id="contributor-123",
        email="contributor@example.com",
        role=UserRole.CONTRIBUTOR,
    )


@pytest.fixture
def mock_analysis_request():
    """Create a mock analysis request."""
    return AnalysisRequest(
        id="req-123",
        user_id="contributor-123",
        source_url="https://github.com/Azure-Samples/test-repo",
        status=AnalysisStatus.PENDING,
    )


@pytest.fixture
def mock_service():
    """Create a mock analysis service."""
    service = MagicMock(spec=AnalysisService)
    service.validate_url.return_value = (True, None)
    # Mock the new async validate_and_resolve_url method
    service.validate_and_resolve_url = AsyncMock(
        return_value=(True, "https://github.com/Azure-Samples/test-repo", None)
    )
    return service


@pytest.fixture
def app_with_mocks(mock_contributor, mock_service):
    """Create app with dependency overrides."""
    app = create_app()
    app.dependency_overrides[require_contributor] = lambda: mock_contributor
    app.dependency_overrides[get_analysis_service] = lambda: mock_service
    return app


@pytest.fixture
def client(app_with_mocks, mock_service, mock_analysis_request):
    """Create test client with mocked background tasks."""
    # Mock create_request to return is_duplicate=True to avoid background task
    mock_service.create_request = AsyncMock(return_value=(mock_analysis_request, True))

    with TestClient(app_with_mocks) as client:
        yield client


class TestCreateAnalysisRequest:
    """Tests for POST /api/v1/analysis-requests."""

    def test_create_request_success(self, app_with_mocks, mock_service, mock_analysis_request):
        """Test successful creation of analysis request."""
        mock_service.create_request = AsyncMock(return_value=(mock_analysis_request, False))

        # Patch the background pipeline to avoid Cosmos DB access
        with patch("app.services.analysis_pipeline.run_analysis_pipeline"):
            with TestClient(app_with_mocks) as client:
                response = client.post(
                    "/api/v1/analysis-requests",
                    json={"source_url": "https://github.com/Azure-Samples/test-repo"},
                )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["source_url"] == "https://github.com/Azure-Samples/test-repo"
        assert "created" in data["meta"]["message"]

    def test_create_request_duplicate(self, client, mock_service, mock_analysis_request):
        """Test returning existing request for duplicate URL."""
        mock_service.create_request = AsyncMock(return_value=(mock_analysis_request, True))

        response = client.post(
            "/api/v1/analysis-requests",
            json={"source_url": "https://github.com/Azure-Samples/test-repo"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["meta"]["message"] == "Analysis request already exists"

    def test_create_request_invalid_url(self, client, mock_service):
        """Test rejection of non-GitHub URL after redirect resolution."""
        # Mock service to reject gitlab URL
        mock_service.validate_and_resolve_url = AsyncMock(
            return_value=(False, "https://gitlab.com/some/repo", "Final URL must be a GitHub repository. Got: gitlab.com")
        )

        response = client.post(
            "/api/v1/analysis-requests",
            json={"source_url": "https://gitlab.com/some/repo"},
        )

        # Should fail validation at service layer
        assert response.status_code == 400
        assert "GitHub" in response.json()["error"]["message"]

    def test_create_request_ssrf_blocked(self, client, mock_service):
        """Test SSRF protection blocks non-github domains."""
        mock_service.validate_and_resolve_url = AsyncMock(
            return_value=(False, "https://github.com/test/repo", "Domain not allowed")
        )

        response = client.post(
            "/api/v1/analysis-requests",
            json={"source_url": "https://github.com/test/repo"},
        )

        assert response.status_code == 400
        assert "Domain not allowed" in response.json()["error"]["message"]


class TestCreateAnalysisRequestNoAuth:
    """Test auth required for analysis endpoints."""

    def test_create_request_requires_auth(self):
        """Test that authentication is required."""
        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analysis-requests",
                json={"source_url": "https://github.com/test/repo"},
            )

            assert response.status_code == 401


class TestListAnalysisRequests:
    """Tests for GET /api/v1/analysis-requests."""

    def test_list_requests(self, client, mock_service, mock_analysis_request):
        """Test listing user's analysis requests."""
        mock_service.list_user_requests = AsyncMock(return_value=([mock_analysis_request], 1))

        response = client.get("/api/v1/analysis-requests")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) == 1
        assert data["data"]["total"] == 1

    def test_list_requests_with_pagination(self, client, mock_service, mock_analysis_request):
        """Test pagination parameters."""
        mock_service.list_user_requests = AsyncMock(return_value=([mock_analysis_request], 50))

        response = client.get("/api/v1/analysis-requests?page=1&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["page"] == 1
        assert data["data"]["limit"] == 10
        assert data["data"]["has_more"] is True

    def test_list_requests_with_status_filter(self, client, mock_service, mock_analysis_request):
        """Test filtering by status."""
        mock_service.list_user_requests = AsyncMock(return_value=([mock_analysis_request], 1))

        response = client.get("/api/v1/analysis-requests?status=pending")

        assert response.status_code == 200
        # Verify status filter was passed
        call_args = mock_service.list_user_requests.call_args
        assert call_args.kwargs.get("status") == AnalysisStatus.PENDING


class TestGetAnalysisRequest:
    """Tests for GET /api/v1/analysis-requests/{id}."""

    def test_get_request(self, client, mock_service, mock_analysis_request):
        """Test getting a specific request."""
        mock_service.get_request = AsyncMock(return_value=mock_analysis_request)

        response = client.get("/api/v1/analysis-requests/req-123")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == "req-123"
        assert "status_history" in data["data"]

    def test_get_request_not_found(self, client, mock_service):
        """Test 404 for non-existent request."""
        mock_service.get_request = AsyncMock(return_value=None)

        response = client.get("/api/v1/analysis-requests/nonexistent")

        assert response.status_code == 404


class TestDeleteAnalysisRequest:
    """Tests for DELETE /api/v1/analysis-requests/{id}."""

    def test_delete_request(self, client, mock_service):
        """Test deleting a request."""
        mock_service.delete_request = AsyncMock(return_value=True)

        response = client.delete("/api/v1/analysis-requests/req-123")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["deleted"] is True

    def test_delete_request_not_found(self, client, mock_service):
        """Test 404 when deleting non-existent request."""
        mock_service.delete_request = AsyncMock(return_value=False)

        response = client.delete("/api/v1/analysis-requests/nonexistent")

        assert response.status_code == 404


class TestCancelAnalysisRequest:
    """Tests for POST /api/v1/analysis-requests/{id}/cancel."""

    def test_cancel_request(self, client, mock_service, mock_analysis_request):
        """Test cancelling a pending request."""
        mock_analysis_request.status = AnalysisStatus.FAILED
        mock_service.cancel_request = AsyncMock(return_value=mock_analysis_request)

        response = client.post("/api/v1/analysis-requests/req-123/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["message"] == "Analysis request cancelled"

    def test_cancel_request_not_found(self, client, mock_service):
        """Test 404 when cancelling non-existent request."""
        mock_service.cancel_request = AsyncMock(return_value=None)

        response = client.post("/api/v1/analysis-requests/nonexistent/cancel")

        assert response.status_code == 404


class TestAnalysisServiceValidation:
    """Tests for AnalysisService URL validation."""

    def test_validate_github_url_valid(self):
        """Test valid GitHub URLs pass validation."""
        service = AnalysisService()

        valid_urls = [
            "https://github.com/Azure-Samples/azure-functions-python",
            "https://github.com/microsoft/vscode",
            "https://github.com/user/repo-name",
            "https://github.com/user123/my.dotted.repo",
        ]

        for url in valid_urls:
            is_valid, error = service.validate_url(url)
            assert is_valid is True, f"URL should be valid: {url}, got error: {error}"

    def test_validate_github_url_invalid(self):
        """Test invalid URLs are rejected."""
        service = AnalysisService()

        invalid_urls = [
            "https://gitlab.com/user/repo",
            "https://bitbucket.org/user/repo",
            "http://localhost:8080/test",
            "https://127.0.0.1/test",
            "file:///etc/passwd",
            "ftp://github.com/test/repo",
        ]

        for url in invalid_urls:
            is_valid, error = service.validate_url(url)
            assert is_valid is False, f"URL should be invalid: {url}"
