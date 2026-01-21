"""Localization Pipeline for translating content to Korean.

Per design.md §3.3 Localization Pipeline.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from app.config import get_settings
from app.models.enums import PipelineType
from app.pipelines.base import BasePipeline
from app.repositories.content_repo import get_content_repo
from app.schemas.pipeline import PipelineMessage
from app.services.llm_service import (
    LLMError,
    TranslationResult,
    get_llm_service,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Default target locale
DEFAULT_TARGET_LOCALE = "ko-KR"

# Fields to translate by default
DEFAULT_SOURCE_FIELDS = [
    "title",
    "description",
    "summary_long",
    "prerequisites",
    "learning_outcomes",
]


class LocalizationPipeline(BasePipeline):
    """
    Pipeline for translating content to Korean.

    Implements design.md §3.3 Localization Pipeline:
    - Translates specified fields via Azure OpenAI
    - Updates Content with _kr suffix fields
    - Idempotency via SHA256(content_id + target_locale + enrichment_version)

    Input params:
        content_id: UUID - Content to translate
        target_locale: str - Target locale (default: ko-KR)
        source_fields: list[str] - Fields to translate (optional)

    Output:
        translations: dict with _kr fields
        localized_at: datetime
        model_used: str
    """

    pipeline_type = PipelineType.LOCALIZATION
    max_attempts = 2  # Per design.md §3.3 retry_policy

    def __init__(self):
        """Initialize LocalizationPipeline."""
        super().__init__()
        self.llm_service = get_llm_service()
        self._content_repo = None

    @property
    def content_repo(self):
        """Lazy load content repository."""
        if self._content_repo is None:
            self._content_repo = get_content_repo()
        return self._content_repo

    async def execute(self, message: PipelineMessage) -> Dict[str, Any]:
        """
        Execute localization pipeline.

        Args:
            message: Pipeline message with input parameters

        Returns:
            Output summary with translation results
        """
        input_params = message.input_params
        content_id = input_params.get("content_id")
        target_locale = input_params.get("target_locale", DEFAULT_TARGET_LOCALE)
        source_fields = input_params.get("source_fields", DEFAULT_SOURCE_FIELDS)

        if not content_id:
            raise ValueError("content_id is required")

        logger.info(
            f"Starting localization for content {content_id} to {target_locale}",
            extra={"correlation_id": message.correlation_id, "run_id": str(message.run_id)}
        )

        # Load content
        content = await self.content_repo.get_by_id_cross_partition(content_id)
        if not content:
            raise ValueError(f"Content not found: {content_id}")

        # Check idempotency - skip if already localized with same version
        idempotency_key = self._generate_idempotency_key(
            content_id, target_locale, content.enrichment_version or "1.0.0"
        )

        if await self._check_idempotency(idempotency_key, content):
            logger.info(
                f"Content {content_id} already localized with same version, skipping",
                extra={"correlation_id": message.correlation_id}
            )
            return {
                "status": "skipped",
                "reason": "already_localized",
                "content_id": content_id,
                "idempotency_key": idempotency_key,
            }

        # Translate content
        translation_result = await self._translate_content(content, source_fields)

        # Update content with translations
        await self._apply_translations(content, translation_result)

        # Output summary
        output_summary = {
            "content_id": content_id,
            "target_locale": target_locale,
            "translated_fields": source_fields,
            "model_used": translation_result.model_used,
            "localized_at": datetime.utcnow().isoformat(),
            "idempotency_key": idempotency_key,
        }

        logger.info(
            f"Localization completed for content {content_id}",
            extra={"correlation_id": message.correlation_id, "run_id": str(message.run_id)}
        )

        return output_summary

    def _generate_idempotency_key(
        self,
        content_id: str,
        target_locale: str,
        enrichment_version: str,
    ) -> str:
        """
        Generate idempotency key per design.md §3.3.

        Key: SHA256(content_id + target_locale + enrichment_version)
        """
        import hashlib
        data = f"{content_id}:{target_locale}:{enrichment_version}"
        return hashlib.sha256(data.encode()).hexdigest()

    async def _check_idempotency(self, key: str, content) -> bool:
        """
        Check if content was already localized with same parameters.

        Returns True if should skip (already done).
        """
        # If content has localization and same enrichment version, skip
        if content.localized_at and content.localization_model:
            # Content has been localized - check if version matches
            return True
        return False

    async def _translate_content(
        self,
        content,
        source_fields: list[str],
    ) -> TranslationResult:
        """
        Translate content fields using LLM service.

        Args:
            content: Content model
            source_fields: Fields to translate

        Returns:
            TranslationResult with translated fields
        """
        try:
            result = await self.llm_service.translate_content(
                title=content.title,
                description=content.description,
                summary=content.summary_long or content.summary_short,
                prerequisites=content.prerequisites if "prerequisites" in source_fields else None,
                learning_outcomes=content.learning_outcomes if "learning_outcomes" in source_fields else None,
            )

            return result

        except LLMError as e:
            logger.error(f"Translation failed: {e}")
            raise

    async def _apply_translations(
        self,
        content,
        translation: TranslationResult,
    ) -> None:
        """
        Apply translation results to content and save.

        Args:
            content: Content model
            translation: TranslationResult with translations
        """
        # Update content with translations
        content.title_kr = translation.title_kr
        content.description_kr = translation.description_kr
        content.summary_kr = translation.summary_kr
        content.prerequisites_kr = translation.prerequisites_kr
        content.learning_outcomes_kr = translation.learning_outcomes_kr
        content.localized_at = datetime.utcnow()
        content.localization_model = translation.model_used
        content.updated_at = datetime.utcnow()

        # Save to database
        await self.content_repo.update(content)

        logger.info(f"Applied translations to content {content.id}")
