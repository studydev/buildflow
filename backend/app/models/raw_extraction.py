"""
RawExtraction model per design.md §5.

Represents immutable raw data extracted from GitHub repositories.
Once created, this document MUST NOT be updated - it serves as
an audit trail of exactly what was extracted at a point in time.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


class RawExtraction(BaseModel):
    """
    Immutable raw extraction document stored in Cosmos DB.
    
    Partition Key: source_url_hash (SHA256)
    Container: raw_extractions
    
    Per design.md §5 RawExtraction schema.
    
    IMPORTANT: This model is IMMUTABLE. The repository MUST NOT
    provide an update() method. Re-extraction creates a new document.
    """
    
    # Primary key
    id: UUID = Field(default_factory=uuid4, description="Unique extraction ID")
    
    # Source identification
    source_url: str = Field(description="GitHub repository URL")
    source_url_hash: str = Field(
        description="SHA256 hash of source_url for deduplication and partition key"
    )
    
    # Immutable raw data
    readme_content: str = Field(
        default="",
        description="Raw README.md content"
    )
    readme_hash: str = Field(
        default="",
        description="SHA256 hash of readme_content for change detection"
    )
    
    # Repository metadata at extraction time
    repository_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Stars, forks, watchers, topics, license, etc."
    )
    
    # Commit activity
    commit_activity: dict[str, Any] = Field(
        default_factory=dict,
        description="Commit counts, last commit date, contributors count"
    )
    
    # Release information
    releases: dict[str, Any] = Field(
        default_factory=dict,
        description="Latest version, release count, last release date"
    )
    
    # Extracted URLs from README
    extracted_urls: dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Demo URL, docs URL, video URL extracted from README"
    )
    
    # Extraction metadata
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When extraction was performed"
    )
    github_api_version: str = Field(
        default="2022-11-28",
        description="GitHub API version used for extraction"
    )
    run_id: UUID = Field(
        description="Pipeline run ID that created this extraction"
    )
    
    def to_cosmos_document(self) -> dict[str, Any]:
        """Convert to Cosmos DB document format."""
        doc = self.model_dump(mode="json")
        doc["id"] = str(self.id)
        doc["run_id"] = str(self.run_id)
        return doc
    
    @classmethod
    def from_cosmos_document(cls, doc: dict[str, Any]) -> "RawExtraction":
        """Create from Cosmos DB document."""
        return cls.model_validate(doc)
    
    class Config:
        use_enum_values = True


class ImmutableRecordError(Exception):
    """Raised when attempting to modify an immutable record."""
    
    def __init__(self, record_type: str, record_id: str):
        self.record_type = record_type
        self.record_id = record_id
        super().__init__(
            f"{record_type} records are immutable and cannot be updated. "
            f"Record ID: {record_id}. Create a new extraction instead."
        )
