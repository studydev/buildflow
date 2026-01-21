"""
AnalysisPipeline class per design.md §3.1 and tasks.md T201-T204.

This pipeline extracts raw data from GitHub repositories:
1. Validates source URL (T202)
2. Checks idempotency (T203)
3. Fetches comprehensive data from GitHub (T200)
4. Stores as immutable RawExtraction
5. Creates or updates Content skeleton with raw_extraction_id
6. Triggers next pipeline if chain specified
"""

import asyncio
import hashlib
import ipaddress
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse
from uuid import UUID, uuid4

from app.models.enums import ContentStatus, PipelineType
from app.models.raw_extraction import RawExtraction
from app.pipelines.base import BasePipeline
from app.repositories.raw_extraction_repo import get_raw_extraction_repository
from app.schemas.pipeline import PipelineMessage
from app.services.github_service import (
    ComprehensiveRepoExtraction,
    GitHubError,
    GitHubService,
    RateLimitError,
    RepoNotFoundError,
    get_github_service,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Error Classes for Analysis Pipeline
# =============================================================================


class AnalysisPipelineError(Exception):
    """Base exception for analysis pipeline errors."""
    pass


class InvalidURLError(AnalysisPipelineError):
    """URL validation failed."""
    pass


class IdempotencySkipError(AnalysisPipelineError):
    """Extraction skipped due to idempotency."""
    pass


class NetworkTimeoutError(AnalysisPipelineError):
    """Network timeout during GitHub fetch."""
    pass


# =============================================================================
# Analysis Pipeline Configuration (per design.md §3.1)
# =============================================================================


# Retry configuration per design.md §3.1 retry_policy
ANALYSIS_MAX_ATTEMPTS = 3
ANALYSIS_BACKOFF_BASE = 2  # 2s, 4s, 8s

# Idempotency window per design.md §3.1 idempotency_strategy
IDEMPOTENCY_WINDOW_HOURS = 24


# =============================================================================
# Analysis Pipeline Implementation
# =============================================================================


class AnalysisPipeline(BasePipeline):
    """
    Analysis Pipeline per design.md §3.1.

    Purpose: Extract raw data from GitHub repositories.

    Execution flow:
    1. Validate URL (T202)
    2. Check idempotency (T203)
    3. Fetch from GitHub (T200)
    4. Store RawExtraction (immutable)
    5. Create/update Content skeleton
    6. Trigger next pipeline if chain specified
    """

    pipeline_type = PipelineType.ANALYSIS
    max_attempts = ANALYSIS_MAX_ATTEMPTS

    def __init__(self):
        super().__init__()
        self._github_service: Optional[GitHubService] = None
        self._raw_extraction_repo = None
        self._content_service = None
        self._pipeline_service = None

    @property
    def github_service(self) -> GitHubService:
        """Lazy load GitHub service."""
        if self._github_service is None:
            self._github_service = get_github_service()
        return self._github_service

    @property
    def raw_extraction_repo(self):
        """Lazy load raw extraction repository."""
        if self._raw_extraction_repo is None:
            self._raw_extraction_repo = get_raw_extraction_repository()
        return self._raw_extraction_repo

    @property
    def content_service(self):
        """Lazy load content service."""
        if self._content_service is None:
            from app.services.content_service import get_content_service
            self._content_service = get_content_service()
        return self._content_service

    @property
    def pipeline_service(self):
        """Lazy load pipeline service."""
        if self._pipeline_service is None:
            from app.services.pipeline_service import get_pipeline_service
            self._pipeline_service = get_pipeline_service()
        return self._pipeline_service

    # =========================================================================
    # Main Execution
    # =========================================================================

    async def execute(self, message: PipelineMessage) -> dict[str, Any]:
        """
        Execute analysis pipeline logic.

        Per design.md §3.1 and tasks.md T201.

        Args:
            message: Pipeline message with source_url in input_params

        Returns:
            Dict with extraction results

        Raises:
            InvalidURLError: URL validation failed (non-retryable)
            IdempotencySkipError: Already extracted recently
            NetworkTimeoutError: GitHub timeout (retryable)
            RateLimitError: GitHub rate limit (retryable)
            GitHubError: Other GitHub errors
        """
        # Extract input parameters
        source_url = message.input_params.get("source_url")
        force_refresh = message.input_params.get("force_refresh", False)

        if not source_url:
            raise InvalidURLError("source_url is required in input_params")

        logger.info(
            "Starting analysis execution",
            extra={
                "run_id": str(message.run_id),
                "source_url": source_url,
                "force_refresh": force_refresh,
                "correlation_id": message.correlation_id,
            }
        )

        # Step 1: Validate URL (T202)
        self._validate_url(source_url)

        # Step 2: Check idempotency (T203)
        source_url_hash = hashlib.sha256(source_url.encode()).hexdigest()

        existing = await self._check_idempotency(source_url_hash, force_refresh)
        if existing:
            logger.info(
                "Skipping extraction due to idempotency",
                extra={
                    "run_id": str(message.run_id),
                    "existing_extraction_id": str(existing.id),
                    "source_url": source_url,
                }
            )
            return {
                "skipped": True,
                "reason": "existing_extraction_within_24h",
                "existing_extraction_id": str(existing.id),
                "extracted_at": existing.extracted_at.isoformat(),
            }

        # Step 3: Fetch from GitHub with retry (T200, T204)
        extraction_data = await self._fetch_with_retry(source_url, message)

        # Step 4: Store as RawExtraction
        raw_extraction = await self._store_raw_extraction(
            extraction_data,
            message.run_id
        )

        # Step 5: Create or update Content skeleton
        content_id = await self._update_content_skeleton(
            source_url=source_url,
            raw_extraction_id=raw_extraction.id,
            message=message,
            extraction_data=extraction_data,
        )

        logger.info(
            "Analysis execution completed",
            extra={
                "run_id": str(message.run_id),
                "raw_extraction_id": str(raw_extraction.id),
                "content_id": str(content_id) if content_id else None,
                "source_url": source_url,
            }
        )

        return {
            "skipped": False,
            "raw_extraction_id": str(raw_extraction.id),
            "content_id": str(content_id) if content_id else None,
            "source_url": source_url,
            "repository_metadata": extraction_data.repository_metadata,
            "commit_activity": extraction_data.commit_activity,
            "releases": extraction_data.releases,
            "extracted_urls": extraction_data.extracted_urls,
            "extracted_at": extraction_data.extracted_at.isoformat(),
        }

    # =========================================================================
    # Step 1: URL Validation (T202)
    # =========================================================================

    def _validate_url(self, source_url: str) -> None:
        """
        Validate source URL per T202 requirements.

        Checks:
        - HTTPS only (not HTTP)
        - github.com domain only
        - No IP addresses
        - Valid repository path format (owner/repo)

        Raises:
            InvalidURLError: If validation fails
        """
        try:
            parsed = urlparse(source_url)
        except Exception as e:
            raise InvalidURLError(f"Failed to parse URL: {e}")

        # Check HTTPS only
        if parsed.scheme != "https":
            raise InvalidURLError(
                f"Only HTTPS URLs allowed. Got: {parsed.scheme}://"
            )

        # Check for IP address (reject)
        hostname = parsed.hostname or ""
        try:
            ipaddress.ip_address(hostname)
            raise InvalidURLError(f"IP addresses not allowed: {hostname}")
        except ValueError:
            pass  # Not an IP address, continue

        # Check github.com domain
        if not hostname.endswith("github.com"):
            raise InvalidURLError(
                f"Only github.com URLs allowed. Got: {hostname}"
            )

        # Check valid repo path format: /owner/repo
        path = parsed.path.strip("/")
        parts = path.split("/")

        if len(parts) < 2:
            raise InvalidURLError(
                f"Invalid repository path. Expected: github.com/owner/repo. Got: {path}"
            )

        owner, repo = parts[0], parts[1].replace(".git", "")

        # Validate owner and repo are non-empty alphanumeric with dashes
        if not re.match(r'^[\w.-]+$', owner):
            raise InvalidURLError(f"Invalid repository owner: {owner}")

        if not re.match(r'^[\w.-]+$', repo):
            raise InvalidURLError(f"Invalid repository name: {repo}")

        logger.debug(f"URL validated: {source_url} -> {owner}/{repo}")

    # =========================================================================
    # Step 2: Idempotency Check (T203)
    # =========================================================================

    async def _check_idempotency(
        self,
        source_url_hash: str,
        force_refresh: bool,
    ) -> Optional[RawExtraction]:
        """
        Check if extraction already exists per T203 idempotency strategy.

        Per design.md §3.1:
        - Key: SHA256(source_url)
        - Skip if RawExtraction exists within 24h (unless force_refresh=true)

        Args:
            source_url_hash: SHA256 hash of source URL
            force_refresh: If True, bypass idempotency check

        Returns:
            Existing RawExtraction if should skip, None otherwise
        """
        if force_refresh:
            logger.debug("Force refresh enabled, skipping idempotency check")
            return None

        # Check for existing extraction
        existing = await self.raw_extraction_repo.get_by_source_url_hash(source_url_hash)

        if not existing:
            return None

        # Check if within idempotency window
        window = timedelta(hours=IDEMPOTENCY_WINDOW_HOURS)
        cutoff = datetime.now(timezone.utc) - window

        if existing.extracted_at > cutoff:
            return existing

        logger.debug(
            f"Existing extraction is older than {IDEMPOTENCY_WINDOW_HOURS}h, "
            "proceeding with new extraction"
        )
        return None

    # =========================================================================
    # Step 3: GitHub Fetch with Retry (T200, T204)
    # =========================================================================

    async def _fetch_with_retry(
        self,
        source_url: str,
        message: PipelineMessage,
    ) -> ComprehensiveRepoExtraction:
        """
        Fetch from GitHub with exponential backoff retry.

        Per design.md §3.1 retry_policy:
        - max_attempts: 3
        - backoff: exponential (2s, 4s, 8s)
        - retryable: NETWORK_TIMEOUT, GITHUB_RATE_LIMIT
        - non-retryable: Invalid URL, 404, 403 (permission)

        Args:
            source_url: GitHub repository URL
            message: Pipeline message for logging

        Returns:
            ComprehensiveRepoExtraction with all data

        Raises:
            NetworkTimeoutError: After max retries for timeout
            RateLimitError: After max retries for rate limit
            RepoNotFoundError: Repository not found (non-retryable)
            GitHubError: Other errors
        """
        last_exception = None

        for attempt in range(ANALYSIS_MAX_ATTEMPTS):
            try:
                # Apply timeout
                return await asyncio.wait_for(
                    self.github_service.fetch_comprehensive_extraction(source_url),
                    timeout=120.0,  # 2 minute timeout per attempt
                )

            except asyncio.TimeoutError as e:
                last_exception = NetworkTimeoutError(f"GitHub fetch timed out: {e}")
                delay = ANALYSIS_BACKOFF_BASE ** (attempt + 1)

                logger.warning(
                    f"GitHub timeout (attempt {attempt + 1}/{ANALYSIS_MAX_ATTEMPTS}). "
                    f"Retrying in {delay}s...",
                    extra={
                        "run_id": str(message.run_id),
                        "source_url": source_url,
                        "attempt": attempt + 1,
                        "delay": delay,
                    }
                )

                if attempt < ANALYSIS_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay)

            except RateLimitError as e:
                last_exception = e
                delay = ANALYSIS_BACKOFF_BASE ** (attempt + 1)

                logger.warning(
                    f"GitHub rate limit (attempt {attempt + 1}/{ANALYSIS_MAX_ATTEMPTS}). "
                    f"Retrying in {delay}s...",
                    extra={
                        "run_id": str(message.run_id),
                        "source_url": source_url,
                        "attempt": attempt + 1,
                        "delay": delay,
                    }
                )

                if attempt < ANALYSIS_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay)

            except (ConnectionError, TimeoutError) as e:
                last_exception = NetworkTimeoutError(str(e))
                delay = ANALYSIS_BACKOFF_BASE ** (attempt + 1)

                logger.warning(
                    f"Network error (attempt {attempt + 1}/{ANALYSIS_MAX_ATTEMPTS}): {e}. "
                    f"Retrying in {delay}s...",
                    extra={
                        "run_id": str(message.run_id),
                        "source_url": source_url,
                        "attempt": attempt + 1,
                    }
                )

                if attempt < ANALYSIS_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay)

            except RepoNotFoundError:
                # Non-retryable: 404
                raise

            except GitHubError as e:
                # Check if permission error (non-retryable)
                if "403" in str(e) and "rate limit" not in str(e).lower():
                    raise  # Permission denied, don't retry

                last_exception = e
                delay = ANALYSIS_BACKOFF_BASE ** (attempt + 1)

                logger.warning(
                    f"GitHub error (attempt {attempt + 1}/{ANALYSIS_MAX_ATTEMPTS}): {e}",
                    extra={
                        "run_id": str(message.run_id),
                        "source_url": source_url,
                        "attempt": attempt + 1,
                    }
                )

                if attempt < ANALYSIS_MAX_ATTEMPTS - 1:
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise last_exception or GitHubError("Unknown error after retries")

    # =========================================================================
    # Step 4: Store RawExtraction
    # =========================================================================

    async def _store_raw_extraction(
        self,
        extraction_data: ComprehensiveRepoExtraction,
        run_id: UUID,
    ) -> RawExtraction:
        """
        Store extraction as immutable RawExtraction document.

        Args:
            extraction_data: Comprehensive extraction from GitHub
            run_id: Pipeline run ID that created this

        Returns:
            Created RawExtraction document
        """
        raw_extraction = RawExtraction(
            id=uuid4(),
            source_url=extraction_data.source_url,
            source_url_hash=extraction_data.source_url_hash,
            readme_content=extraction_data.raw_readme,
            readme_hash=extraction_data.readme_hash,
            repository_metadata=extraction_data.repository_metadata,
            commit_activity=extraction_data.commit_activity,
            releases=extraction_data.releases,
            extracted_urls=extraction_data.extracted_urls,
            extracted_at=extraction_data.extracted_at,
            github_api_version=extraction_data.github_api_version,
            run_id=run_id,
        )

        created = await self.raw_extraction_repo.create(raw_extraction)

        logger.info(
            "Stored raw extraction",
            extra={
                "raw_extraction_id": str(created.id),
                "source_url": extraction_data.source_url,
                "run_id": str(run_id),
            }
        )

        return created

    # =========================================================================
    # Step 5: Update Content Skeleton
    # =========================================================================

    async def _update_content_skeleton(
        self,
        source_url: str,
        raw_extraction_id: UUID,
        message: PipelineMessage,
        extraction_data: ComprehensiveRepoExtraction,
    ) -> Optional[UUID]:
        """
        Create or update Content skeleton with raw_extraction_id reference.

        Per design.md §3.1:
        - Creates Content if not exists
        - Updates existing Content with new raw_extraction_id
        - Sets status to DRAFT

        Args:
            source_url: GitHub repository URL
            raw_extraction_id: ID of the created RawExtraction
            message: Pipeline message for context
            extraction_data: Extracted data for initial content fields

        Returns:
            Content ID (new or existing)
        """
        try:
            # Check if content already exists for this URL
            content_id = message.content_id

            if content_id:
                # Update existing content
                await self.content_service.update_raw_extraction_ref(
                    content_id=str(content_id),
                    raw_extraction_id=raw_extraction_id,
                )
                return content_id

            # Create new content skeleton
            repo_meta = extraction_data.repository_metadata

            from app.models.content import Content

            # Determine owner from message or use system
            contributor_id = str(message.triggered_by) if message.triggered_by else None

            # Extract title from repo name or description
            owner_repo = source_url.split("github.com/")[-1].strip("/")
            title = repo_meta.get("description") or owner_repo.split("/")[-1]

            content = Content(
                id=str(uuid4()),
                title=title[:200] if title else owner_repo,
                source_url=source_url,
                contributor_id=contributor_id,
                status=ContentStatus.DRAFT,
                raw_extraction_id=raw_extraction_id,
                # Set initial metadata from extraction
                language=repo_meta.get("language"),
                categories=repo_meta.get("topics", [])[:5],  # Limit initial categories
            )

            created = await self.content_service.create_skeleton(content)

            logger.info(
                "Created content skeleton",
                extra={
                    "content_id": str(created.id),
                    "source_url": source_url,
                    "raw_extraction_id": str(raw_extraction_id),
                }
            )

            # Return as UUID if needed
            try:
                return UUID(created.id)
            except (ValueError, TypeError):
                return None

        except Exception as e:
            # Content creation failure is not fatal
            logger.warning(
                f"Failed to create/update content skeleton: {e}",
                extra={
                    "source_url": source_url,
                    "raw_extraction_id": str(raw_extraction_id),
                }
            )
            return None

    # =========================================================================
    # Override: is_retryable for Analysis-specific errors
    # =========================================================================

    def is_retryable(self, error: Exception) -> bool:
        """
        Check if error is retryable per design.md §3.1 retry_policy.

        Retryable: NETWORK_TIMEOUT, GITHUB_RATE_LIMIT
        Non-retryable: Invalid URL, 404, 403 (permission)
        """
        if isinstance(error, (NetworkTimeoutError, RateLimitError)):
            return True

        if isinstance(error, (InvalidURLError, RepoNotFoundError)):
            return False

        # Check parent class for general transient errors
        return super().is_retryable(error)
