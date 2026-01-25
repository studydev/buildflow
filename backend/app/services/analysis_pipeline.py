"""Analysis pipeline orchestrator for processing GitHub repositories."""

import asyncio
import logging
from typing import Optional

from app.core.retry import RetryConfig, RetryError
from app.models.analysis import AnalysisRequest
from app.models.enums import AnalysisStatus
from app.repositories.analysis_repo import AnalysisRequestRepository, get_analysis_repo
from app.services.content_service import ContentService, get_content_service
from app.services.github_service import (
    GitHubError,
    GitHubService,
    RateLimitError,
    get_github_service,
)
from app.services.llm_service import LLMAPIError, LLMError, LLMService, get_llm_service

logger = logging.getLogger(__name__)


# Retry configurations for different services
GITHUB_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    retryable_exceptions=(GitHubError, ConnectionError, TimeoutError),
)

LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=3.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    retryable_exceptions=(LLMAPIError, ConnectionError, TimeoutError),
)


class AnalysisPipeline:
    """
    Orchestrates the analysis pipeline for GitHub repositories.

    Pipeline stages:
    1. PENDING -> FETCHING: Fetch repository data from GitHub
    2. FETCHING -> PARSING: Extract metadata using LLM
    3. PARSING -> COMPLETED: Create Content and store results

    On failure at any stage: -> FAILED
    """

    # Progress percentages for each stage
    PROGRESS_PENDING = 0
    PROGRESS_FETCHING = 25
    PROGRESS_PARSING = 50
    PROGRESS_CREATING = 75
    PROGRESS_COMPLETED = 100

    def __init__(
        self,
        repo: Optional[AnalysisRequestRepository] = None,
        github_service: Optional[GitHubService] = None,
        llm_service: Optional[LLMService] = None,
        content_service: Optional[ContentService] = None,
    ):
        """
        Initialize pipeline with services.

        Args:
            repo: Analysis request repository
            github_service: GitHub service for fetching repos
            llm_service: LLM service for metadata extraction
            content_service: Content service for creating content
        """
        self._repo = repo
        self._github_service = github_service
        self._llm_service = llm_service
        self._content_service = content_service

    @property
    def repo(self) -> AnalysisRequestRepository:
        """Get repository instance."""
        if self._repo is None:
            self._repo = get_analysis_repo()
        return self._repo

    @property
    def github_service(self) -> GitHubService:
        """Get GitHub service instance."""
        if self._github_service is None:
            self._github_service = get_github_service()
        return self._github_service

    @property
    def llm_service(self) -> LLMService:
        """Get LLM service instance."""
        if self._llm_service is None:
            self._llm_service = get_llm_service()
        return self._llm_service

    @property
    def content_service(self) -> ContentService:
        """Get content service instance."""
        if self._content_service is None:
            self._content_service = get_content_service()
        return self._content_service

    async def process_request(self, request: AnalysisRequest) -> AnalysisRequest:
        """
        Process an analysis request through all pipeline stages.

        Args:
            request: The analysis request to process

        Returns:
            Updated analysis request with results or error
        """
        logger.info(f"Starting pipeline for request {request.id}")

        try:
            # Stage 1: Fetch from GitHub
            request = await self._stage_fetch(request)
            if request.status == AnalysisStatus.FAILED:
                return request

            # Stage 2: Parse with LLM
            request = await self._stage_parse(request)
            if request.status == AnalysisStatus.FAILED:
                return request

            # Stage 3: Create Content from extracted metadata
            request = await self._stage_create_content(request)
            if request.status == AnalysisStatus.FAILED:
                return request

            # Stage 4: Complete
            request = await self._stage_complete(request)

            logger.info(f"Pipeline completed for request {request.id}")
            return request

        except Exception as e:
            logger.error(f"Pipeline failed for request {request.id}: {e}")
            return await self._handle_failure(request, str(e))

    async def _stage_fetch(self, request: AnalysisRequest) -> AnalysisRequest:
        """
        Stage 1: Fetch repository data from GitHub.

        Updates status to FETCHING, fetches repo info and README.
        Includes retry logic with exponential backoff for network errors.
        """
        logger.info(f"Fetching repository data for {request.source_url}")

        # Update status
        request = await self._update_status(
            request,
            AnalysisStatus.FETCHING,
            "Fetching repository data from GitHub",
            self.PROGRESS_FETCHING,
        )

        try:
            repo_info = await self._fetch_with_retry(request.source_url)

            if not repo_info.readme_content:
                return await self._handle_failure(
                    request,
                    "No README found in repository",
                )

            # Store fetched data in request (transient, used by next stage)
            request._repo_info = repo_info

            return request

        except RetryError as e:
            return await self._handle_failure(
                request,
                f"GitHub error after {GITHUB_RETRY_CONFIG.max_attempts} attempts: {e.last_exception}",
            )
        except GitHubError as e:
            return await self._handle_failure(request, f"GitHub error: {e}")

    async def _fetch_with_retry(self, source_url: str):
        """
        Fetch repository with retry logic.

        Args:
            source_url: GitHub repository URL

        Returns:
            RepoInfo with repository data

        Raises:
            RetryError: After all retry attempts fail
            GitHubError: For non-retryable errors (e.g., 404)
        """
        last_exception = None

        for attempt in range(GITHUB_RETRY_CONFIG.max_attempts):
            try:
                return await self.github_service.fetch_repo_with_readme(source_url)
            except RateLimitError as e:
                # Rate limit is always retryable
                last_exception = e
                if attempt < GITHUB_RETRY_CONFIG.max_attempts - 1:
                    delay = GITHUB_RETRY_CONFIG.calculate_delay(attempt)
                    logger.warning(
                        f"GitHub rate limit hit (attempt {attempt + 1}/{GITHUB_RETRY_CONFIG.max_attempts}). "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            except (ConnectionError, TimeoutError) as e:
                # Network errors are retryable
                last_exception = e
                if attempt < GITHUB_RETRY_CONFIG.max_attempts - 1:
                    delay = GITHUB_RETRY_CONFIG.calculate_delay(attempt)
                    logger.warning(
                        f"Network error fetching from GitHub (attempt {attempt + 1}/{GITHUB_RETRY_CONFIG.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            except GitHubError:
                # Non-retryable GitHub errors (e.g., 404 Not Found)
                raise

        raise RetryError(
            f"GitHub fetch failed after {GITHUB_RETRY_CONFIG.max_attempts} attempts",
            last_exception=last_exception,
        )

    async def _stage_parse(self, request: AnalysisRequest) -> AnalysisRequest:
        """
        Stage 2: Parse content using LLM.

        Extracts structured metadata from README.
        Includes retry logic with exponential backoff for API errors.
        """
        logger.info(f"Parsing content for request {request.id}")

        # Update status
        request = await self._update_status(
            request,
            AnalysisStatus.PARSING,
            "Extracting metadata from content",
            self.PROGRESS_PARSING,
        )

        try:
            repo_info = getattr(request, '_repo_info', None)
            if not repo_info:
                return await self._handle_failure(
                    request,
                    "Missing repository data from fetch stage",
                )

            result = await self._parse_with_retry(repo_info)

            # Merge GitHub metadata from repo_info into result
            result.stars = repo_info.stars
            result.forks = repo_info.forks
            result.watchers = repo_info.watchers
            result.language = repo_info.language
            result.license = repo_info.license
            result.topics = ", ".join(repo_info.topics) if repo_info.topics else None
            result.owner = repo_info.owner
            result.contributors = repo_info.contributors_str
            result.contributors_count = repo_info.contributors_count
            result.created_at = repo_info.created_at
            result.updated_at = repo_info.updated_at
            result.source_url = request.source_url
            result.homepage_url = repo_info.homepage_url

            # Store result in request (don't mark as completed yet)
            request.result = result
            request._analysis_result = result  # Transient for next stage

            return request

        except RetryError as e:
            return await self._handle_failure(
                request,
                f"LLM error after {LLM_RETRY_CONFIG.max_attempts} attempts: {e.last_exception}",
            )
        except LLMError as e:
            return await self._handle_failure(request, f"LLM error: {e}")

    async def _parse_with_retry(self, repo_info):
        """
        Parse repository content with retry logic.

        Args:
            repo_info: Repository information including README content

        Returns:
            AnalysisResult with extracted metadata

        Raises:
            RetryError: After all retry attempts fail
            LLMError: For non-retryable errors (e.g., configuration errors)
        """
        from app.services.llm_service import LLMConfigError

        last_exception = None

        for attempt in range(LLM_RETRY_CONFIG.max_attempts):
            try:
                return await self.llm_service.extract_metadata(
                    readme_content=repo_info.readme_content,
                    repo_description=repo_info.description,
                    repo_topics=repo_info.topics,
                    repo_language=repo_info.language,
                    repo_stars=repo_info.stars,
                )
            except LLMAPIError as e:
                # API errors are retryable
                last_exception = e
                if attempt < LLM_RETRY_CONFIG.max_attempts - 1:
                    delay = LLM_RETRY_CONFIG.calculate_delay(attempt)
                    logger.warning(
                        f"LLM API error (attempt {attempt + 1}/{LLM_RETRY_CONFIG.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            except (ConnectionError, TimeoutError) as e:
                # Network errors are retryable
                last_exception = e
                if attempt < LLM_RETRY_CONFIG.max_attempts - 1:
                    delay = LLM_RETRY_CONFIG.calculate_delay(attempt)
                    logger.warning(
                        f"Network error calling LLM (attempt {attempt + 1}/{LLM_RETRY_CONFIG.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            except LLMConfigError:
                # Configuration errors are not retryable
                raise
            except LLMError:
                # Other LLM errors are not retryable by default
                raise

        raise RetryError(
            f"LLM parse failed after {LLM_RETRY_CONFIG.max_attempts} attempts",
            last_exception=last_exception,
        )

    async def _stage_create_content(self, request: AnalysisRequest) -> AnalysisRequest:
        """
        Stage 3: Create Content from extracted metadata.

        Creates a Content record in draft status linked to the analysis request.
        """
        logger.info(f"Creating content for request {request.id}")

        # Update status
        request = await self._update_status(
            request,
            AnalysisStatus.PARSING,  # Still in parsing phase conceptually
            "Creating content from extracted metadata",
            self.PROGRESS_CREATING,
        )

        try:
            result = getattr(request, '_analysis_result', None) or request.result
            if not result:
                return await self._handle_failure(
                    request,
                    "Missing analysis result from parse stage",
                )

            # Create Content from analysis result
            content = await self.content_service.create_from_analysis(
                contributor_id=request.user_id,
                source_url=request.source_url,
                result=result,
                analysis_request_id=request.id,
            )

            # Link content to request
            request.content_ids.append(content.id)

            logger.info(f"Created content {content.id} for request {request.id}")
            return request

        except Exception as e:
            logger.error(f"Failed to create content: {e}")
            # Content creation failure is not fatal, continue to complete
            # but log the error
            return request

    async def _stage_complete(self, request: AnalysisRequest) -> AnalysisRequest:
        """
        Stage 4: Mark as completed and persist.
        """
        logger.info(f"Completing request {request.id}")

        # Build completion message with content count
        content_count = len(request.content_ids)
        if content_count > 0:
            message = f"Analysis completed successfully. Created {content_count} content item(s)."
        else:
            message = "Analysis completed successfully."

        # Update to completed status
        request = await self._update_status(
            request,
            AnalysisStatus.COMPLETED,
            message,
            self.PROGRESS_COMPLETED,
        )

        return request

    async def _update_status(
        self,
        request: AnalysisRequest,
        status: AnalysisStatus,
        message: str,
        progress: int,
    ) -> AnalysisRequest:
        """Update request status and persist to database."""
        request.update_status(status, message=message, progress=progress)

        try:
            updated = await self.repo.update(request)
            return updated if updated else request
        except Exception as e:
            logger.error(f"Failed to persist status update: {e}")
            # Continue with in-memory request
            return request

    async def _handle_failure(
        self,
        request: AnalysisRequest,
        error_message: str,
    ) -> AnalysisRequest:
        """Handle pipeline failure."""
        logger.error(f"Request {request.id} failed: {error_message}")

        request.set_error(error_message)

        try:
            updated = await self.repo.update(request)
            return updated if updated else request
        except Exception as e:
            logger.error(f"Failed to persist failure status: {e}")
            return request


async def run_analysis_pipeline(request_id: str, user_id: str) -> Optional[AnalysisRequest]:
    """
    Run the analysis pipeline for a specific request.

    This is the entry point for background processing.

    Args:
        request_id: The analysis request ID
        user_id: The user ID (partition key)

    Returns:
        Updated analysis request, or None if not found
    """
    pipeline = AnalysisPipeline()

    # Fetch request from database
    request = await pipeline.repo.get_by_id(request_id, user_id)
    if not request:
        logger.error(f"Request not found: {request_id}")
        return None

    # Only process pending requests
    if request.status != AnalysisStatus.PENDING:
        logger.warning(
            f"Request {request_id} is not pending (status: {request.status})"
        )
        return request

    # Run pipeline
    return await pipeline.process_request(request)


# Singleton instance
_pipeline: Optional[AnalysisPipeline] = None


def get_analysis_pipeline() -> AnalysisPipeline:
    """Get the analysis pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = AnalysisPipeline()
    return _pipeline
