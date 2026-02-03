"""YouTube analysis pipeline orchestrator for processing YouTube videos."""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from app.core.retry import RetryConfig, RetryError
from app.models.enums import YouTubeAnalysisStatus
from app.models.youtube import (
    YouTubeAnalysisRequest,
    YouTubeAnalysisResult,
    YouTubeContent,
)
from app.services.youtube_service import (
    QuotaExceededError,
    TranscriptNotAvailableError,
    VideoNotFoundError,
    YouTubeError,
    YouTubeService,
)

if TYPE_CHECKING:
    from app.repositories.youtube_repo import YouTubeRepository
    from app.services.llm_service import LLMService
    from app.services.youtube_content_service import YouTubeContentService

logger = logging.getLogger(__name__)


# Retry configurations for YouTube API
YOUTUBE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
    retryable_exceptions=(YouTubeError, ConnectionError, TimeoutError),
)

LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=3.0,
    max_delay=60.0,
    exponential_base=2.0,
    jitter=True,
    retryable_exceptions=(ConnectionError, TimeoutError),
)


class YouTubePipeline:
    """
    Orchestrates the analysis pipeline for YouTube videos.

    Pipeline stages:
    1. PENDING -> FETCHING: Fetch video metadata from YouTube API
    2. FETCHING -> TRANSCRIPT: Fetch video transcript/subtitles
    3. TRANSCRIPT -> PARSING: Extract metadata and summarize using LLM
    4. PARSING -> COMPLETED: Create YouTubeContent and store results

    On failure at any stage: -> FAILED
    """

    # Progress percentages for each stage
    PROGRESS_PENDING = 0
    PROGRESS_FETCHING = 20
    PROGRESS_TRANSCRIPT = 40
    PROGRESS_PARSING = 70
    PROGRESS_COMPLETED = 100

    def __init__(
        self,
        youtube_service: Optional[YouTubeService] = None,
        llm_service: Optional["LLMService"] = None,
        youtube_repo: Optional["YouTubeRepository"] = None,
        youtube_content_service: Optional["YouTubeContentService"] = None,
    ):
        """
        Initialize pipeline with services.

        Args:
            youtube_service: YouTube service for fetching video data
            llm_service: LLM service for metadata extraction and summarization
            youtube_repo: Repository for YouTube analysis requests
            youtube_content_service: Service for creating YouTube content
        """
        self._youtube_service = youtube_service
        self._llm_service = llm_service
        self._youtube_repo = youtube_repo
        self._youtube_content_service = youtube_content_service

    @property
    def youtube_service(self) -> YouTubeService:
        """Get YouTube service instance."""
        if self._youtube_service is None:
            self._youtube_service = get_youtube_service()
        return self._youtube_service

    @property
    def llm_service(self) -> "LLMService":
        """Get LLM service instance."""
        if self._llm_service is None:
            from app.services.llm_service import get_llm_service
            self._llm_service = get_llm_service()
        return self._llm_service

    @property
    def youtube_repo(self) -> "YouTubeRepository":
        """Get YouTube repository instance."""
        if self._youtube_repo is None:
            from app.repositories.youtube_repo import get_youtube_repo
            self._youtube_repo = get_youtube_repo()
        return self._youtube_repo

    @property
    def youtube_content_service(self) -> "YouTubeContentService":
        """Get YouTube content service instance."""
        if self._youtube_content_service is None:
            from app.services.youtube_content_service import get_youtube_content_service
            self._youtube_content_service = get_youtube_content_service()
        return self._youtube_content_service

    async def process_request(self, request: YouTubeAnalysisRequest) -> YouTubeAnalysisRequest:
        """
        Process a YouTube analysis request through all pipeline stages.

        Args:
            request: The YouTube analysis request to process

        Returns:
            Updated analysis request with results or error
        """
        logger.info(f"Starting YouTube pipeline for request {request.id}")

        try:
            # Stage 1: Fetch video metadata from YouTube
            request = await self._stage_fetch(request)
            if request.status == YouTubeAnalysisStatus.FAILED:
                return request

            # Stage 2: Fetch transcript
            request = await self._stage_transcript(request)
            if request.status == YouTubeAnalysisStatus.FAILED:
                return request

            # Stage 3: Parse and enrich with LLM
            request = await self._stage_parse(request)
            if request.status == YouTubeAnalysisStatus.FAILED:
                return request

            # Stage 4: Complete and create content
            request = await self._stage_complete(request)

            logger.info(f"YouTube pipeline completed for request {request.id}")
            return request

        except Exception as e:
            logger.error(f"YouTube pipeline failed for request {request.id}: {e}")
            return await self._handle_failure(request, str(e))

    async def _stage_fetch(self, request: YouTubeAnalysisRequest) -> YouTubeAnalysisRequest:
        """
        Stage 1: Fetch video metadata from YouTube API.

        Updates status to FETCHING, fetches video info.
        """
        logger.info(f"Fetching video data for {request.source_url}")

        # Update status
        request = await self._update_status(
            request,
            YouTubeAnalysisStatus.FETCHING,
            "Fetching video metadata from YouTube",
            self.PROGRESS_FETCHING,
        )

        try:
            video_info = await self._fetch_with_retry(request.source_url)

            # Store fetched data in request (transient, used by next stage)
            request._video_info = video_info
            request.video_id = video_info.video_id

            # Start building result
            result = YouTubeAnalysisResult(
                video_id=video_info.video_id,
                video_url=video_info.video_url,
                channel_id=video_info.channel_id,
                channel_name=video_info.channel_name,
                channel_url=video_info.channel_url,
                title=video_info.title,
                description=video_info.description,
                thumbnail_url=video_info.thumbnail_url,
                view_count=video_info.view_count,
                like_count=video_info.like_count,
                comment_count=video_info.comment_count,
                duration_seconds=video_info.duration_seconds,
                upload_date=video_info.upload_date,
                published_at=video_info.published_at,
                chapters=video_info.chapters,
                tags=video_info.tags,
                raw_metadata=video_info.raw_metadata,
            )
            request._result = result

            return request

        except QuotaExceededError as e:
            return await self._handle_failure(
                request,
                str(e),  # "YouTube API 일일 할당량이 초과되었습니다. 내일 다시 시도해주세요."
            )
        except VideoNotFoundError as e:
            return await self._handle_failure(
                request,
                f"Video not found: {e}",
            )
        except RetryError as e:
            return await self._handle_failure(
                request,
                f"YouTube API error after {YOUTUBE_RETRY_CONFIG.max_attempts} attempts: {e.last_exception}",
            )
        except YouTubeError as e:
            return await self._handle_failure(request, f"YouTube error: {e}")

    async def _fetch_with_retry(self, source_url: str):
        """
        Fetch video info with retry logic.

        Args:
            source_url: YouTube video URL

        Returns:
            VideoInfo with video metadata

        Raises:
            RetryError: After all retry attempts fail
            YouTubeError: For non-retryable errors
        """
        last_exception = None

        for attempt in range(YOUTUBE_RETRY_CONFIG.max_attempts):
            try:
                return await self.youtube_service.fetch_video_info(source_url)
            except QuotaExceededError:
                # Quota exceeded is not retryable
                raise
            except VideoNotFoundError:
                # Video not found is not retryable
                raise
            except (ConnectionError, TimeoutError) as e:
                # Network errors are retryable
                last_exception = e
                if attempt < YOUTUBE_RETRY_CONFIG.max_attempts - 1:
                    delay = YOUTUBE_RETRY_CONFIG.calculate_delay(attempt)
                    logger.warning(
                        f"Network error fetching from YouTube (attempt {attempt + 1}/{YOUTUBE_RETRY_CONFIG.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            except YouTubeError as e:
                # Other YouTube errors might be retryable
                last_exception = e
                if attempt < YOUTUBE_RETRY_CONFIG.max_attempts - 1:
                    delay = YOUTUBE_RETRY_CONFIG.calculate_delay(attempt)
                    logger.warning(
                        f"YouTube error (attempt {attempt + 1}/{YOUTUBE_RETRY_CONFIG.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)

        raise RetryError(
            f"YouTube fetch failed after {YOUTUBE_RETRY_CONFIG.max_attempts} attempts",
            last_exception=last_exception,
        )

    async def _stage_transcript(self, request: YouTubeAnalysisRequest) -> YouTubeAnalysisRequest:
        """
        Stage 2: Fetch video transcript.

        Updates status to TRANSCRIPT, fetches subtitles/captions.
        Note: Transcript not being available is not a fatal error.
        """
        logger.info(f"Fetching transcript for video {request.video_id}")

        # Update status
        request = await self._update_status(
            request,
            YouTubeAnalysisStatus.TRANSCRIPT,
            "Fetching video transcript",
            self.PROGRESS_TRANSCRIPT,
        )

        try:
            # Try to fetch transcript
            transcript = await self.youtube_service.fetch_transcript(
                request.video_id,
                language_priority=["en", "ko"],  # English first as per requirements
            )

            # Store transcript in result
            result = getattr(request, "_result", YouTubeAnalysisResult())
            result.script_original = transcript.full_text
            result.script_language = transcript.language
            request._result = result
            request._transcript = transcript

            logger.info(f"Transcript fetched successfully (language: {transcript.language})")

        except TranscriptNotAvailableError as e:
            # Transcript not available is not fatal - continue without it
            logger.warning(f"Transcript not available for video {request.video_id}: {e}")
            result = getattr(request, "_result", YouTubeAnalysisResult())
            result.script_original = None
            result.script_language = None
            request._result = result
            request._transcript = None

        return request

    async def _stage_parse(self, request: YouTubeAnalysisRequest) -> YouTubeAnalysisRequest:
        """
        Stage 3: Parse and enrich content using LLM.

        Translates title/description, summarizes transcript.
        """
        logger.info(f"Parsing content for request {request.id}")

        # Update status
        request = await self._update_status(
            request,
            YouTubeAnalysisStatus.PARSING,
            "Extracting metadata and summarizing content",
            self.PROGRESS_PARSING,
        )

        try:
            result = getattr(request, "_result", None)
            if not result:
                return await self._handle_failure(
                    request,
                    "Missing video data from fetch stage",
                )

            # Call LLM to process metadata
            enriched_result = await self._parse_with_retry(result)
            request._result = enriched_result
            request.result = enriched_result

            return request

        except RetryError as e:
            return await self._handle_failure(
                request,
                f"LLM error after {LLM_RETRY_CONFIG.max_attempts} attempts: {e.last_exception}",
            )
        except Exception as e:
            return await self._handle_failure(request, f"Parsing error: {e}")

    async def _parse_with_retry(self, result: YouTubeAnalysisResult) -> YouTubeAnalysisResult:
        """
        Parse YouTube content with retry logic.

        Args:
            result: Partial YouTubeAnalysisResult with video metadata

        Returns:
            Enriched YouTubeAnalysisResult

        Raises:
            RetryError: After all retry attempts fail
        """
        from app.services.llm_service import LLMAPIError, LLMConfigError

        last_exception = None

        for attempt in range(LLM_RETRY_CONFIG.max_attempts):
            try:
                return await self.llm_service.process_youtube_metadata(result)
            except LLMAPIError as e:
                last_exception = e
                if attempt < LLM_RETRY_CONFIG.max_attempts - 1:
                    delay = LLM_RETRY_CONFIG.calculate_delay(attempt)
                    logger.warning(
                        f"LLM API error (attempt {attempt + 1}/{LLM_RETRY_CONFIG.max_attempts}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
            except (ConnectionError, TimeoutError) as e:
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

        raise RetryError(
            f"LLM processing failed after {LLM_RETRY_CONFIG.max_attempts} attempts",
            last_exception=last_exception,
        )

    async def _stage_complete(self, request: YouTubeAnalysisRequest) -> YouTubeAnalysisRequest:
        """
        Stage 4: Complete pipeline and create YouTubeContent.

        Creates YouTubeContent entry and updates request status.
        """
        logger.info(f"Completing pipeline for request {request.id}")

        try:
            result = getattr(request, "_result", request.result)
            if not result:
                return await self._handle_failure(
                    request,
                    "Missing analysis result",
                )

            # Create YouTubeContent from result
            content = YouTubeContent.from_analysis_result(
                result=result,
                request_id=request.id,
                contributor_id=request.user_id,
                contributor_email=request.user_email,
            )

            # Save content
            saved_content = await self.youtube_content_service.create_content(content)
            request.content_ids = [saved_content.id]

            # Auto-publish the content
            try:
                await self.youtube_content_service.publish_content(
                    content_id=saved_content.id,
                    contributor_email=request.user_email,
                )
                logger.info(f"Auto-published YouTube content: {saved_content.id}")
            except Exception as pub_error:
                logger.warning(f"Failed to auto-publish content {saved_content.id}: {pub_error}")
                # Continue even if publish fails - content is still created as draft

            # Update request status to completed
            request.result = result
            request = await self._update_status(
                request,
                YouTubeAnalysisStatus.COMPLETED,
                "Analysis completed successfully",
                self.PROGRESS_COMPLETED,
            )

            return request

        except Exception as e:
            return await self._handle_failure(
                request,
                f"Failed to create content: {e}",
            )

    async def _update_status(
        self,
        request: YouTubeAnalysisRequest,
        status: YouTubeAnalysisStatus,
        message: str,
        progress: int,
    ) -> YouTubeAnalysisRequest:
        """Update request status and persist to database."""
        request.update_status(status, message, progress)

        try:
            await self.youtube_repo.update(request)
        except Exception as e:
            logger.error(f"Failed to update request status: {e}")

        return request

    async def _handle_failure(
        self,
        request: YouTubeAnalysisRequest,
        error_message: str,
    ) -> YouTubeAnalysisRequest:
        """Handle pipeline failure."""
        logger.error(f"Pipeline failed for request {request.id}: {error_message}")

        request.set_error(error_message)

        try:
            await self.youtube_repo.update(request)
        except Exception as e:
            logger.error(f"Failed to save error status: {e}")

        return request


# =============================================================================
# Service singleton
# =============================================================================

_youtube_service: Optional[YouTubeService] = None
_youtube_pipeline: Optional[YouTubePipeline] = None


def get_youtube_service() -> YouTubeService:
    """Get or create YouTube service singleton."""
    global _youtube_service
    if _youtube_service is None:
        _youtube_service = YouTubeService()
    return _youtube_service


def get_youtube_pipeline() -> YouTubePipeline:
    """Get or create YouTube pipeline singleton."""
    global _youtube_pipeline
    if _youtube_pipeline is None:
        _youtube_pipeline = YouTubePipeline()
    return _youtube_pipeline
