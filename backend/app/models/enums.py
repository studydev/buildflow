"""Enums for the application."""

from enum import Enum


class UserRole(str, Enum):
    """User roles in the system."""

    USER = "user"
    CONTRIBUTOR = "contributor"


class ContentStatus(str, Enum):
    """Content item status."""

    DRAFT = "draft"
    PENDING = "pending"
    ANALYZING = "analyzing"
    PUBLISHED = "published"
    ACTIVE = "active"
    FAILED = "failed"
    ARCHIVED = "archived"


class ContentType(str, Enum):
    """Types of learning content."""

    WORKSHOP = "workshop"
    LAB = "lab"
    TUTORIAL = "tutorial"
    SAMPLE = "sample"
    TEMPLATE = "template"
    SOLUTION_IDEA = "solution_idea"
    OTHER = "other"


class AnalysisStatus(str, Enum):
    """GitHub URL analysis status.

    DEPRECATED: Use PipelineStatus instead for new pipeline architecture.
    Kept for backward compatibility with existing analysis flows.
    """

    PENDING = "pending"
    QUEUED = "queued"
    FETCHING = "fetching"
    PARSING = "parsing"
    ENRICHING = "enriching"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Pipeline Architecture Enums (Constitution v2.0.0)
# =============================================================================


class PipelineType(str, Enum):
    """
    Pipeline types per design.md §2.

    Each pipeline type corresponds to a distinct processing stage
    executed as an Azure Container Apps Job.
    """

    ANALYSIS = "analysis"                   # Raw data extraction from GitHub
    ENRICHMENT = "enrichment"               # AI-powered enhancement (LLM)
    LOCALIZATION = "localization"           # Translation and adaptation
    ASSET_GENERATION = "asset_generation"   # Thumbnails, previews
    INDEXING = "indexing"                   # Search index updates


class PipelineStatus(str, Enum):
    """
    Pipeline run status per design.md §9.

    Valid transitions:
    - pending → running, cancelled
    - running → completed, failed, cancelled
    - failed → retrying, pending (manual retry)
    - retrying → running
    - completed → (terminal)
    - cancelled → (terminal)
    """

    PENDING = "pending"         # Queued, waiting to start
    RUNNING = "running"         # Currently executing
    COMPLETED = "completed"     # Successfully finished
    FAILED = "failed"           # Terminal failure
    CANCELLED = "cancelled"     # User cancelled
    RETRYING = "retrying"       # Failed, attempting retry


# Valid status transitions for state machine enforcement
VALID_STATUS_TRANSITIONS: dict[PipelineStatus, list[PipelineStatus]] = {
    PipelineStatus.PENDING: [PipelineStatus.RUNNING, PipelineStatus.CANCELLED],
    PipelineStatus.RUNNING: [PipelineStatus.COMPLETED, PipelineStatus.FAILED, PipelineStatus.CANCELLED],
    PipelineStatus.FAILED: [PipelineStatus.RETRYING, PipelineStatus.PENDING],
    PipelineStatus.RETRYING: [PipelineStatus.RUNNING],
    PipelineStatus.COMPLETED: [],  # Terminal
    PipelineStatus.CANCELLED: [],  # Terminal
}


class AssetType(str, Enum):
    """
    Generated asset types per design.md §3.4.
    """

    THUMBNAIL = "thumbnail"
    PREVIEW = "preview"
    OG_IMAGE = "og_image"


class Visibility(str, Enum):
    """
    Content visibility per design.md §7.

    - PUBLIC: Anyone can see (including anonymous users)
    - INTERNAL: Logged-in users only
    """

    PUBLIC = "public"
    INTERNAL = "internal"


class PromotionStatus(str, Enum):
    """
    Content promotion status for Dev → Prod workflow per design.md §1.
    """

    NONE = "none"                           # Not requested
    PENDING_VALIDATION = "pending_validation"  # Awaiting automated checks
    VALIDATION_FAILED = "validation_failed"    # Automated checks failed
    PENDING_APPROVAL = "pending_approval"      # Awaiting admin approval
    REJECTED = "rejected"                      # Admin rejected
    PROMOTED = "promoted"                      # Successfully promoted to Prod
