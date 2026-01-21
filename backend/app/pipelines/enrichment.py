"""Enrichment Pipeline - AI-powered content enhancement.

Per design.md §3.2: Enhances raw data with AI-generated insights.

Pipeline Type: enrichment
Trigger: analysis_completed | manual_trigger | version_bump
Execution: Azure Container Apps Job
Depends on: analysis (raw data must exist)
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from app.models.content import Content
from app.models.enums import PipelineStatus, PipelineType
from app.models.pipeline_run import PipelineRun
from app.models.raw_extraction import RawExtraction
from app.pipelines.base import BasePipeline
from app.repositories.content_repo import ContentRepository
from app.repositories.pipeline_repo import PipelineRepository
from app.repositories.raw_extraction_repo import RawExtractionRepository
from app.schemas.pipeline import PipelineMessage
from app.services.llm_service import (
    EnrichmentResult,
    LLMAPIError,
    LLMRateLimitError,
    LLMTimeoutError,
    get_llm_service,
)

logger = logging.getLogger(__name__)


# Enrichment version - increment when changing enrichment logic
ENRICHMENT_VERSION = "1.0.0"


@dataclass
class PopularityInputs:
    """Input signals for popularity score calculation.
    
    Per design.md §3.2 popularity_score definition.
    """
    stars: int = 0
    last_commit_date: Optional[datetime] = None
    commit_activity_30d: int = 0
    commit_activity_90d: int = 0
    release_count: int = 0


def calculate_popularity_score(inputs: PopularityInputs) -> float:
    """Calculate normalized popularity score.
    
    Per design.md §3.2 output_contract:
    - Stars: 40% (primary popularity signal)
    - Recency: 25% (maintenance signal)
    - Commit activity: 20% (active development)
    - Release frequency: 15% (maturity indicator)
    
    All inputs normalized to 0.0-1.0 using log-based scaling.
    
    Args:
        inputs: PopularityInputs with repository signals
        
    Returns:
        Float 0.0-1.0 popularity score
    """
    import math
    
    # Normalization constants (based on typical GitHub repo distributions)
    STARS_MAX = 10000  # Repos with 10k+ stars get max score
    COMMIT_30D_MAX = 100  # 100+ commits in 30 days is very active
    COMMIT_90D_MAX = 300  # 300+ commits in 90 days is very active
    RELEASE_MAX = 50  # 50+ releases indicates mature project
    RECENCY_DECAY_DAYS = 180  # 6 months for freshness decay
    
    # Star score (logarithmic scale, 40% weight)
    if inputs.stars > 0:
        star_score = min(1.0, math.log10(inputs.stars + 1) / math.log10(STARS_MAX + 1))
    else:
        star_score = 0.0
    
    # Recency score (exponential decay, 25% weight)
    if inputs.last_commit_date:
        days_since_commit = (datetime.utcnow() - inputs.last_commit_date).days
        recency_score = max(0.0, 1.0 - (days_since_commit / RECENCY_DECAY_DAYS))
    else:
        recency_score = 0.0  # No commit date = assume stale
    
    # Commit activity score (20% weight)
    # Combine 30d and 90d activity
    activity_30d = min(1.0, inputs.commit_activity_30d / COMMIT_30D_MAX) if inputs.commit_activity_30d > 0 else 0.0
    activity_90d = min(1.0, inputs.commit_activity_90d / COMMIT_90D_MAX) if inputs.commit_activity_90d > 0 else 0.0
    # Weight recent activity higher
    commit_score = (activity_30d * 0.6 + activity_90d * 0.4)
    
    # Release frequency score (15% weight)
    if inputs.release_count > 0:
        release_score = min(1.0, math.log10(inputs.release_count + 1) / math.log10(RELEASE_MAX + 1))
    else:
        release_score = 0.0
    
    # Weighted sum (weights sum to 1.0)
    popularity = (
        star_score * 0.40 +
        recency_score * 0.25 +
        commit_score * 0.20 +
        release_score * 0.15
    )
    
    # Ensure bounds
    return max(0.0, min(1.0, popularity))


class EnrichmentPipeline(BasePipeline):
    """AI-powered content enrichment pipeline.
    
    Per design.md §3.2:
    - Loads RawExtraction for content
    - Calls LLM for enrichment
    - Calculates popularity score
    - Updates Content with enriched data
    - Triggers next pipeline if chain specified
    """
    
    pipeline_type = PipelineType.ENRICHMENT
    
    def __init__(
        self,
        content_repo: Optional[ContentRepository] = None,
        pipeline_repo: Optional[PipelineRepository] = None,
        raw_extraction_repo: Optional[RawExtractionRepository] = None,
    ):
        """Initialize EnrichmentPipeline.
        
        Args:
            content_repo: Content repository
            pipeline_repo: Pipeline repository
            raw_extraction_repo: RawExtraction repository
        """
        super().__init__()
        self.content_repo = content_repo
        self.pipeline_repo = pipeline_repo
        self.raw_extraction_repo = raw_extraction_repo
        self.llm_service = get_llm_service()
        
        # Pipeline state
        self.content: Optional[Content] = None
        self.raw_extraction: Optional[RawExtraction] = None
        self.enrichment_result: Optional[EnrichmentResult] = None
        self.popularity_score: float = 0.0
    
    def _generate_idempotency_key(self, content_id: str, enrichment_version: str) -> str:
        """Generate idempotency key.
        
        Per design.md §3.2 idempotency_strategy:
        key = SHA256(content_id + enrichment_version)
        """
        data = f"{content_id}{enrichment_version}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def _check_idempotency(
        self,
        content_id: str,
        enrichment_version: str,
        force_refresh: bool = False,
    ) -> Optional[PipelineRun]:
        """Check if enrichment already exists.
        
        Per design.md §3.2:
        - behavior: replace_if_version_differs
        - If same version exists, skip (unless force_refresh)
        
        Returns:
            Existing PipelineRun if should skip, None if should proceed
        """
        if force_refresh:
            logger.info("Force refresh enabled, skipping idempotency check")
            return None
        
        if not self.pipeline_repo:
            return None
        
        # Look for recent successful enrichment runs for this content
        try:
            content_uuid = UUID(content_id)
            runs, _ = await self.pipeline_repo.list_by_content_id(
                content_id=content_uuid,
                limit=50,
            )
            
            # Check if any completed enrichment run has same version
            for run in runs:
                if (
                    run.pipeline_type == PipelineType.ENRICHMENT
                    and run.status == PipelineStatus.COMPLETED
                    and run.enrichment_version == enrichment_version
                ):
                    logger.info(
                        f"Skipping enrichment - already completed with version {enrichment_version}"
                    )
                    return run
        except Exception as e:
            logger.warning(f"Idempotency check failed, proceeding anyway: {e}")
        
        return None
    
    async def validate_input(self, input_params: dict[str, Any]) -> bool:
        """Validate input parameters.
        
        Required:
        - content_id: UUID of content to enrich
        
        Optional:
        - enrichment_version: Version string (default: ENRICHMENT_VERSION)
        - force_refresh: Force re-enrichment (default: False)
        """
        content_id = input_params.get("content_id")
        if not content_id:
            self.error_message = "content_id is required"
            return False
        
        # Validate content_id format
        try:
            UUID(content_id) if isinstance(content_id, str) else content_id
        except (ValueError, TypeError):
            self.error_message = f"Invalid content_id format: {content_id}"
            return False
        
        return True
    
    async def execute(self, message: PipelineMessage) -> dict[str, Any]:
        """Execute enrichment pipeline.
        
        Steps per design.md §3.2:
        1. Load RawExtraction for content
        2. Call LLM for enrichment
        3. Calculate popularity score
        4. Update Content with enriched data
        5. Set enrichment_version and last_enriched_at
        6. Trigger next pipeline if chain specified
        
        Args:
            message: PipelineMessage with input parameters containing:
                - content_id: str (UUID)
                - enrichment_version: str (optional)
                - force_refresh: bool (optional)
                - chain: str (optional) - pipeline chain to trigger
            
        Returns:
            Output summary dict
        """
        input_params = message.input_params
        content_id = str(message.content_id or input_params.get("content_id"))
        enrichment_version = message.enrichment_version or input_params.get("enrichment_version", ENRICHMENT_VERSION)
        force_refresh = input_params.get("force_refresh", False)
        
        # Step 0: Check idempotency
        existing_run = await self._check_idempotency(
            content_id, enrichment_version, force_refresh
        )
        if existing_run:
            return {
                "status": "skipped",
                "reason": "already_enriched",
                "existing_run_id": str(existing_run.id),
            }
        
        # Step 1: Load Content
        if not self.content_repo:
            raise RuntimeError("ContentRepository not configured")
        
        # Use cross-partition query since we don't have contributor_id
        self.content = await self.content_repo.get_by_id_cross_partition(content_id)
        if not self.content:
            raise ValueError(f"Content not found: {content_id}")
        
        logger.info(f"Enriching content: {self.content.title}")
        
        # Step 2: Load RawExtraction
        if self.content.raw_extraction_id and self.raw_extraction_repo:
            self.raw_extraction = await self.raw_extraction_repo.get_by_id(
                self.content.raw_extraction_id  # Already a UUID
            )
        
        # Extract data from RawExtraction or Content
        extraction_data = self._get_extraction_data()
        
        # Step 3: Call LLM for enrichment
        self.enrichment_result = await self._call_llm_enrichment(extraction_data)
        
        # Step 4: Calculate popularity score
        self.popularity_score = await self._calculate_popularity(extraction_data)
        
        # Step 5: Update Content with enriched data
        await self._update_content(enrichment_version)
        
        # Step 6: Return result (chaining is handled by BasePipeline.on_success)
        # Note: next pipeline trigger is handled via message.chain in BasePipeline
        next_pipeline = await self._trigger_next_pipeline(message.chain)
        
        return {
            "status": "enriched",
            "content_id": content_id,
            "enrichment_version": enrichment_version,
            "popularity_score": self.popularity_score,
            "model_used": self.enrichment_result.model_used if self.enrichment_result else "none",
            "next_pipeline": next_pipeline,
        }
    
    def _get_extraction_data(self) -> dict[str, Any]:
        """Get extraction data from RawExtraction or Content."""
        # Content is required for this method
        if not self.content:
            return {}
        
        if self.raw_extraction:
            # Extract from RawExtraction fields
            repo_meta = self.raw_extraction.repository_metadata or {}
            commit_activity = self.raw_extraction.commit_activity or {}
            releases = self.raw_extraction.releases or {}
            
            return {
                "title": self.content.title,
                "description": self.content.description,
                "readme_excerpt": (self.raw_extraction.readme_content or "")[:4000],
                "technologies": repo_meta.get("topics", []) or self.content.technologies,
                "categories": self.content.categories,
                "language": repo_meta.get("primary_language") or self.content.language,
                "stars": repo_meta.get("stars", 0),
                "forks": repo_meta.get("forks", 0),
                "last_commit_date": commit_activity.get("last_commit_date"),
                "commit_activity_30d": commit_activity.get("last_30_days", 0),
                "commit_activity_90d": commit_activity.get("last_90_days", 0),
                "release_count": releases.get("count", 0),
                "has_tests": repo_meta.get("has_tests", False),
                "has_ci": repo_meta.get("has_ci", False),
            }
        
        # Fallback to Content data
        return {
            "title": self.content.title,
            "description": self.content.description,
            "readme_excerpt": "",
            "technologies": self.content.technologies,
            "categories": self.content.categories,
            "language": self.content.language,
            "stars": self.content.stars or 0,
            "forks": self.content.forks or 0,
            "last_commit_date": self.content.last_commit_date.isoformat() if self.content.last_commit_date else None,
            "commit_activity_30d": 0,
            "commit_activity_90d": 0,
            "release_count": 0,
            "has_tests": self.content.has_tests or False,
            "has_ci": self.content.has_ci or False,
        }
    
    async def _call_llm_enrichment(self, extraction_data: dict) -> EnrichmentResult:
        """Call LLM service for enrichment.
        
        Per design.md §3.2 retry_policy:
        - max_attempts: 2
        - backoff: fixed (5s)
        - retryable_errors: [LLM_TIMEOUT, LLM_RATE_LIMIT]
        """
        import asyncio
        
        max_attempts = 2
        backoff_seconds = 5
        last_error: Optional[Exception] = None
        
        for attempt in range(max_attempts):
            try:
                result = await self.llm_service.enrich_content(
                    title=extraction_data.get("title", ""),
                    description=extraction_data.get("description", ""),
                    readme_excerpt=extraction_data.get("readme_excerpt", ""),
                    technologies=extraction_data.get("technologies"),
                    categories=extraction_data.get("categories"),
                    language=extraction_data.get("language"),
                    stars=extraction_data.get("stars", 0),
                    last_commit_date=extraction_data.get("last_commit_date"),
                    has_tests=extraction_data.get("has_tests", False),
                    has_ci=extraction_data.get("has_ci", False),
                )
                return result
                
            except (LLMTimeoutError, LLMRateLimitError) as e:
                last_error = e
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"LLM error (attempt {attempt + 1}/{max_attempts}): {e}"
                    )
                    await asyncio.sleep(backoff_seconds)
                else:
                    logger.error(f"LLM failed after {max_attempts} attempts: {e}")
                    raise
            except LLMAPIError as e:
                # Non-retryable error
                logger.error(f"LLM API error (non-retryable): {e}")
                raise
        
        # Should not reach here, but raise last error if we do
        if last_error:
            raise last_error
        raise RuntimeError("LLM enrichment failed with no error captured")
    
    async def _calculate_popularity(self, extraction_data: dict) -> float:
        """Calculate popularity score from extraction data."""
        last_commit_date = None
        if extraction_data.get("last_commit_date"):
            try:
                if isinstance(extraction_data["last_commit_date"], str):
                    last_commit_date = datetime.fromisoformat(
                        extraction_data["last_commit_date"].replace("Z", "+00:00")
                    )
                else:
                    last_commit_date = extraction_data["last_commit_date"]
            except (ValueError, TypeError):
                pass
        
        inputs = PopularityInputs(
            stars=extraction_data.get("stars", 0),
            last_commit_date=last_commit_date,
            commit_activity_30d=extraction_data.get("commit_activity_30d", 0),
            commit_activity_90d=extraction_data.get("commit_activity_90d", 0),
            release_count=extraction_data.get("release_count", 0),
        )
        
        return calculate_popularity_score(inputs)
    
    async def _update_content(self, enrichment_version: str) -> None:
        """Update Content with enriched data."""
        if not self.content or not self.content_repo:
            return
        
        now = datetime.utcnow()
        
        # Update from enrichment result
        if self.enrichment_result:
            self.content.summary_short = self.enrichment_result.summary_short
            self.content.summary_long = self.enrichment_result.summary_long
            self.content.categories = self.enrichment_result.categories or self.content.categories
            self.content.technologies = self.enrichment_result.technologies or self.content.technologies
            self.content.difficulty_level = self.enrichment_result.difficulty_level
            self.content.estimated_time = self.enrichment_result.estimated_time
            self.content.prerequisites = self.enrichment_result.prerequisites
            self.content.learning_outcomes = self.enrichment_result.learning_outcomes
            
            # Quality signals
            quality = self.enrichment_result.quality_signals
            self.content.has_documentation = quality.get("has_documentation", False)
            self.content.has_tests = quality.get("has_tests", False)
            self.content.has_ci = quality.get("has_ci", False)
            self.content.is_maintained = quality.get("is_maintained", False)
        
        # Update popularity and version
        self.content.popularity_score = self.popularity_score
        self.content.enrichment_version = enrichment_version
        self.content.last_enriched_at = now
        self.content.updated_at = now
        
        # Persist
        await self.content_repo.update(self.content)
        
        logger.info(
            f"Content enriched: {self.content.id} "
            f"(version={enrichment_version}, popularity={self.popularity_score:.3f})"
        )
    
    async def _trigger_next_pipeline(self, chain: Optional[str]) -> Optional[str]:
        """Trigger next pipeline in chain if specified.
        
        Uses BasePipeline's trigger_next_pipeline via PipelineMessage.
        
        Returns the name of the triggered pipeline, or None.
        """
        if not chain:
            return None
        
        # Chain definitions per design.md §4
        PIPELINE_CHAINS = {
            "full_ingestion": ["analysis", "enrichment", "localization", "asset_generation", "indexing"],
            "refresh_enrichment": ["enrichment", "localization", "indexing"],
            "reindex_only": ["indexing"],
        }
        
        if chain not in PIPELINE_CHAINS:
            logger.warning(f"Unknown pipeline chain: {chain}")
            return None
        
        chain_steps = PIPELINE_CHAINS[chain]
        current_index = chain_steps.index("enrichment") if "enrichment" in chain_steps else -1
        
        if current_index >= 0 and current_index < len(chain_steps) - 1:
            next_step = chain_steps[current_index + 1]
            logger.info(f"Chain '{chain}': next pipeline is '{next_step}'")
            # Note: Actual triggering is handled by BasePipeline.on_success()
            # which calls trigger_next_pipeline() with full message context
            return next_step
        
        return None
    
    async def on_success(self, message: PipelineMessage, output: dict[str, Any]) -> None:
        """Handle successful completion with enrichment-specific logging."""
        logger.info(
            f"Enrichment completed for content {output.get('content_id')} "
            f"(popularity={output.get('popularity_score', 0):.3f})"
        )
        # Call parent to update status and trigger chain
        await super().on_success(message, output)
    
    async def on_failure(self, message: PipelineMessage, error: Exception) -> None:
        """Handle pipeline failure with content status update."""
        logger.error(f"Enrichment failed: {error}")
        
        # Update content status if possible
        if self.content and self.content_repo:
            self.content.analysis_status = "failed"
            self.content.updated_at = datetime.utcnow()
            try:
                await self.content_repo.update(self.content)
            except Exception as e:
                logger.error(f"Failed to update content status: {e}")
        
        # Call parent to update pipeline status
        await super().on_failure(message, error)
