"""Tests for GitHub service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.services.github_service import (
    GitHubService,
    RepoInfo,
    GitHubError,
    RepoNotFoundError,
    RateLimitError,
)


class TestParseGitHubUrl:
    """Tests for GitHub URL parsing."""
    
    def test_parse_standard_url(self):
        """Test parsing standard GitHub URL."""
        service = GitHubService()
        owner, repo = service.parse_github_url("https://github.com/Azure-Samples/azure-functions-python")
        
        assert owner == "Azure-Samples"
        assert repo == "azure-functions-python"
    
    def test_parse_url_with_trailing_slash(self):
        """Test parsing URL with trailing slash."""
        service = GitHubService()
        owner, repo = service.parse_github_url("https://github.com/microsoft/vscode/")
        
        assert owner == "microsoft"
        assert repo == "vscode"
    
    def test_parse_url_with_git_extension(self):
        """Test parsing URL with .git extension."""
        service = GitHubService()
        owner, repo = service.parse_github_url("https://github.com/user/repo.git")
        
        assert owner == "user"
        assert repo == "repo"
    
    def test_parse_http_url(self):
        """Test parsing HTTP URL."""
        service = GitHubService()
        owner, repo = service.parse_github_url("http://github.com/user/repo")
        
        assert owner == "user"
        assert repo == "repo"
    
    def test_parse_invalid_url(self):
        """Test parsing invalid URL raises error."""
        service = GitHubService()
        
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            service.parse_github_url("https://gitlab.com/user/repo")
    
    def test_parse_url_with_extra_path(self):
        """Test parsing URL with extra path components."""
        service = GitHubService()
        
        # Extra path components should not match
        with pytest.raises(ValueError, match="Invalid GitHub URL"):
            service.parse_github_url("https://github.com/user/repo/tree/main")


class TestFetchRepoInfo:
    """Tests for fetching repository info."""
    
    @pytest.fixture
    def service(self):
        """Create service instance."""
        return GitHubService()
    
    @pytest.fixture
    def mock_response(self):
        """Create mock API response."""
        return {
            "description": "A test repository",
            "topics": ["python", "testing"],
            "language": "Python",
            "stargazers_count": 100,
            "forks_count": 25,
            "license": {"name": "MIT License"},
        }
    
    @pytest.mark.asyncio
    async def test_fetch_repo_info_success(self, service, mock_response):
        """Test successful repo info fetch."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: mock_response,
        )
        mock_client.is_closed = False
        service._client = mock_client
        
        repo_info = await service.fetch_repo_info("Azure-Samples", "test-repo")
        
        assert repo_info.owner == "Azure-Samples"
        assert repo_info.repo == "test-repo"
        assert repo_info.description == "A test repository"
        assert repo_info.stars == 100
        assert "python" in repo_info.topics
    
    @pytest.mark.asyncio
    async def test_fetch_repo_info_not_found(self, service):
        """Test 404 raises RepoNotFoundError."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = MagicMock(status_code=404)
        mock_client.is_closed = False
        service._client = mock_client
        
        with pytest.raises(RepoNotFoundError, match="Repository not found"):
            await service.fetch_repo_info("nonexistent", "repo")
    
    @pytest.mark.asyncio
    async def test_fetch_repo_info_rate_limited(self, service):
        """Test rate limit raises RateLimitError."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock(
            status_code=403,
            headers={"X-RateLimit-Remaining": "0"},
        )
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        service._client = mock_client
        
        with pytest.raises(RateLimitError, match="rate limit"):
            await service.fetch_repo_info("user", "repo")


class TestFetchReadme:
    """Tests for fetching README."""
    
    @pytest.fixture
    def service(self):
        """Create service instance."""
        return GitHubService()
    
    @pytest.mark.asyncio
    async def test_fetch_readme_success(self, service):
        """Test successful README fetch."""
        readme_content = "# Test Repo\n\nThis is a test."
        
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = MagicMock(
            status_code=200,
            text=readme_content,
        )
        mock_client.is_closed = False
        service._client = mock_client
        
        result = await service.fetch_readme("user", "repo")
        
        assert result == readme_content
    
    @pytest.mark.asyncio
    async def test_fetch_readme_not_found(self, service):
        """Test README not found returns None."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = MagicMock(status_code=404)
        mock_client.is_closed = False
        service._client = mock_client
        
        result = await service.fetch_readme("user", "repo")
        
        assert result is None


class TestFetchRepoWithReadme:
    """Tests for fetching complete repo info."""
    
    @pytest.mark.asyncio
    async def test_fetch_repo_with_readme(self):
        """Test fetching complete repo info with README."""
        service = GitHubService()
        
        # Mock fetch_repo_info
        service.fetch_repo_info = AsyncMock(
            return_value=RepoInfo(
                owner="user",
                repo="test",
                description="Test repo",
                stars=50,
            )
        )
        
        # Mock fetch_readme
        service.fetch_readme = AsyncMock(return_value="# Test README")
        
        result = await service.fetch_repo_with_readme("https://github.com/user/test")
        
        assert result.owner == "user"
        assert result.repo == "test"
        assert result.readme_content == "# Test README"
        assert result.description == "Test repo"


# Integration tests with real GitHub API
@pytest.mark.skip(reason="Requires network access to GitHub API")
class TestGitHubServiceIntegration:
    """Integration tests hitting real GitHub API."""
    
    @pytest.mark.asyncio
    async def test_fetch_real_repo(self):
        """Test fetching a real public repository."""
        service = GitHubService()
        
        try:
            repo_info = await service.fetch_repo_with_readme(
                "https://github.com/Azure-Samples/azure-functions-python"
            )
            
            assert repo_info.owner == "Azure-Samples"
            assert repo_info.readme_content is not None
            assert len(repo_info.readme_content) > 0
            
        finally:
            await service.close()
    
    @pytest.mark.asyncio
    async def test_fetch_nonexistent_repo(self):
        """Test fetching a non-existent repository."""
        service = GitHubService()
        
        try:
            with pytest.raises(RepoNotFoundError):
                await service.fetch_repo_info(
                    "this-user-definitely-does-not-exist-12345",
                    "neither-does-this-repo"
                )
        finally:
            await service.close()
