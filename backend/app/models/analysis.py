"""AnalysisRequest model for content analysis submissions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from app.models.enums import AnalysisStatus


@dataclass
class StatusHistoryEntry:
    """Entry in the status history."""

    status: AnalysisStatus
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
    def from_dict(cls, data: dict[str, Any]) -> "StatusHistoryEntry":
        """Create from dictionary."""
        return cls(
            status=AnalysisStatus(data["status"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            message=data.get("message"),
        )


@dataclass
class AnalysisResult:
    """Result of content analysis."""

    # 기본 정보
    title: Optional[str] = None
    title_kr: Optional[str] = None  # 한국어 제목
    description: Optional[str] = None
    description_kr: Optional[str] = None  # 한국어 설명
    topic: Optional[str] = None  # 주제/토픽 요약

    # 분류 정보
    content_type: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    level: Optional[str] = None
    duration_minutes: Optional[int] = None

    # 기술 스택
    technologies: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)

    # 학습 정보
    learning_objectives: list[str] = field(default_factory=list)
    lab_modules: list[str] = field(default_factory=list)  # 실습 모듈 목록

    # 저장소 메타데이터 (필터링/정렬용)
    source_url: Optional[str] = None
    stars: int = 0
    forks: int = 0
    watchers: int = 0
    language: Optional[str] = None  # Primary programming language
    languages: Optional[str] = None  # Top 10 languages, comma-separated
    license: Optional[str] = None
    topics: Optional[str] = None  # Topics, comma-separated
    owner: Optional[str] = None  # Repository owner/author
    contributors: Optional[str] = None  # Top contributors, comma-separated
    contributors_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None  # Last update date

    # 외부 링크
    demo_url: Optional[str] = None
    docs_url: Optional[str] = None
    video_url: Optional[str] = None  # YouTube or video link
    homepage_url: Optional[str] = None

    # 메타데이터
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "title_kr": self.title_kr,
            "description": self.description,
            "description_kr": self.description_kr,
            "topic": self.topic,
            "content_type": self.content_type,
            "categories": self.categories,
            "level": self.level,
            "duration_minutes": self.duration_minutes,
            "technologies": self.technologies,
            "prerequisites": self.prerequisites,
            "learning_objectives": self.learning_objectives,
            "lab_modules": self.lab_modules,
            # Repository metadata
            "source_url": self.source_url,
            "stars": self.stars,
            "forks": self.forks,
            "watchers": self.watchers,
            "language": self.language,
            "languages": self.languages,
            "license": self.license,
            "topics": self.topics,
            "owner": self.owner,
            "contributors": self.contributors,
            "contributors_count": self.contributors_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # External links
            "demo_url": self.demo_url,
            "docs_url": self.docs_url,
            "video_url": self.video_url,
            "homepage_url": self.homepage_url,
            "raw_metadata": self.raw_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisResult":
        """Create from dictionary."""
        return cls(
            title=data.get("title"),
            title_kr=data.get("title_kr"),
            description=data.get("description"),
            description_kr=data.get("description_kr"),
            topic=data.get("topic"),
            content_type=data.get("content_type"),
            categories=data.get("categories", []),
            level=data.get("level"),
            duration_minutes=data.get("duration_minutes"),
            technologies=data.get("technologies", []),
            prerequisites=data.get("prerequisites", []),
            learning_objectives=data.get("learning_objectives", []),
            lab_modules=data.get("lab_modules", []),
            # Repository metadata
            source_url=data.get("source_url"),
            stars=data.get("stars", 0),
            forks=data.get("forks", 0),
            watchers=data.get("watchers", 0),
            language=data.get("language"),
            languages=data.get("languages"),
            license=data.get("license"),
            topics=data.get("topics"),
            owner=data.get("owner"),
            contributors=data.get("contributors"),
            contributors_count=data.get("contributors_count", 0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            # External links
            demo_url=data.get("demo_url"),
            docs_url=data.get("docs_url"),
            video_url=data.get("video_url"),
            homepage_url=data.get("homepage_url"),
            raw_metadata=data.get("raw_metadata", {}),
        )


@dataclass
class AnalysisRequest:
    """
    Model for content analysis requests.

    Partition key: user_id (for user-centric queries)
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""  # Partition key
    source_url: str = ""
    status: AnalysisStatus = AnalysisStatus.PENDING
    status_history: list[StatusHistoryEntry] = field(default_factory=list)
    result: Optional[AnalysisResult] = None
    content_ids: list[str] = field(default_factory=list)  # Created Content IDs
    error_message: Optional[str] = None
    progress: int = 0  # 0-100 percentage
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        """Add initial status to history if empty."""
        if not self.status_history:
            self.status_history.append(
                StatusHistoryEntry(
                    status=self.status,
                    timestamp=self.created_at,
                    message="Request created",
                )
            )

    def update_status(
        self,
        new_status: AnalysisStatus,
        message: Optional[str] = None,
        progress: Optional[int] = None,
    ) -> None:
        """
        Update the request status.

        Args:
            new_status: New status
            message: Optional status message
            progress: Optional progress percentage
        """
        self.status = new_status
        self.updated_at = datetime.utcnow()

        if progress is not None:
            self.progress = progress

        self.status_history.append(
            StatusHistoryEntry(
                status=new_status,
                timestamp=self.updated_at,
                message=message,
            )
        )

        if new_status in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED):
            self.completed_at = self.updated_at
            if new_status == AnalysisStatus.COMPLETED:
                self.progress = 100

    def set_result(self, result: AnalysisResult) -> None:
        """Set the analysis result and mark as completed."""
        self.result = result
        self.update_status(
            AnalysisStatus.COMPLETED,
            message="Analysis completed successfully",
            progress=100,
        )

    def set_error(self, error_message: str) -> None:
        """Set error and mark as failed."""
        self.error_message = error_message
        self.update_status(
            AnalysisStatus.FAILED,
            message=error_message,
        )

    def to_cosmos_item(self) -> dict[str, Any]:
        """Convert to Cosmos DB item."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "source_url": self.source_url,
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
            "type": "analysis_request",
            "partition_key": self.user_id,
        }

    @classmethod
    def from_cosmos_item(cls, item: dict[str, Any]) -> "AnalysisRequest":
        """Create from Cosmos DB item."""
        status_history = [
            StatusHistoryEntry.from_dict(entry)
            for entry in item.get("status_history", [])
        ]

        result = None
        if item.get("result"):
            result = AnalysisResult.from_dict(item["result"])

        return cls(
            id=item["id"],
            user_id=item["user_id"],
            source_url=item["source_url"],
            status=AnalysisStatus(item["status"]),
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
class AnalysisRequestPublic:
    """Public representation of an analysis request (for API responses)."""

    id: str
    source_url: str
    status: str
    progress: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    result: Optional[dict[str, Any]]
    content_ids: list[str]
    error_message: Optional[str]

    @classmethod
    def from_request(cls, request: AnalysisRequest) -> "AnalysisRequestPublic":
        """Create from AnalysisRequest."""
        return cls(
            id=request.id,
            source_url=request.source_url,
            status=request.status.value,
            progress=request.progress,
            created_at=request.created_at,
            updated_at=request.updated_at,
            completed_at=request.completed_at,
            result=request.result.to_dict() if request.result else None,
            content_ids=request.content_ids,
            error_message=request.error_message,
        )
