"""Content model for learning resources."""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.enums import ContentStatus, ContentType


class Content(BaseModel):
    """
    Content model representing a learning resource.

    Partition Key: contributor_id (for efficient contributor-based queries)
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    contributor_id: Optional[str] = None  # Made optional for pipeline creation

    # Analysis request reference (for bidirectional linking)
    analysis_request_id: Optional[str] = None  # Reference to the analysis request that created this content

    # Basic info
    title: str
    description: str = ""
    content_type: ContentType = ContentType.WORKSHOP
    status: ContentStatus = ContentStatus.DRAFT

    # Source information
    source_url: str  # GitHub repo URL
    source_type: str = "github"  # github, azuredevops, etc.

    # Categories and tags
    categories: list[str] = Field(default_factory=list)
    level: str = "beginner"  # beginner, intermediate, advanced
    duration_minutes: int = 60

    # Metadata
    thumbnail_url: Optional[str] = None
    icon: Optional[str] = None
    language: Optional[str] = None  # Primary programming language

    # Analysis results
    analysis_status: str = "pending"  # pending, processing, completed, failed

    # Learning content fields
    learning_outcomes: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

    # Repository signals
    stars: Optional[int] = None
    forks: Optional[int] = None
    last_commit_date: Optional[datetime] = None
    contributors: list[str] = Field(default_factory=list)  # GitHub contributor IDs (top 5)

    # Contributor tracking (who collected/updated this content)
    contributor_create_email: Optional[str] = None  # Email of user who created this content
    contributor_update_email: Optional[str] = None  # Email of user who last updated this content

    # Localization fields
    title_kr: Optional[str] = None
    description_kr: Optional[str] = None

    # Resource links (for card display)
    video_url: Optional[str] = None
    docs_url: Optional[str] = None
    pptx_url: Optional[str] = None

    # Stats
    view_count: int = 0
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
            "title": self.title,
            "description": self.description,
            "content_type": self.content_type.value,
            "status": self.status.value,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "categories": self.categories,
            "level": self.level,
            "duration_minutes": self.duration_minutes,
            "thumbnail_url": self.thumbnail_url,
            "icon": self.icon,
            "language": self.language,
            "analysis_status": self.analysis_status,
            # Learning content fields
            "learning_outcomes": self.learning_outcomes,
            "prerequisites": self.prerequisites,
            "technologies": self.technologies,
            # Repository signals
            "stars": self.stars,
            "forks": self.forks,
            "last_commit_date": self.last_commit_date.isoformat() if self.last_commit_date else None,
            "contributors": self.contributors,
            # Contributor tracking
            "contributor_create_email": self.contributor_create_email,
            "contributor_update_email": self.contributor_update_email,
            # Localization fields
            "title_kr": self.title_kr,
            "description_kr": self.description_kr,
            # Resource links
            "video_url": self.video_url,
            "docs_url": self.docs_url,
            "pptx_url": self.pptx_url,
            # Stats
            "view_count": self.view_count,
            "bookmark_count": self.bookmark_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }

    @classmethod
    def from_cosmos_item(cls, item: dict[str, Any]) -> "Content":
        """Create Content from Cosmos DB document."""
        return cls(
            id=item["id"],
            contributor_id=item.get("contributor_id"),
            analysis_request_id=item.get("analysis_request_id"),
            title=item["title"],
            description=item.get("description", ""),
            content_type=ContentType(item["content_type"]),
            status=ContentStatus(item["status"]),
            source_url=item["source_url"],
            source_type=item.get("source_type", "github"),
            categories=item.get("categories", []),
            level=item.get("level", "beginner"),
            duration_minutes=item.get("duration_minutes", 60),
            thumbnail_url=item.get("thumbnail_url"),
            icon=item.get("icon"),
            language=item.get("language"),
            analysis_status=item.get("analysis_status", "pending"),
            # Learning content fields
            learning_outcomes=item.get("learning_outcomes", []),
            prerequisites=item.get("prerequisites", []),
            technologies=item.get("technologies", []),
            # Repository signals
            stars=item.get("stars"),
            forks=item.get("forks"),
            last_commit_date=datetime.fromisoformat(item["last_commit_date"].replace("Z", "+00:00")) if item.get("last_commit_date") else None,
            contributors=item.get("contributors", []),
            # Contributor tracking
            contributor_create_email=item.get("contributor_create_email"),
            contributor_update_email=item.get("contributor_update_email"),
            # Localization fields
            title_kr=item.get("title_kr"),
            description_kr=item.get("description_kr"),
            # Resource links
            video_url=item.get("video_url"),
            docs_url=item.get("docs_url"),
            pptx_url=item.get("pptx_url"),
            # Stats
            view_count=item.get("view_count", 0),
            bookmark_count=item.get("bookmark_count", 0),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
            published_at=datetime.fromisoformat(item["published_at"]) if item.get("published_at") else None,
        )

    def publish(self) -> None:
        """Mark content as published."""
        self.status = ContentStatus.PUBLISHED
        self.published_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def increment_view(self) -> None:
        """Increment view count."""
        self.view_count += 1
        self.updated_at = datetime.utcnow()


class ContentPublic(BaseModel):
    """Public view of content (for API responses)."""

    id: str
    title: str
    description: str
    content_type: str
    categories: list[str]
    level: str
    duration_minutes: int
    thumbnail_url: Optional[str]
    icon: Optional[str]
    source_url: str
    view_count: int
    bookmark_count: int
    published_at: Optional[datetime]
    # Learning content fields
    learning_outcomes: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    stars: Optional[int] = None
    # Localization fields
    title_kr: Optional[str] = None
    description_kr: Optional[str] = None

    @classmethod
    def from_content(cls, content: Content) -> "ContentPublic":
        """Create public view from Content model."""
        return cls(
            id=content.id,
            title=content.title,
            description=content.description,
            content_type=content.content_type.value,
            categories=content.categories,
            level=content.level,
            duration_minutes=content.duration_minutes,
            thumbnail_url=content.thumbnail_url,
            icon=content.icon,
            source_url=content.source_url,
            view_count=content.view_count,
            bookmark_count=content.bookmark_count,
            published_at=content.published_at,
            # Learning content fields
            learning_outcomes=content.learning_outcomes,
            prerequisites=content.prerequisites,
            technologies=content.technologies,
            stars=content.stars,
            # Localization fields
            title_kr=content.title_kr,
            description_kr=content.description_kr,
        )
