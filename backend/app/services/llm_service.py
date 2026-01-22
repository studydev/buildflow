"""LLM service for metadata extraction from repository content."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings
from app.models.analysis import AnalysisResult

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMConfigError(LLMError):
    """LLM configuration error (missing API key, etc.)."""
    pass


class LLMAPIError(LLMError):
    """LLM API call failed."""
    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out."""
    pass


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""
    pass


@dataclass
class EnrichmentResult:
    """Result of content enrichment via LLM.

    Per design.md §3.2 output_contract.
    """
    summary_short: str  # max 200 chars
    summary_long: str  # max 2000 chars
    categories: List[str]  # AI-suggested
    technologies: List[str]  # detected from content
    difficulty_level: str  # beginner/intermediate/advanced
    estimated_time: str  # e.g., "2-4 hours"
    prerequisites: List[str]
    learning_outcomes: List[str]
    quality_signals: Dict[str, bool] = field(default_factory=dict)
    model_used: str = "gpt-4o"
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualitySignals:
    """Quality indicators for repository."""
    has_documentation: bool = False
    has_tests: bool = False
    has_ci: bool = False
    is_maintained: bool = False


# Prompt template for enrichment (design.md §3.2)
ENRICHMENT_PROMPT = """You are a technical content analyst specializing in developer education. Analyze the following repository data and generate comprehensive enrichment metadata.

Repository Information:
---
Title: {title}
Description: {description}
README Content (excerpt):
{readme_excerpt}
---

Technologies detected: {technologies}
Categories: {categories}
Primary Language: {language}
Stars: {stars}
Last Commit: {last_commit_date}
Has Tests: {has_tests}
Has CI: {has_ci}

Generate enrichment metadata. Respond with a valid JSON object:

{{
  "summary_short": "Concise summary in 200 characters or less",
  "summary_long": "Detailed summary explaining what this content covers, who it's for, and what learners will gain (max 2000 chars)",
  "categories": ["Refined list of 2-5 categories that best describe this content"],
  "technologies": ["Complete list of technologies, frameworks, libraries, and tools used"],
  "difficulty_level": "One of: beginner, intermediate, advanced",
  "estimated_time": "Estimated time to complete (e.g., '30 minutes', '2-4 hours', '1-2 days')",
  "prerequisites": ["List of knowledge, skills, or tools needed before starting"],
  "learning_outcomes": ["5-7 specific, measurable outcomes starting with action verbs like 'Build', 'Deploy', 'Configure', 'Understand'"],
  "quality_signals": {{
    "has_documentation": true/false (based on README quality and completeness),
    "has_tests": true/false,
    "has_ci": true/false,
    "is_maintained": true/false (based on commit activity and last update)
  }}
}}

IMPORTANT:
- summary_short must be ≤200 characters
- summary_long must be ≤2000 characters
- Be specific about technologies (include versions if known)
- Learning outcomes should be actionable and measurable
- Assess is_maintained based on whether last commit is within 6 months

Respond ONLY with the JSON object, no additional text."""


# Prompt template for metadata extraction
EXTRACTION_PROMPT = """You are a technical content analyst specialized in developer education content. Analyze the following GitHub repository README and extract comprehensive structured metadata.

README content:
---
{readme_content}
---

Repository metadata:
- Description: {description}
- Topics: {topics}
- Language: {language}
- Stars: {stars}

Extract the following information and respond with a valid JSON object. Provide BOTH English and Korean translations for title and description:

IMPORTANT: The README may be written in English, Korean, or a mix of both languages.
- If the README is in English: translate to Korean for title_kr and description_kr
- If the README is in Korean: translate to English for title and description, keep original Korean for title_kr and description_kr
- Always ensure title/description are in English and title_kr/description_kr are in Korean

{{
  "topic": "A brief topic summary in English (1-2 sentences describing the main theme)",
  "title": "A concise, descriptive title for this content in ENGLISH (max 100 chars) - translate if README is in Korean",
  "title_kr": "한국어 제목 (max 100 chars) - README가 영어인 경우 번역하여 제공",
  "description": "A clear summary in ENGLISH of what this content teaches (2-3 sentences) - translate if README is in Korean",
  "description_kr": "이 컨텐츠가 가르치는 내용에 대한 한국어 설명 (2-3 문장) - README가 영어인 경우 번역하여 제공",
  "content_type": "One of: workshop, tutorial, lab, sample, demo, course, article",
  "categories": ["List of relevant categories from: AI, Azure, DevOps, Web, Mobile, Data, Security, Cloud, IoT, Serverless, Containers, Kubernetes, Machine Learning, Databases, Copilot, Agent, Analytics"],
  "level": "One of: beginner, intermediate, advanced",
  "duration_minutes": estimated time to complete (integer, 0 if unknown),
  "technologies": ["List of specific technologies, frameworks, services, and tools used (e.g., Visual Studio Code, GitHub Copilot, Azure AI Search, Python, Terraform, Bicep)"],
  "prerequisites": ["List of prerequisites and requirements needed to complete this content"],
  "learning_objectives": ["List of 3-7 specific, actionable things users will learn or be able to do after completing this content"],
  "lab_modules": ["List of lab exercises, modules, or sections if this is a hands-on lab/workshop (leave empty if not applicable)"]
}}

IMPORTANT:
- Be specific and detailed in technologies (include version numbers if mentioned)
- Extract actual lab module names if present in the README
- Categories should reflect the main focus areas (select 2-5 relevant categories)
- Korean translations should be natural and professional, not machine-translated style
- For learning_objectives, use action verbs like "Use", "Build", "Deploy", "Configure", "Understand"

Respond ONLY with the JSON object, no additional text."""


class LLMService:
    """Service for LLM-based content analysis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        """
        Initialize LLM service.

        Args:
            api_key: Azure OpenAI API key
            endpoint: Azure OpenAI endpoint URL
            deployment: Deployment/model name
            api_version: API version
        """
        self.api_key = api_key or getattr(settings, 'azure_openai_api_key', None)
        self.endpoint = endpoint or getattr(settings, 'azure_openai_endpoint', 'https://genai-thon-04.openai.azure.com/')
        self.deployment = deployment or getattr(settings, 'azure_openai_deployment', 'gpt-5.2')
        self.api_version = api_version or getattr(settings, 'azure_openai_api_version', '2025-04-01-preview')
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if LLM is properly configured."""
        return bool(self.api_key and self.endpoint)

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_url(self) -> str:
        """Build Azure OpenAI API URL."""
        base = self.endpoint.rstrip('/')
        return f"{base}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"

    async def extract_metadata(
        self,
        readme_content: str,
        repo_description: Optional[str] = None,
        repo_topics: Optional[List[str]] = None,
        repo_language: Optional[str] = None,
        repo_stars: int = 0,
    ) -> AnalysisResult:
        """
        Extract structured metadata from README content using LLM.

        Args:
            readme_content: The README content to analyze
            repo_description: Repository description
            repo_topics: Repository topics
            repo_language: Primary programming language
            repo_stars: Star count

        Returns:
            AnalysisResult with extracted metadata

        Raises:
            LLMConfigError: If LLM is not configured
            LLMAPIError: If API call fails
        """
        if not self.is_configured:
            logger.warning("LLM not configured, using fallback extraction")
            return self._fallback_extraction(
                readme_content,
                repo_description,
                repo_topics,
                repo_language,
            )

        # Truncate README if too long (keep first ~8000 chars)
        max_content_length = 8000
        if len(readme_content) > max_content_length:
            readme_content = readme_content[:max_content_length] + "\n\n[Content truncated...]"

        # Build prompt
        prompt = EXTRACTION_PROMPT.format(
            readme_content=readme_content,
            description=repo_description or "N/A",
            topics=", ".join(repo_topics) if repo_topics else "None",
            language=repo_language or "Not specified",
            stars=repo_stars,
        )

        try:
            client = await self.get_client()

            response = await client.post(
                self._build_url(),
                headers={
                    "Content-Type": "application/json",
                    "api-key": self.api_key,
                },
                json={
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,  # Low temperature for consistent extraction
                    "max_completion_tokens": 2000,  # GPT-5.2 uses max_completion_tokens instead of max_tokens
                },
            )

            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                raise LLMAPIError(f"LLM API returned {response.status_code}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON response
            return self._parse_llm_response(content)

        except httpx.RequestError as e:
            logger.error(f"LLM request error: {e}")
            raise LLMAPIError(f"Failed to connect to LLM: {e}")
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # Fall back to basic extraction
            return self._fallback_extraction(
                readme_content,
                repo_description,
                repo_topics,
                repo_language,
            )

    def _parse_llm_response(self, content: str) -> AnalysisResult:
        """
        Parse LLM response into AnalysisResult.

        Args:
            content: Raw LLM response content

        Returns:
            AnalysisResult
        """
        # Try to extract JSON from response
        content = content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            data = json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON: {e}")
            raise LLMAPIError(f"Invalid JSON response from LLM: {e}")

        return AnalysisResult(
            title=data.get("title", "Untitled"),
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
            raw_metadata=data,
        )

    def _fallback_extraction(
        self,
        readme_content: str,
        description: Optional[str] = None,
        topics: Optional[List[str]] = None,
        language: Optional[str] = None,
    ) -> AnalysisResult:
        """
        Basic metadata extraction without LLM.

        Used when LLM is not configured or fails.
        """
        # Extract title from first heading or use description
        title = "Untitled Content"
        lines = readme_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                title = line[2:].strip()
                break

        # Map topics to categories
        category_mapping = {
            "azure": "Azure",
            "python": "Python",
            "javascript": "Web",
            "typescript": "Web",
            "ai": "AI",
            "machine-learning": "Machine Learning",
            "ml": "Machine Learning",
            "docker": "Containers",
            "kubernetes": "Kubernetes",
            "k8s": "Kubernetes",
            "serverless": "Serverless",
            "functions": "Serverless",
            "devops": "DevOps",
            "iot": "IoT",
            "security": "Security",
            "copilot": "Copilot",
            "agent": "Agent",
            "analytics": "Analytics",
        }

        categories = set()
        if topics:
            for topic in topics:
                topic_lower = topic.lower()
                if topic_lower in category_mapping:
                    categories.add(category_mapping[topic_lower])

        # Use language as technology
        technologies = []
        if language:
            technologies.append(language)

        return AnalysisResult(
            title=title[:100],  # Max 100 chars
            title_kr=None,  # No Korean translation in fallback
            description=description,
            description_kr=None,
            topic=description,  # Use description as topic in fallback
            content_type="sample",  # Default to sample
            categories=list(categories) or ["Other"],
            level="intermediate",  # Default
            duration_minutes=None,
            technologies=technologies,
            prerequisites=[],
            learning_objectives=[],
            lab_modules=[],
        )

    async def enrich_content(
        self,
        title: str,
        description: str,
        readme_excerpt: str,
        technologies: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        language: Optional[str] = None,
        stars: int = 0,
        last_commit_date: Optional[str] = None,
        has_tests: bool = False,
        has_ci: bool = False,
    ) -> EnrichmentResult:
        """
        Generate enrichment metadata for content using LLM.

        Per design.md §3.2 output_contract.

        Args:
            title: Content title
            description: Content description
            readme_excerpt: Excerpt from README (first ~4000 chars)
            technologies: Detected technologies
            categories: Initial categories
            language: Primary programming language
            stars: GitHub star count
            last_commit_date: Date of last commit
            has_tests: Whether repo has tests
            has_ci: Whether repo has CI configuration

        Returns:
            EnrichmentResult with AI-generated enrichment

        Raises:
            LLMConfigError: If LLM is not configured
            LLMAPIError: If API call fails
            LLMTimeoutError: If request times out
            LLMRateLimitError: If rate limited
        """
        if not self.is_configured:
            logger.warning("LLM not configured, using fallback enrichment")
            return self._fallback_enrichment(
                title, description, technologies, categories
            )

        # Truncate README excerpt if needed
        max_excerpt_length = 4000
        if len(readme_excerpt) > max_excerpt_length:
            readme_excerpt = readme_excerpt[:max_excerpt_length] + "\n\n[Content truncated...]"

        # Build prompt
        prompt = ENRICHMENT_PROMPT.format(
            title=title,
            description=description or "N/A",
            readme_excerpt=readme_excerpt,
            technologies=", ".join(technologies) if technologies else "None detected",
            categories=", ".join(categories) if categories else "Uncategorized",
            language=language or "Not specified",
            stars=stars,
            last_commit_date=last_commit_date or "Unknown",
            has_tests=str(has_tests).lower(),
            has_ci=str(has_ci).lower(),
        )

        try:
            client = await self.get_client()

            response = await client.post(
                self._build_url(),
                headers={
                    "Content-Type": "application/json",
                    "api-key": self.api_key,
                },
                json={
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_completion_tokens": 3000,
                },
            )

            # Handle rate limiting
            if response.status_code == 429:
                logger.warning("LLM rate limit exceeded")
                raise LLMRateLimitError("Rate limit exceeded")

            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                raise LLMAPIError(f"LLM API returned {response.status_code}")

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON response
            return self._parse_enrichment_response(content)

        except httpx.TimeoutException as e:
            logger.error(f"LLM timeout: {e}")
            raise LLMTimeoutError(f"LLM request timed out: {e}")
        except httpx.RequestError as e:
            logger.error(f"LLM request error: {e}")
            raise LLMAPIError(f"Failed to connect to LLM: {e}")

    def _parse_enrichment_response(self, content: str) -> EnrichmentResult:
        """
        Parse LLM response into EnrichmentResult.

        Args:
            content: Raw LLM response content

        Returns:
            EnrichmentResult
        """
        # Clean up response
        content = content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            data = json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse enrichment JSON: {e}")
            raise LLMAPIError(f"Invalid JSON response from LLM: {e}")

        # Extract quality signals
        quality_signals = data.get("quality_signals", {})
        if not isinstance(quality_signals, dict):
            quality_signals = {}

        return EnrichmentResult(
            summary_short=data.get("summary_short", "")[:200],  # Enforce limit
            summary_long=data.get("summary_long", "")[:2000],  # Enforce limit
            categories=data.get("categories", []),
            technologies=data.get("technologies", []),
            difficulty_level=data.get("difficulty_level", "intermediate"),
            estimated_time=data.get("estimated_time", "Unknown"),
            prerequisites=data.get("prerequisites", []),
            learning_outcomes=data.get("learning_outcomes", []),
            quality_signals={
                "has_documentation": quality_signals.get("has_documentation", False),
                "has_tests": quality_signals.get("has_tests", False),
                "has_ci": quality_signals.get("has_ci", False),
                "is_maintained": quality_signals.get("is_maintained", False),
            },
            model_used=self.deployment,
            raw_response=data,
        )

    def _fallback_enrichment(
        self,
        title: str,
        description: str,
        technologies: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
    ) -> EnrichmentResult:
        """
        Basic enrichment without LLM.

        Used when LLM is not configured or fails.
        """
        # Create basic summary from description
        summary_short = description[:200] if description else title[:200]
        summary_long = description or title

        return EnrichmentResult(
            summary_short=summary_short,
            summary_long=summary_long,
            categories=categories or ["Other"],
            technologies=technologies or [],
            difficulty_level="intermediate",
            estimated_time="Unknown",
            prerequisites=[],
            learning_outcomes=[],
            quality_signals={
                "has_documentation": False,
                "has_tests": False,
                "has_ci": False,
                "is_maintained": False,
            },
            model_used="fallback",
            raw_response={},
        )

    async def generate_embedding(
        self,
        text: str,
        model: str = "text-embedding-3-small",
    ) -> List[float]:
        """
        Generate embedding vector for text content.

        Per tasks.md T402: Embedding generation for search indexing.

        Args:
            text: Text to embed (concatenated title + description + summary)
            model: Embedding model to use (default: text-embedding-3-small)

        Returns:
            1536-dimension float vector (text-embedding-3-small default)

        Raises:
            LLMConfigError: If service not configured
            LLMAPIError: If API call fails
            LLMTimeoutError: If request times out
        """
        if not self.is_configured:
            raise LLMConfigError("Azure OpenAI is not configured (missing API key)")

        # Truncate text to avoid token limits (text-embedding-3-small has 8191 token limit)
        # Roughly 4 chars per token, so ~32000 chars max
        truncated_text = text[:30000] if len(text) > 30000 else text

        # Build embedding API URL
        # Azure OpenAI embedding endpoint format
        embedding_deployment = getattr(settings, 'azure_openai_embedding_deployment', 'text-embedding-3-small')
        url = f"{self.endpoint.rstrip('/')}/openai/deployments/{embedding_deployment}/embeddings?api-version={self.api_version}"

        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }

        payload = {
            "input": truncated_text,
        }

        try:
            client = await self.get_client()
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 429:
                raise LLMRateLimitError("Embedding rate limit exceeded")

            if response.status_code != 200:
                raise LLMAPIError(f"Embedding API error: {response.status_code} - {response.text}")

            result = response.json()
            embedding = result.get("data", [{}])[0].get("embedding", [])

            if len(embedding) != 1536:
                logger.warning(f"Unexpected embedding dimension: {len(embedding)} (expected 1536)")

            return embedding

        except httpx.TimeoutException:
            raise LLMTimeoutError("Embedding request timed out")
        except httpx.RequestError as e:
            raise LLMAPIError(f"Embedding request failed: {e}")

    def generate_embedding_text(
        self,
        title: str,
        description: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> str:
        """
        Concatenate fields for embedding generation.

        Args:
            title: Content title
            description: Content description
            summary: Content summary (from enrichment)

        Returns:
            Concatenated text for embedding
        """
        parts = [title]
        if description:
            parts.append(description)
        if summary:
            parts.append(summary)
        return " ".join(parts)

    async def translate_content(
        self,
        title: str,
        description: str,
        summary: Optional[str] = None,
        prerequisites: Optional[List[str]] = None,
        learning_outcomes: Optional[List[str]] = None,
        target_locale: str = "ko-KR",
    ) -> "TranslationResult":
        """
        Translate content fields to target locale using Azure OpenAI.

        Per design.md §3.3 Localization Pipeline.

        Args:
            title: Content title
            description: Content description
            summary: Content summary (optional)
            prerequisites: List of prerequisites (optional)
            learning_outcomes: List of learning outcomes (optional)
            target_locale: Target locale (default: ko-KR)

        Returns:
            TranslationResult with translated fields
        """
        if not self.is_configured:
            raise LLMConfigError("Azure OpenAI not configured")

        prompt = TRANSLATION_PROMPT.format(
            title=title,
            description=description,
            summary=summary or "(No summary provided)",
            prerequisites=json.dumps(prerequisites or [], ensure_ascii=False),
            learning_outcomes=json.dumps(learning_outcomes or [], ensure_ascii=False),
            target_locale=target_locale,
        )

        try:
            client = await self.get_client()
            response = await client.post(
                self._build_url(),
                headers=self._build_headers(),
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional translator specializing in technical content. Translate the given content to Korean while maintaining technical accuracy and natural Korean expression."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )

            if response.status_code == 429:
                raise LLMRateLimitError("Translation rate limit exceeded")

            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            return self._parse_translation_response(content)

        except httpx.TimeoutException:
            raise LLMTimeoutError("Translation request timed out")
        except httpx.HTTPStatusError as e:
            raise LLMAPIError(f"Translation API error: {e.response.status_code}")
        except (KeyError, IndexError) as e:
            raise LLMAPIError(f"Invalid translation response: {e}")

    def _parse_translation_response(self, content: str) -> "TranslationResult":
        """Parse translation response from LLM."""
        try:
            # Clean markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines)

            data = json.loads(content)

            return TranslationResult(
                title_kr=data.get("title_kr", ""),
                description_kr=data.get("description_kr", ""),
                summary_kr=data.get("summary_kr"),
                prerequisites_kr=data.get("prerequisites_kr", []),
                learning_outcomes_kr=data.get("learning_outcomes_kr", []),
                model_used=self.deployment,
                raw_response=data,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse translation response: {e}")
            logger.error(f"Response content: {content[:500]}")
            raise LLMAPIError(f"Invalid JSON in translation response: {e}")


@dataclass
class TranslationResult:
    """Result of content translation via LLM.

    Per design.md §3.3 output_contract.
    """
    title_kr: str
    description_kr: str
    summary_kr: Optional[str] = None
    prerequisites_kr: List[str] = field(default_factory=list)
    learning_outcomes_kr: List[str] = field(default_factory=list)
    model_used: str = "gpt-4o"
    raw_response: Dict[str, Any] = field(default_factory=dict)


# Translation prompt template (design.md §3.3)
TRANSLATION_PROMPT = """Translate the following technical content to Korean ({target_locale}). Maintain technical accuracy and use natural Korean expressions appropriate for developer documentation.

Content to translate:
---
Title: {title}
Description: {description}
Summary: {summary}
Prerequisites: {prerequisites}
Learning Outcomes: {learning_outcomes}
---

Respond with a valid JSON object:

{{
  "title_kr": "한국어 제목",
  "description_kr": "한국어 설명",
  "summary_kr": "한국어 요약 (if summary was provided, otherwise null)",
  "prerequisites_kr": ["한국어 사전 요구사항 목록"],
  "learning_outcomes_kr": ["한국어 학습 성과 목록"]
}}

IMPORTANT:
- Use professional Korean appropriate for technical documentation
- Preserve technical terms in English when commonly used (e.g., API, Docker, Kubernetes)
- Keep code examples and command names in English
- Use formal language style (존댓말)
- Maintain the same number of items in lists

Respond ONLY with the JSON object, no additional text."""


# Singleton instance
_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get the LLM service singleton."""
    global _service
    if _service is None:
        _service = LLMService()
    return _service
