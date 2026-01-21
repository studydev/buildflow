"""Tests for analysis pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models.analysis import AnalysisRequest, AnalysisResult
from app.models.content import Content
from app.models.enums import AnalysisStatus, ContentType, ContentStatus
from app.services.analysis_pipeline import AnalysisPipeline, run_analysis_pipeline
from app.services.github_service import RepoInfo, GitHubError
from app.services.llm_service import LLMError


class TestAnalysisPipeline:
    """Tests for AnalysisPipeline class."""
    
    @pytest.fixture
    def mock_repo(self):
        """Create mock repository."""
        repo = MagicMock()
        repo.get_by_id = AsyncMock()
        repo.update = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_github_service(self):
        """Create mock GitHub service."""
        service = MagicMock()
        service.fetch_repo_with_readme = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_llm_service(self):
        """Create mock LLM service."""
        service = MagicMock()
        service.extract_metadata = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_content_service(self):
        """Create mock content service."""
        service = MagicMock()
        service.create_from_analysis = AsyncMock()
        return service
    
    @pytest.fixture
    def pipeline(self, mock_repo, mock_github_service, mock_llm_service, mock_content_service):
        """Create pipeline with mocked dependencies."""
        return AnalysisPipeline(
            repo=mock_repo,
            github_service=mock_github_service,
            llm_service=mock_llm_service,
            content_service=mock_content_service,
        )
    
    @pytest.fixture
    def sample_request(self):
        """Create sample analysis request."""
        return AnalysisRequest(
            id="req-123",
            user_id="user-456",
            source_url="https://github.com/test/repo",
            status=AnalysisStatus.PENDING,
        )
    
    @pytest.fixture
    def sample_repo_info(self):
        """Create sample repo info."""
        return RepoInfo(
            owner="test",
            repo="repo",
            readme_content="# Test Repo\nThis is a test.",
            description="A test repository",
            topics=["python", "testing"],
            language="Python",
            stars=50,
        )
    
    @pytest.fixture
    def sample_result(self):
        """Create sample analysis result."""
        return AnalysisResult(
            title="Test Repo",
            description="A test repository",
            content_type="sample",
            categories=["Python"],
            level="intermediate",
            technologies=["Python"],
        )
    
    @pytest.mark.asyncio
    async def test_process_request_success(
        self,
        pipeline,
        mock_repo,
        mock_github_service,
        mock_llm_service,
        mock_content_service,
        sample_request,
        sample_repo_info,
        sample_result,
    ):
        """Test successful pipeline processing."""
        mock_github_service.fetch_repo_with_readme.return_value = sample_repo_info
        mock_llm_service.extract_metadata.return_value = sample_result
        mock_repo.update.return_value = sample_request
        
        # Mock content creation
        mock_content = Content(
            id="content-123",
            contributor_id=sample_request.user_id,
            title=sample_result.title,
            description=sample_result.description or "",
            source_url=sample_request.source_url,
        )
        mock_content_service.create_from_analysis.return_value = mock_content
        
        result = await pipeline.process_request(sample_request)
        
        # Verify all stages were called
        mock_github_service.fetch_repo_with_readme.assert_called_once_with(
            sample_request.source_url
        )
        mock_llm_service.extract_metadata.assert_called_once()
        mock_content_service.create_from_analysis.assert_called_once()
        
        # Verify content was linked
        assert "content-123" in result.content_ids
        
        # Verify status updates were persisted
        assert mock_repo.update.call_count >= 2  # At least fetch and complete
    
    @pytest.mark.asyncio
    async def test_process_request_github_error(
        self,
        pipeline,
        mock_repo,
        mock_github_service,
        sample_request,
    ):
        """Test pipeline handles GitHub errors."""
        mock_github_service.fetch_repo_with_readme.side_effect = GitHubError("API error")
        mock_repo.update.return_value = sample_request
        
        result = await pipeline.process_request(sample_request)
        
        assert result.status == AnalysisStatus.FAILED
        assert "GitHub error" in result.error_message
    
    @pytest.mark.asyncio
    async def test_process_request_no_readme(
        self,
        pipeline,
        mock_repo,
        mock_github_service,
        sample_request,
    ):
        """Test pipeline handles missing README."""
        mock_github_service.fetch_repo_with_readme.return_value = RepoInfo(
            owner="test",
            repo="repo",
            readme_content=None,  # No README
        )
        mock_repo.update.return_value = sample_request
        
        result = await pipeline.process_request(sample_request)
        
        assert result.status == AnalysisStatus.FAILED
        assert "No README" in result.error_message
    
    @pytest.mark.asyncio
    async def test_process_request_llm_error(
        self,
        pipeline,
        mock_repo,
        mock_github_service,
        mock_llm_service,
        sample_request,
        sample_repo_info,
    ):
        """Test pipeline handles LLM errors."""
        mock_github_service.fetch_repo_with_readme.return_value = sample_repo_info
        mock_llm_service.extract_metadata.side_effect = LLMError("LLM API error")
        mock_repo.update.return_value = sample_request
        
        result = await pipeline.process_request(sample_request)
        
        assert result.status == AnalysisStatus.FAILED
        assert "LLM error" in result.error_message


class TestRunAnalysisPipeline:
    """Tests for run_analysis_pipeline function."""
    
    @pytest.mark.asyncio
    async def test_run_pipeline_not_found(self):
        """Test pipeline returns None for non-existent request."""
        with patch("app.services.analysis_pipeline.get_analysis_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            mock_get_repo.return_value = mock_repo
            
            result = await run_analysis_pipeline("nonexistent", "user-123")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_run_pipeline_skips_non_pending(self):
        """Test pipeline skips requests not in pending status."""
        completed_request = AnalysisRequest(
            id="req-123",
            user_id="user-456",
            source_url="https://github.com/test/repo",
        )
        completed_request.update_status(AnalysisStatus.COMPLETED)
        
        with patch("app.services.analysis_pipeline.get_analysis_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=completed_request)
            mock_get_repo.return_value = mock_repo
            
            result = await run_analysis_pipeline("req-123", "user-456")
            
            # Should return without processing
            assert result.status == AnalysisStatus.COMPLETED


class TestPipelineProgressTracking:
    """Tests for pipeline progress tracking."""
    
    @pytest.fixture
    def mock_content_service(self):
        """Create mock content service."""
        service = MagicMock()
        service.create_from_analysis = AsyncMock(return_value=Content(
            id="content-123",
            contributor_id="user-456",
            title="Test",
            description="Test description",
            source_url="https://github.com/test/repo",
        ))
        return service
    
    @pytest.fixture
    def pipeline_with_mocks(self, mock_content_service):
        """Create pipeline with progress tracking mocks."""
        repo = MagicMock()
        repo.update = AsyncMock(side_effect=lambda r: r)
        
        github = MagicMock()
        github.fetch_repo_with_readme = AsyncMock(return_value=RepoInfo(
            owner="test",
            repo="repo",
            readme_content="# Test",
        ))
        
        llm = MagicMock()
        llm.extract_metadata = AsyncMock(return_value=AnalysisResult(
            title="Test",
            categories=["Test"],
        ))
        
        return AnalysisPipeline(
            repo=repo,
            github_service=github,
            llm_service=llm,
            content_service=mock_content_service,
        )
    
    @pytest.mark.asyncio
    async def test_progress_updates_through_stages(self, pipeline_with_mocks):
        """Test progress is updated through pipeline stages."""
        request = AnalysisRequest(
            id="req-123",
            user_id="user-456",
            source_url="https://github.com/test/repo",
        )
        
        result = await pipeline_with_mocks.process_request(request)
        
        # Final progress should be 100%
        assert result.progress == 100
        assert result.status == AnalysisStatus.COMPLETED
        
        # Content should be created
        assert len(result.content_ids) == 1
        assert result.content_ids[0] == "content-123"
        
        # Status history should have entries for each stage
        assert len(result.status_history) >= 3  # PENDING, FETCHING, PARSING, COMPLETED


class TestContentCreationFromAnalysis:
    """Tests for Content creation during analysis pipeline."""
    
    @pytest.fixture
    def mock_content_service(self):
        """Create mock content service."""
        service = MagicMock()
        service.create_from_analysis = AsyncMock()
        return service
    
    @pytest.fixture
    def full_pipeline(self, mock_content_service):
        """Create pipeline with all mocks."""
        repo = MagicMock()
        repo.update = AsyncMock(side_effect=lambda r: r)
        
        github = MagicMock()
        github.fetch_repo_with_readme = AsyncMock(return_value=RepoInfo(
            owner="Azure-Samples",
            repo="azure-functions-python",
            readme_content="# Azure Functions\nBuild serverless applications.",
            description="Sample Azure Functions",
            topics=["azure", "serverless", "python"],
            language="Python",
            stars=1500,
        ))
        
        llm = MagicMock()
        llm.extract_metadata = AsyncMock(return_value=AnalysisResult(
            title="Azure Functions Python Sample",
            description="Learn to build serverless applications with Azure Functions",
            content_type="sample",
            categories=["Azure", "Serverless"],
            level="intermediate",
            duration_minutes=90,
            technologies=["Python", "Azure Functions"],
        ))
        
        return AnalysisPipeline(
            repo=repo,
            github_service=github,
            llm_service=llm,
            content_service=mock_content_service,
        )
    
    @pytest.mark.asyncio
    async def test_content_created_from_analysis_result(self, full_pipeline, mock_content_service):
        """Test Content is created from analysis result."""
        # Setup mock content
        created_content = Content(
            id="new-content-id",
            contributor_id="user-123",
            title="Azure Functions Python Sample",
            description="Learn to build serverless applications with Azure Functions",
            source_url="https://github.com/Azure-Samples/azure-functions-python",
        )
        mock_content_service.create_from_analysis.return_value = created_content
        
        request = AnalysisRequest(
            id="req-456",
            user_id="user-123",
            source_url="https://github.com/Azure-Samples/azure-functions-python",
        )
        
        result = await full_pipeline.process_request(request)
        
        # Verify content service was called with correct parameters
        mock_content_service.create_from_analysis.assert_called_once()
        call_args = mock_content_service.create_from_analysis.call_args
        assert call_args.kwargs["contributor_id"] == "user-123"
        assert call_args.kwargs["source_url"] == "https://github.com/Azure-Samples/azure-functions-python"
        assert call_args.kwargs["result"].title == "Azure Functions Python Sample"
        
        # Verify content ID was linked
        assert "new-content-id" in result.content_ids
    
    @pytest.mark.asyncio
    async def test_content_creation_failure_does_not_fail_pipeline(self, full_pipeline, mock_content_service):
        """Test pipeline completes even if content creation fails."""
        mock_content_service.create_from_analysis.side_effect = Exception("Database error")
        
        request = AnalysisRequest(
            id="req-789",
            user_id="user-123",
            source_url="https://github.com/Azure-Samples/azure-functions-python",
        )
        
        result = await full_pipeline.process_request(request)
        
        # Pipeline should still complete
        assert result.status == AnalysisStatus.COMPLETED
        # But no content IDs
        assert len(result.content_ids) == 0


class TestPipelineRetryLogic:
    """Tests for pipeline retry logic with exponential backoff."""
    
    @pytest.fixture
    def mock_repo(self):
        """Create mock repository."""
        repo = MagicMock()
        repo.update = AsyncMock(side_effect=lambda r: r)
        return repo
    
    @pytest.fixture
    def mock_content_service(self):
        """Create mock content service."""
        service = MagicMock()
        service.create_from_analysis = AsyncMock(return_value=Content(
            id="content-123",
            contributor_id="user-456",
            title="Test",
            description="Test description",
            source_url="https://github.com/test/repo",
        ))
        return service
    
    @pytest.mark.asyncio
    async def test_github_retry_on_rate_limit(self, mock_repo, mock_content_service):
        """Test GitHub fetch retries on rate limit error."""
        from app.services.github_service import RateLimitError
        
        github_service = MagicMock()
        github_service.fetch_repo_with_readme = AsyncMock(
            side_effect=[
                RateLimitError("Rate limit exceeded"),
                RateLimitError("Rate limit exceeded"),
                RepoInfo(owner="test", repo="repo", readme_content="# Test"),
            ]
        )
        
        llm_service = MagicMock()
        llm_service.extract_metadata = AsyncMock(return_value=AnalysisResult(
            title="Test",
            categories=["Test"],
        ))
        
        pipeline = AnalysisPipeline(
            repo=mock_repo,
            github_service=github_service,
            llm_service=llm_service,
            content_service=mock_content_service,
        )
        
        request = AnalysisRequest(
            id="req-retry-1",
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )
        
        # Use patching to speed up delays
        with patch("app.services.analysis_pipeline.GITHUB_RETRY_CONFIG") as mock_config:
            from app.core.retry import RetryConfig
            mock_config.max_attempts = 3
            mock_config.calculate_delay = MagicMock(return_value=0.01)
            
            result = await pipeline.process_request(request)
        
        # Should eventually succeed
        assert result.status == AnalysisStatus.COMPLETED
        assert github_service.fetch_repo_with_readme.call_count == 3
    
    @pytest.mark.asyncio
    async def test_github_retry_on_connection_error(self, mock_repo, mock_content_service):
        """Test GitHub fetch retries on connection error."""
        github_service = MagicMock()
        github_service.fetch_repo_with_readme = AsyncMock(
            side_effect=[
                ConnectionError("Network unreachable"),
                RepoInfo(owner="test", repo="repo", readme_content="# Test"),
            ]
        )
        
        llm_service = MagicMock()
        llm_service.extract_metadata = AsyncMock(return_value=AnalysisResult(
            title="Test",
            categories=["Test"],
        ))
        
        pipeline = AnalysisPipeline(
            repo=mock_repo,
            github_service=github_service,
            llm_service=llm_service,
            content_service=mock_content_service,
        )
        
        request = AnalysisRequest(
            id="req-retry-2",
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )
        
        with patch("app.services.analysis_pipeline.GITHUB_RETRY_CONFIG") as mock_config:
            mock_config.max_attempts = 3
            mock_config.calculate_delay = MagicMock(return_value=0.01)
            
            result = await pipeline.process_request(request)
        
        # Should succeed after retry
        assert result.status == AnalysisStatus.COMPLETED
        assert github_service.fetch_repo_with_readme.call_count == 2
    
    @pytest.mark.asyncio
    async def test_github_fails_after_max_retries(self, mock_repo, mock_content_service):
        """Test GitHub fetch fails after max retries."""
        from app.services.github_service import RateLimitError
        
        github_service = MagicMock()
        github_service.fetch_repo_with_readme = AsyncMock(
            side_effect=RateLimitError("Rate limit exceeded")
        )
        
        pipeline = AnalysisPipeline(
            repo=mock_repo,
            github_service=github_service,
            llm_service=MagicMock(),
            content_service=mock_content_service,
        )
        
        request = AnalysisRequest(
            id="req-retry-3",
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )
        
        with patch("app.services.analysis_pipeline.GITHUB_RETRY_CONFIG") as mock_config:
            mock_config.max_attempts = 3
            mock_config.calculate_delay = MagicMock(return_value=0.01)
            
            result = await pipeline.process_request(request)
        
        # Should fail after all retries
        assert result.status == AnalysisStatus.FAILED
        assert "3 attempts" in result.error_message
        assert github_service.fetch_repo_with_readme.call_count == 3
    
    @pytest.mark.asyncio
    async def test_llm_retry_on_api_error(self, mock_repo, mock_content_service):
        """Test LLM parsing retries on API error."""
        from app.services.llm_service import LLMAPIError
        
        github_service = MagicMock()
        github_service.fetch_repo_with_readme = AsyncMock(
            return_value=RepoInfo(owner="test", repo="repo", readme_content="# Test")
        )
        
        llm_service = MagicMock()
        llm_service.extract_metadata = AsyncMock(
            side_effect=[
                LLMAPIError("Service unavailable"),
                AnalysisResult(title="Test", categories=["Test"]),
            ]
        )
        
        pipeline = AnalysisPipeline(
            repo=mock_repo,
            github_service=github_service,
            llm_service=llm_service,
            content_service=mock_content_service,
        )
        
        request = AnalysisRequest(
            id="req-retry-4",
            user_id="user-123",
            source_url="https://github.com/test/repo",
        )
        
        with patch("app.services.analysis_pipeline.LLM_RETRY_CONFIG") as mock_config:
            mock_config.max_attempts = 3
            mock_config.calculate_delay = MagicMock(return_value=0.01)
            
            result = await pipeline.process_request(request)
        
        # Should succeed after retry
        assert result.status == AnalysisStatus.COMPLETED
        assert llm_service.extract_metadata.call_count == 2
    
    @pytest.mark.asyncio
    async def test_non_retryable_github_error(self, mock_repo, mock_content_service):
        """Test non-retryable GitHub errors fail immediately."""
        from app.services.github_service import RepoNotFoundError
        
        github_service = MagicMock()
        github_service.fetch_repo_with_readme = AsyncMock(
            side_effect=RepoNotFoundError("Repository not found")
        )
        
        pipeline = AnalysisPipeline(
            repo=mock_repo,
            github_service=github_service,
            llm_service=MagicMock(),
            content_service=mock_content_service,
        )
        
        request = AnalysisRequest(
            id="req-no-retry",
            user_id="user-123",
            source_url="https://github.com/nonexistent/repo",
        )
        
        result = await pipeline.process_request(request)
        
        # Should fail immediately without retry
        assert result.status == AnalysisStatus.FAILED
        assert "GitHub error" in result.error_message
        # Only one call (no retries for 404)
        assert github_service.fetch_repo_with_readme.call_count == 1
