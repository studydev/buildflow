"""YouTube analysis models for video content collection."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.enums import ContentStatus, ContentType, YouTubeAnalysisStatus


@dataclass
class YouTubeStatusHistoryEntry:
    """Entry in the YouTube analysis status history."""

    status: YouTubeAnalysisStatus
    timestamp: datetime
    message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YouTubeStatusHistoryEntry":
        """Create from dictionary."""
        return cls(
            status=YouTubeAnalysisStatus(data["status"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message=data.get("message"),
        )


@dataclass
class YouTubeChapter:
    """YouTube video chapter information."""

    title: str
    start_time: int  # seconds
    end_time: Optional[int] = None  # seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YouTubeChapter":
        """Create from dictionary."""
        return cls(
            title=data["title"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
        )


@dataclass
class YouTubeAnalysisResult:
    """Result of YouTube video analysis."""

    # Video identifiers
    video_id: str = ""
    video_url: str = ""

    # Channel information
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None

    # Titles (bilingual)
    title: Optional[str] = None  # Original title
    title_en: Optional[str] = None  # English version
    title_kr: Optional[str] = None  # Korean version

    # Descriptions (bilingual)
    description: Optional[str] = None  # Original description
    description_en: Optional[str] = None  # English version
    description_kr: Optional[str] = None  # Korean version

    # Video metadata
    thumbnail_url: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    duration_seconds: int = 0  # Video duration in seconds
    upload_date: Optional[str] = None  # ISO format date string
    published_at: Optional[str] = None

    # Chapters
    chapters: list[YouTubeChapter] = field(default_factory=list)

    # Transcript/Script
    script_original: Optional[str] = None  # Full original transcript in English (no timestamps)
    script_original_kr: Optional[str] = None  # Full original transcript in Korean (translated if original is English)
    script_language: Optional[str] = None  # Language of the original script (en, ko, etc.)
    script_summary_en: Optional[str] = None  # English summary (max 1000 chars)
    script_summary_kr: Optional[str] = None  # Korean summary (max 1000 chars)

    # Classification
    content_type: Optional[str] = None  # tutorial, workshop, talk, demo, etc.
    categories: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    level: Optional[str] = None  # beginner, intermediate, advanced

    # Tags from YouTube
    tags: list[str] = field(default_factory=list)

    # Raw metadata for reference
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "video_id": self.video_id,
            "video_url": self.video_url,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "channel_url": self.channel_url,
            "title": self.title,
            "title_en": self.title_en,
            "title_kr": self.title_kr,
            "description": self.description,
            "description_en": self.description_en,
            "description_kr": self.description_kr,
            "thumbnail_url": self.thumbnail_url,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "duration_seconds": self.duration_seconds,
            "upload_date": self.upload_date,
            "published_at": self.published_at,
            "chapters": [ch.to_dict() for ch in self.chapters],
            "script_original": self.script_original,
            "script_original_kr": self.script_original_kr,
            "script_language": self.script_language,
            "script_summary_en": self.script_summary_en,
            "script_summary_kr": self.script_summary_kr,
            "content_type": self.content_type,
            "categories": self.categories,
            "technologies": self.technologies,
            "level": self.level,
            "tags": self.tags,
            "raw_metadata": self.raw_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YouTubeAnalysisResult":
        """Create from dictionary."""
        chapters = [
            YouTubeChapter.from_dict(ch) for ch in data.get("chapters", [])
        ]
        return cls(
            video_id=data.get("video_id", ""),
            video_url=data.get("video_url", ""),
            channel_id=data.get("channel_id"),
            channel_name=data.get("channel_name"),
            channel_url=data.get("channel_url"),
            title=data.get("title"),
            title_en=data.get("title_en"),
            title_kr=data.get("title_kr"),
            description=data.get("description"),
            description_en=data.get("description_en"),
            description_kr=data.get("description_kr"),
            thumbnail_url=data.get("thumbnail_url"),
            view_count=data.get("view_count", 0),
            like_count=data.get("like_count", 0),
            comment_count=data.get("comment_count", 0),
            duration_seconds=data.get("duration_seconds", 0),
            upload_date=data.get("upload_date"),
            published_at=data.get("published_at"),
            chapters=chapters,
            script_original=data.get("script_original"),
            script_original_kr=data.get("script_original_kr"),
            script_language=data.get("script_language"),
            script_summary_en=data.get("script_summary_en"),
            script_summary_kr=data.get("script_summary_kr"),
            content_type=data.get("content_type"),
            categories=data.get("categories", []),
            technologies=data.get("technologies", []),
            level=data.get("level"),
            tags=data.get("tags", []),
            raw_metadata=data.get("raw_metadata", {}),
        )


@dataclass
class YouTubeAnalysisRequest:
    """
    Model for YouTube video analysis requests.

    Partition key: user_id (for user-centric queries)
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""  # Partition key
    user_email: Optional[str] = None
    source_url: str = ""  # YouTube video URL
    video_id: str = ""  # Extracted video ID
    status: YouTubeAnalysisStatus = YouTubeAnalysisStatus.PENDING
    status_history: list[YouTubeStatusHistoryEntry] = field(default_factory=list)
    result: Optional[YouTubeAnalysisResult] = None
    content_ids: list[str] = field(default_factory=list)  # Created YouTubeContent IDs
    error_message: Optional[str] = None
    progress: int = 0  # 0-100 percentage
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        """Add initial status to history if empty."""
        if not self.status_history:
            self.status_history.append(
                YouTubeStatusHistoryEntry(
                    status=self.status,
                    timestamp=self.created_at,
                    message="Request created",
                )
            )

    def update_status(
        self,
        new_status: YouTubeAnalysisStatus,
        message: Optional[str] = None,
        progress: Optional[int] = None,
    ) -> None:
        """Update the request status."""
        self.status = new_status
        self.updated_at = datetime.utcnow()

        if progress is not None:
            self.progress = progress

        self.status_history.append(
            YouTubeStatusHistoryEntry(
                status=new_status,
                timestamp=self.updated_at,
                message=message,
            )
        )

        if new_status in (YouTubeAnalysisStatus.COMPLETED, YouTubeAnalysisStatus.FAILED):
            self.completed_at = self.updated_at
            if new_status == YouTubeAnalysisStatus.COMPLETED:
                self.progress = 100

    def set_result(self, result: YouTubeAnalysisResult) -> None:
        """Set the analysis result and mark as completed."""
        self.result = result
        self.update_status(
            YouTubeAnalysisStatus.COMPLETED,
            message="Analysis completed successfully",
            progress=100,
        )

    def set_error(self, error_message: str) -> None:
        """Set error and mark as failed."""
        self.error_message = error_message
        self.update_status(
            YouTubeAnalysisStatus.FAILED,
            message=error_message,
        )

    def to_cosmos_item(self) -> dict[str, Any]:
        """Convert to Cosmos DB item."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "source_url": self.source_url,
            "video_id": self.video_id,
            "status": self.status.value,
            "status_history": [entry.to_dict() for entry in self.status_history],
            "result": self.result.to_dict() if self.result else None,
            "content_ids": self.content_ids,
            "error_message": self.error_message,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            # Cosmos metadata
            "type": "youtube_analysis_request",
            "partition_key": self.user_id,
        }

    @classmethod
    def from_cosmos_item(cls, item: dict[str, Any]) -> "YouTubeAnalysisRequest":
        """Create from Cosmos DB item."""
        status_history = [
            YouTubeStatusHistoryEntry.from_dict(entry)
            for entry in item.get("status_history", [])
        ]

        result = None
        if item.get("result"):
            result = YouTubeAnalysisResult.from_dict(item["result"])

        return cls(
            id=item["id"],
            user_id=item["user_id"],
            user_email=item.get("user_email"),
            source_url=item["source_url"],
            video_id=item.get("video_id", ""),
            status=YouTubeAnalysisStatus(item["status"]),
            status_history=status_history,
            result=result,
            content_ids=item.get("content_ids", []),
            error_message=item.get("error_message"),
            progress=item.get("progress", 0),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            completed_at=datetime.fromisoformat(item["completed_at"]) if item.get("completed_at") else None,
        )


@dataclass
class YouTubeAnalysisRequestPublic:
    """Public representation of a YouTube analysis request (for API responses)."""

    id: str
    source_url: str
    video_id: str
    status: str
    progress: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    result: Optional[dict[str, Any]]
    content_ids: list[str]
    error_message: Optional[str]

    @classmethod
    def from_request(cls, request: YouTubeAnalysisRequest) -> "YouTubeAnalysisRequestPublic":
        """Create from YouTubeAnalysisRequest."""
        return cls(
            id=request.id,
            source_url=request.source_url,
            video_id=request.video_id,
            status=request.status.value,
            progress=request.progress,
            created_at=request.created_at,
            updated_at=request.updated_at,
            completed_at=request.completed_at,
            result=request.result.to_dict() if request.result else None,
            content_ids=request.content_ids,
            error_message=request.error_message,
        )


class YouTubeContent(BaseModel):
    """
    YouTubeContent model representing a YouTube video learning resource.

    Partition Key: contributor_id (for efficient contributor-based queries)
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    contributor_id: Optional[str] = None

    # Analysis request reference
    analysis_request_id: Optional[str] = None

    # Video identifiers
    video_id: str = ""
    source_url: str = ""
    source_type: str = "youtube"

    # Channel information
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    channel_url: Optional[str] = None

    # Titles (bilingual)
    title: str = ""
    title_en: Optional[str] = None
    title_kr: Optional[str] = None

    # Descriptions (bilingual)
    description: str = ""
    description_en: Optional[str] = None
    description_kr: Optional[str] = None

    # Video metadata
    thumbnail_url: Optional[str] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    duration_seconds: int = 0
    duration_minutes: int = 0  # Computed from duration_seconds for compatibility
    upload_date: Optional[datetime] = None

    # Chapters
    chapters: list[dict[str, Any]] = Field(default_factory=list)

    # Transcript/Script (summary only, full script is in analysis_request)
    script_language: Optional[str] = None
    script_summary_en: Optional[str] = None
    script_summary_kr: Optional[str] = None

    # Classification
    content_type: ContentType = ContentType.TUTORIAL
    status: ContentStatus = ContentStatus.DRAFT
    categories: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    level: str = "beginner"
    tags: list[str] = Field(default_factory=list)

    # Contributor tracking
    contributor_create_email: Optional[str] = None
    contributor_update_email: Optional[str] = None

    # Stats
    bookmark_count: int = 0

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

    def to_cosmos_item(self) -> dict[str, Any]:
        """Convert to Cosmos DB document format."""
        return {
            "id": self.id,
            "contributor_id": self.contributor_id,
            "analysis_request_id": self.analysis_request_id,
            "video_id": self.video_id,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "channel_url": self.channel_url,
            "title": self.title,
            "title_en": self.title_en,
            "title_kr": self.title_kr,
            "description": self.description,
            "description_en": self.description_en,
            "description_kr": self.description_kr,
            "thumbnail_url": self.thumbnail_url,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "duration_seconds": self.duration_seconds,
            "duration_minutes": self.duration_minutes,
            "upload_date": self.upload_date.isoformat() if self.upload_date else None,
            "chapters": self.chapters,
            "script_language": self.script_language,
            "script_summary_en": self.script_summary_en,
            "script_summary_kr": self.script_summary_kr,
            "content_type": self.content_type.value,
            "status": self.status.value,
            "categories": self.categories,
            "technologies": self.technologies,
            "level": self.level,
            "tags": self.tags,
            "contributor_create_email": self.contributor_create_email,
            "contributor_update_email": self.contributor_update_email,
            "bookmark_count": self.bookmark_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            # Cosmos metadata
            "type": "youtube_content",
            "partition_key": self.contributor_id,
        }

    @classmethod
    def from_cosmos_item(cls, item: dict[str, Any]) -> "YouTubeContent":
        """Create YouTubeContent from Cosmos DB document."""
        return cls(
            id=item["id"],
            contributor_id=item.get("contributor_id"),
            analysis_request_id=item.get("analysis_request_id"),
            video_id=item.get("video_id", ""),
            source_url=item.get("source_url", ""),
            source_type=item.get("source_type", "youtube"),
            channel_id=item.get("channel_id"),
            channel_name=item.get("channel_name"),
            channel_url=item.get("channel_url"),
            title=item.get("title", ""),
            title_en=item.get("title_en"),
            title_kr=item.get("title_kr"),
            description=item.get("description", ""),
            description_en=item.get("description_en"),
            description_kr=item.get("description_kr"),
            thumbnail_url=item.get("thumbnail_url"),
            view_count=item.get("view_count", 0),
            like_count=item.get("like_count", 0),
            comment_count=item.get("comment_count", 0),
            duration_seconds=item.get("duration_seconds", 0),
            duration_minutes=item.get("duration_minutes", 0),
            upload_date=datetime.fromisoformat(item["upload_date"]) if item.get("upload_date") else None,
            chapters=item.get("chapters", []),
            script_language=item.get("script_language"),
            script_summary_en=item.get("script_summary_en"),
            script_summary_kr=item.get("script_summary_kr"),
            content_type=ContentType(item.get("content_type", "tutorial")),
            status=ContentStatus(item.get("status", "draft")),
            categories=item.get("categories", []),
            technologies=item.get("technologies", []),
            level=item.get("level", "beginner"),
            tags=item.get("tags", []),
            contributor_create_email=item.get("contributor_create_email"),
            contributor_update_email=item.get("contributor_update_email"),
            bookmark_count=item.get("bookmark_count", 0),
            created_at=datetime.fromisoformat(item["created_at"]) if item.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else datetime.utcnow(),
            published_at=datetime.fromisoformat(item["published_at"]) if item.get("published_at") else None,
        )

    @classmethod
    def from_analysis_result(
        cls,
        result: YouTubeAnalysisResult,
        request_id: str,
        contributor_id: Optional[str] = None,
        contributor_email: Optional[str] = None,
    ) -> "YouTubeContent":
        """Create YouTubeContent from analysis result."""
        # Use English title as primary, fallback to original
        title = result.title_en or result.title or "Untitled Video"

        # Convert duration to minutes
        duration_minutes = result.duration_seconds // 60 if result.duration_seconds else 0

        # Parse upload date
        upload_date = None
        if result.upload_date:
            try:
                upload_date = datetime.fromisoformat(result.upload_date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return cls(
            contributor_id=contributor_id,
            analysis_request_id=request_id,
            video_id=result.video_id,
            source_url=result.video_url,
            channel_id=result.channel_id,
            channel_name=result.channel_name,
            channel_url=result.channel_url,
            title=title,
            title_en=result.title_en,
            title_kr=result.title_kr,
            description=result.description_en or result.description or "",
            description_en=result.description_en,
            description_kr=result.description_kr,
            thumbnail_url=result.thumbnail_url,
            view_count=result.view_count,
            like_count=result.like_count,
            comment_count=result.comment_count,
            duration_seconds=result.duration_seconds,
            duration_minutes=duration_minutes,
            upload_date=upload_date,
            chapters=[ch.to_dict() for ch in result.chapters],
            script_language=result.script_language,
            script_summary_en=result.script_summary_en,
            script_summary_kr=result.script_summary_kr,
            content_type=ContentType(result.content_type) if result.content_type else ContentType.TUTORIAL,
            categories=result.categories,
            technologies=result.technologies,
            level=result.level or "beginner",
            tags=result.tags,
            contributor_create_email=contributor_email,
            status=ContentStatus.DRAFT,
        )
