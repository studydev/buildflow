"""Content model for learning resources."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.models.enums import ContentStatus, ContentType


class Content(BaseModel):
    """
    Content model representing a learning resource.

    Partition Key: contributor_id (for efficient contributor-based queries)
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    contributor_id: Optional[str] = None  # Made optional for pipeline creation

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
    og_image_url: Optional[str] = None  # Open Graph image for social sharing
    icon: Optional[str] = None
    language: Optional[str] = None  # Primary programming language

    # Analysis results
    analysis_status: str = "pending"  # pending, processing, completed, failed
    analysis_result: Optional[dict] = None

    # Pipeline references (Milestone 2)
    raw_extraction_id: Optional[UUID] = None  # Reference to immutable RawExtraction
    enrichment_version: Optional[str] = None  # Semantic version e.g., "1.0.0"
    last_enriched_at: Optional[datetime] = None
    popularity_score: Optional[float] = None  # 0.0-1.0 normalized score

    # Enrichment fields (Milestone 3 - design.md §5 Content Extended)
    summary_short: Optional[str] = None  # max 200 chars
    summary_long: Optional[str] = None  # max 2000 chars
    difficulty_level: Optional[str] = None  # beginner/intermediate/advanced
    estimated_time: Optional[str] = None  # e.g., "2-4 hours"
    learning_outcomes: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)

    # Repository signals (for popularity score)
    stars: Optional[int] = None
    forks: Optional[int] = None
    last_commit_date: Optional[datetime] = None
    is_maintained: Optional[bool] = None

    # Quality signals
    has_documentation: Optional[bool] = None
    has_tests: Optional[bool] = None
    has_ci: Optional[bool] = None

    # Localization fields (Milestone 5 - design.md §3.3)
    title_kr: Optional[str] = None
    description_kr: Optional[str] = None
    summary_kr: Optional[str] = None
    prerequisites_kr: list[str] = Field(default_factory=list)
    learning_outcomes_kr: list[str] = Field(default_factory=list)
    localized_at: Optional[datetime] = None
    localization_model: Optional[str] = None

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
            "og_image_url": self.og_image_url,
            "icon": self.icon,
            "language": self.language,
            "analysis_status": self.analysis_status,
            "analysis_result": self.analysis_result,
            "raw_extraction_id": str(self.raw_extraction_id) if self.raw_extraction_id else None,
            "enrichment_version": self.enrichment_version,
            "last_enriched_at": self.last_enriched_at.isoformat() if self.last_enriched_at else None,
            "popularity_score": self.popularity_score,
            # Enrichment fields (Milestone 3)
            "summary_short": self.summary_short,
            "summary_long": self.summary_long,
            "difficulty_level": self.difficulty_level,
            "estimated_time": self.estimated_time,
            "learning_outcomes": self.learning_outcomes,
            "prerequisites": self.prerequisites,
            "technologies": self.technologies,
            # Repository signals
            "stars": self.stars,
            "forks": self.forks,
            "last_commit_date": self.last_commit_date.isoformat() if self.last_commit_date else None,
            "is_maintained": self.is_maintained,
            # Quality signals
            "has_documentation": self.has_documentation,
            "has_tests": self.has_tests,
            "has_ci": self.has_ci,
            # Localization fields (Milestone 5)
            "title_kr": self.title_kr,
            "description_kr": self.description_kr,
            "summary_kr": self.summary_kr,
            "prerequisites_kr": self.prerequisites_kr,
            "learning_outcomes_kr": self.learning_outcomes_kr,
            "localized_at": self.localized_at.isoformat() if self.localized_at else None,
            "localization_model": self.localization_model,
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
        from uuid import UUID

        raw_extraction_id = None
        if item.get("raw_extraction_id"):
            try:
                raw_extraction_id = UUID(item["raw_extraction_id"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=item["id"],
            contributor_id=item.get("contributor_id"),
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
            og_image_url=item.get("og_image_url"),
            icon=item.get("icon"),
            language=item.get("language"),
            analysis_status=item.get("analysis_status", "pending"),
            analysis_result=item.get("analysis_result"),
            raw_extraction_id=raw_extraction_id,
            enrichment_version=item.get("enrichment_version"),
            last_enriched_at=datetime.fromisoformat(item["last_enriched_at"]) if item.get("last_enriched_at") else None,
            popularity_score=item.get("popularity_score"),
            # Enrichment fields (Milestone 3)
            summary_short=item.get("summary_short"),
            summary_long=item.get("summary_long"),
            difficulty_level=item.get("difficulty_level"),
            estimated_time=item.get("estimated_time"),
            learning_outcomes=item.get("learning_outcomes", []),
            prerequisites=item.get("prerequisites", []),
            technologies=item.get("technologies", []),
            # Repository signals
            stars=item.get("stars"),
            forks=item.get("forks"),
            last_commit_date=datetime.fromisoformat(item["last_commit_date"]) if item.get("last_commit_date") else None,
            is_maintained=item.get("is_maintained"),
            # Quality signals
            has_documentation=item.get("has_documentation"),
            has_tests=item.get("has_tests"),
            has_ci=item.get("has_ci"),
            # Localization fields (Milestone 5)
            title_kr=item.get("title_kr"),
            description_kr=item.get("description_kr"),
            summary_kr=item.get("summary_kr"),
            prerequisites_kr=item.get("prerequisites_kr", []),
            learning_outcomes_kr=item.get("learning_outcomes_kr", []),
            localized_at=datetime.fromisoformat(item["localized_at"]) if item.get("localized_at") else None,
            localization_model=item.get("localization_model"),
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
    og_image_url: Optional[str]
    icon: Optional[str]
    source_url: str
    view_count: int
    bookmark_count: int
    published_at: Optional[datetime]
    # Enrichment fields (Milestone 3)
    summary_short: Optional[str] = None
    summary_long: Optional[str] = None
    difficulty_level: Optional[str] = None
    estimated_time: Optional[str] = None
    learning_outcomes: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    popularity_score: Optional[float] = None
    stars: Optional[int] = None
    is_maintained: Optional[bool] = None

    # Localization fields (Milestone 5)
    title_kr: Optional[str] = None
    description_kr: Optional[str] = None
    summary_kr: Optional[str] = None
    prerequisites_kr: list[str] = Field(default_factory=list)
    learning_outcomes_kr: list[str] = Field(default_factory=list)

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
            og_image_url=content.og_image_url,
            icon=content.icon,
            source_url=content.source_url,
            view_count=content.view_count,
            bookmark_count=content.bookmark_count,
            published_at=content.published_at,
            # Enrichment fields
            summary_short=content.summary_short,
            summary_long=content.summary_long,
            difficulty_level=content.difficulty_level,
            estimated_time=content.estimated_time,
            learning_outcomes=content.learning_outcomes,
            prerequisites=content.prerequisites,
            technologies=content.technologies,
            popularity_score=content.popularity_score,
            stars=content.stars,
            is_maintained=content.is_maintained,
            # Localization fields
            title_kr=content.title_kr,
            description_kr=content.description_kr,
            summary_kr=content.summary_kr,
            prerequisites_kr=content.prerequisites_kr,
            learning_outcomes_kr=content.learning_outcomes_kr,
        )
