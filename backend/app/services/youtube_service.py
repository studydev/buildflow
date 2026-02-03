"""YouTube service for fetching video data and transcripts."""

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import httpx

from app.config import get_settings
from app.models.youtube import YouTubeChapter

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# Exceptions
# =============================================================================


class YouTubeError(Exception):
    """Base exception for YouTube service errors."""
    pass


class VideoNotFoundError(YouTubeError):
    """Video not found."""
    pass


class QuotaExceededError(YouTubeError):
    """YouTube API quota exceeded - retry next day."""
    pass


class TranscriptNotAvailableError(YouTubeError):
    """Transcript/subtitles not available for this video."""
    pass


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class VideoInfo:
    """Information extracted from a YouTube video."""

    video_id: str
    video_url: str

    # Channel info
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None

    # Basic metadata
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None

    # Statistics
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0

    # Duration and dates
    duration_seconds: int = 0
    published_at: Optional[str] = None
    upload_date: Optional[str] = None

    # Tags and chapters
    tags: List[str] = field(default_factory=list)
    chapters: List[YouTubeChapter] = field(default_factory=list)

    # Raw API response for reference
    raw_metadata: dict = field(default_factory=dict)


@dataclass
class TranscriptEntry:
    """Single transcript entry."""

    text: str
    start: float  # seconds
    duration: float  # seconds


@dataclass
class TranscriptResult:
    """Result of transcript fetch."""

    entries: List[TranscriptEntry]
    language: str  # Language code (en, ko, etc.)
    is_generated: bool = False  # Whether auto-generated

    @property
    def full_text(self) -> str:
        """Get full transcript text without timestamps."""
        return " ".join(entry.text for entry in self.entries)


# =============================================================================
# Transcript Provider Interface (for external API abstraction)
# =============================================================================


class TranscriptProvider(ABC):
    """Abstract interface for transcript providers."""

    @abstractmethod
    async def get_transcript(
        self,
        video_id: str,
        language_priority: Optional[List[str]] = None,
    ) -> TranscriptResult:
        """
        Get transcript for a video.

        Args:
            video_id: YouTube video ID
            language_priority: Priority order of languages to try (default: ["en", "ko"])

        Returns:
            TranscriptResult with entries and language info

        Raises:
            TranscriptNotAvailableError: If no transcript is available
        """
        pass


class LocalTranscriptProvider(TranscriptProvider):
    """
    Local transcript provider using youtube-transcript-api library.

    Note: This may not work in Azure deployment due to IP restrictions.
    Use ExternalTranscriptProvider as fallback.
    """

    async def get_transcript(
        self,
        video_id: str,
        language_priority: Optional[List[str]] = None,
    ) -> TranscriptResult:
        """Get transcript using youtube-transcript-api library (v1.2+ API)."""
        if language_priority is None:
            language_priority = ["en", "ko"]  # English first as per requirements

        try:
            # Import here to avoid import errors if library not installed
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import (
                NoTranscriptFound,
                TranscriptsDisabled,
                VideoUnavailable,
            )

            try:
                # Create API instance (new in v1.2+)
                api = YouTubeTranscriptApi()

                # List available transcripts
                transcript_list = api.list(video_id)

                # Try manual transcripts first, then generated
                transcript = None
                language_used = None
                is_generated = False

                # First pass: try manual transcripts
                for lang in language_priority:
                    try:
                        transcript = transcript_list.find_manually_created_transcript([lang])
                        language_used = lang
                        is_generated = False
                        break
                    except NoTranscriptFound:
                        continue

                # Second pass: try generated transcripts
                if transcript is None:
                    for lang in language_priority:
                        try:
                            transcript = transcript_list.find_generated_transcript([lang])
                            language_used = lang
                            is_generated = True
                            break
                        except NoTranscriptFound:
                            continue

                # If still no transcript, try any available
                if transcript is None:
                    try:
                        # Get first available transcript
                        for t in transcript_list:
                            transcript = t
                            language_used = t.language_code
                            is_generated = t.is_generated
                            break
                    except Exception:
                        pass

                if transcript is None:
                    raise TranscriptNotAvailableError(
                        f"No transcript available for video {video_id}"
                    )

                # Fetch the transcript
                raw_transcript = transcript.fetch()

                # New API returns FetchedTranscriptSnippet objects with attributes
                entries = [
                    TranscriptEntry(
                        text=item.text,
                        start=item.start,
                        duration=item.duration,
                    )
                    for item in raw_transcript
                ]

                return TranscriptResult(
                    entries=entries,
                    language=language_used or "unknown",
                    is_generated=is_generated,
                )

            except (TranscriptsDisabled, VideoUnavailable) as e:
                raise TranscriptNotAvailableError(str(e))
            except NoTranscriptFound:
                raise TranscriptNotAvailableError(
                    f"No transcript found for video {video_id}"
                )

        except ImportError:
            logger.error("youtube-transcript-api not installed")
            raise TranscriptNotAvailableError(
                "Transcript library not available. Please install youtube-transcript-api."
            )
        except Exception as e:
            logger.error(f"Error fetching transcript: {e}")
            raise TranscriptNotAvailableError(str(e))


class ExternalTranscriptProvider(TranscriptProvider):
    """
    External transcript provider using a separate API service.

    Use this when youtube-transcript-api doesn't work in cloud deployment.
    """

    def __init__(self, api_url: str, api_key: Optional[str] = None):
        """
        Initialize external provider.

        Args:
            api_url: Base URL of the external transcript API
            api_key: Optional API key for authentication
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    async def get_transcript(
        self,
        video_id: str,
        language_priority: Optional[List[str]] = None,
    ) -> TranscriptResult:
        """Get transcript from external API."""
        if language_priority is None:
            language_priority = ["en", "ko"]

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.api_url}/transcript",
                    json={
                        "video_id": video_id,
                        "language_priority": language_priority,
                    },
                    headers=headers,
                )

                if response.status_code == 404:
                    raise TranscriptNotAvailableError(
                        f"No transcript available for video {video_id}"
                    )

                response.raise_for_status()
                data = response.json()

                entries = [
                    TranscriptEntry(
                        text=item["text"],
                        start=item["start"],
                        duration=item["duration"],
                    )
                    for item in data.get("entries", [])
                ]

                return TranscriptResult(
                    entries=entries,
                    language=data.get("language", "unknown"),
                    is_generated=data.get("is_generated", False),
                )

            except httpx.HTTPStatusError as e:
                logger.error(f"External transcript API error: {e}")
                raise TranscriptNotAvailableError(str(e))


# =============================================================================
# YouTube Service
# =============================================================================


class YouTubeService:
    """Service for interacting with YouTube Data API v3."""

    API_BASE_URL = "https://www.googleapis.com/youtube/v3"

    # Regex patterns for extracting video ID
    VIDEO_ID_PATTERNS = [
        r"(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?]|$)",  # Standard and short URLs
        r"^([a-zA-Z0-9_-]{11})$",  # Just the ID
        r"youtu\.be/([a-zA-Z0-9_-]{11})",  # youtu.be URLs
        r"embed/([a-zA-Z0-9_-]{11})",  # Embed URLs
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        transcript_provider: Optional[TranscriptProvider] = None,
    ):
        """
        Initialize YouTube service.

        Args:
            api_key: YouTube Data API key
            transcript_provider: Provider for fetching transcripts
        """
        self.api_key = api_key or getattr(settings, "youtube_api_key", None)
        self._client: Optional[httpx.AsyncClient] = None

        # Set up transcript provider
        external_api_url = os.getenv("YOUTUBE_TRANSCRIPT_API_URL")
        if external_api_url:
            logger.info(f"Using external transcript API: {external_api_url}")
            self.transcript_provider = ExternalTranscriptProvider(
                api_url=external_api_url,
                api_key=os.getenv("YOUTUBE_TRANSCRIPT_API_KEY"),
            )
        elif transcript_provider:
            self.transcript_provider = transcript_provider
        else:
            self.transcript_provider = LocalTranscriptProvider()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from YouTube URL.

        Args:
            url: YouTube video URL or video ID

        Returns:
            Video ID or None if not found
        """
        for pattern in self.VIDEO_ID_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _api_request(
        self,
        endpoint: str,
        params: dict,
    ) -> dict:
        """
        Make YouTube API request.

        Args:
            endpoint: API endpoint (e.g., "videos")
            params: Query parameters

        Returns:
            API response as dict

        Raises:
            QuotaExceededError: If API quota is exceeded
            VideoNotFoundError: If video not found
            YouTubeError: For other API errors
        """
        if not self.api_key:
            raise YouTubeError("YouTube API key not configured")

        client = await self._get_client()
        params["key"] = self.api_key

        try:
            response = await client.get(
                f"{self.API_BASE_URL}/{endpoint}",
                params=params,
            )

            # Handle quota exceeded
            if response.status_code == 403:
                error_data = response.json()
                if "quotaExceeded" in str(error_data):
                    raise QuotaExceededError(
                        "YouTube API 일일 할당량이 초과되었습니다. 내일 다시 시도해주세요."
                    )
                raise YouTubeError(f"API forbidden: {error_data}")

            # Handle not found
            if response.status_code == 404:
                raise VideoNotFoundError("Video not found")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"YouTube API error: {e}")
            raise YouTubeError(str(e))

    def _parse_duration(self, duration_iso: str) -> int:
        """
        Parse ISO 8601 duration to seconds.

        Args:
            duration_iso: Duration string like "PT1H2M3S"

        Returns:
            Duration in seconds
        """
        if not duration_iso:
            return 0

        # Remove PT prefix
        duration = duration_iso.replace("PT", "")

        hours = 0
        minutes = 0
        seconds = 0

        # Extract hours
        if "H" in duration:
            parts = duration.split("H")
            hours = int(parts[0])
            duration = parts[1] if len(parts) > 1 else ""

        # Extract minutes
        if "M" in duration:
            parts = duration.split("M")
            minutes = int(parts[0])
            duration = parts[1] if len(parts) > 1 else ""

        # Extract seconds
        if "S" in duration:
            seconds = int(duration.replace("S", ""))

        return hours * 3600 + minutes * 60 + seconds

    def _parse_chapters_from_description(
        self,
        description: str,
        duration_seconds: int,
    ) -> List[YouTubeChapter]:
        """
        Parse chapters from video description.

        Chapters are typically in format:
        0:00 Introduction
        1:30 Chapter 1
        etc.

        Args:
            description: Video description
            duration_seconds: Total video duration

        Returns:
            List of chapters
        """
        if not description:
            return []

        chapters = []
        # Pattern: timestamp followed by title
        # Matches: 0:00, 00:00, 1:00:00, etc.
        pattern = r"(?:^|\n)\s*(\d{1,2}:)?(\d{1,2}):(\d{2})\s+(.+?)(?:\n|$)"

        for match in re.finditer(pattern, description, re.MULTILINE):
            hours = int(match.group(1).rstrip(":")) if match.group(1) else 0
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            title = match.group(4).strip()

            start_time = hours * 3600 + minutes * 60 + seconds

            # Skip if start time is beyond video duration
            if start_time >= duration_seconds:
                continue

            chapters.append(
                YouTubeChapter(
                    title=title,
                    start_time=start_time,
                )
            )

        # Calculate end times
        for i, chapter in enumerate(chapters):
            if i < len(chapters) - 1:
                chapter.end_time = chapters[i + 1].start_time
            else:
                chapter.end_time = duration_seconds

        return chapters

    def _get_best_thumbnail(self, thumbnails: dict) -> Optional[str]:
        """Get the best available thumbnail URL."""
        # Priority: maxres > standard > high > medium > default
        for quality in ["maxres", "standard", "high", "medium", "default"]:
            if quality in thumbnails:
                return thumbnails[quality].get("url")
        return None

    async def fetch_video_info(self, url: str) -> VideoInfo:
        """
        Fetch video information from YouTube API.

        Args:
            url: YouTube video URL

        Returns:
            VideoInfo with video metadata

        Raises:
            VideoNotFoundError: If video not found
            QuotaExceededError: If API quota exceeded
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            raise VideoNotFoundError(f"Invalid YouTube URL: {url}")

        # Fetch video details
        response = await self._api_request(
            "videos",
            {
                "part": "snippet,contentDetails,statistics",
                "id": video_id,
            },
        )

        items = response.get("items", [])
        if not items:
            raise VideoNotFoundError(f"Video not found: {video_id}")

        video_data = items[0]
        snippet = video_data.get("snippet", {})
        content_details = video_data.get("contentDetails", {})
        statistics = video_data.get("statistics", {})

        # Parse duration
        duration_seconds = self._parse_duration(
            content_details.get("duration", "")
        )

        # Parse chapters from description
        description = snippet.get("description", "")
        chapters = self._parse_chapters_from_description(
            description, duration_seconds
        )

        # Get best thumbnail
        thumbnail_url = self._get_best_thumbnail(
            snippet.get("thumbnails", {})
        )

        # Parse published date
        published_at = snippet.get("publishedAt")
        upload_date = None
        if published_at:
            try:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                upload_date = dt.strftime("%Y-%m-%d")
            except (ValueError, AttributeError):
                pass

        return VideoInfo(
            video_id=video_id,
            video_url=f"https://www.youtube.com/watch?v={video_id}",
            channel_id=snippet.get("channelId"),
            channel_name=snippet.get("channelTitle"),
            channel_url=f"https://www.youtube.com/channel/{snippet.get('channelId')}" if snippet.get("channelId") else None,
            title=snippet.get("title"),
            description=description,
            thumbnail_url=thumbnail_url,
            view_count=int(statistics.get("viewCount", 0)),
            like_count=int(statistics.get("likeCount", 0)),
            comment_count=int(statistics.get("commentCount", 0)),
            duration_seconds=duration_seconds,
            published_at=published_at,
            upload_date=upload_date,
            tags=snippet.get("tags", []),
            chapters=chapters,
            raw_metadata=video_data,
        )

    async def fetch_transcript(
        self,
        video_id: str,
        language_priority: Optional[List[str]] = None,
    ) -> TranscriptResult:
        """
        Fetch transcript for a video.

        Args:
            video_id: YouTube video ID
            language_priority: Priority order of languages (default: ["en", "ko"])

        Returns:
            TranscriptResult with transcript entries

        Raises:
            TranscriptNotAvailableError: If no transcript available
        """
        if language_priority is None:
            language_priority = ["en", "ko"]  # English first as per requirements

        return await self.transcript_provider.get_transcript(
            video_id=video_id,
            language_priority=language_priority,
        )

    async def fetch_video_with_transcript(
        self,
        url: str,
        language_priority: Optional[List[str]] = None,
    ) -> tuple:
        """
        Fetch video info and transcript together.

        Args:
            url: YouTube video URL
            language_priority: Priority order for transcript languages

        Returns:
            Tuple of (VideoInfo, TranscriptResult or None)
        """
        video_info = await self.fetch_video_info(url)

        transcript = None
        try:
            transcript = await self.fetch_transcript(
                video_info.video_id,
                language_priority=language_priority,
            )
        except TranscriptNotAvailableError as e:
            logger.warning(f"Transcript not available for {video_info.video_id}: {e}")

        return video_info, transcript

    def validate_youtube_url(self, url: str) -> tuple:
        """
        Validate YouTube URL.

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url:
            return False, "URL is required"

        # Check if it's a YouTube URL
        youtube_patterns = [
            r"youtube\.com",
            r"youtu\.be",
        ]

        is_youtube = any(re.search(p, url) for p in youtube_patterns)
        if not is_youtube:
            return False, "Not a valid YouTube URL"

        # Try to extract video ID
        video_id = self.extract_video_id(url)
        if not video_id:
            return False, "Could not extract video ID from URL"

        return True, None
