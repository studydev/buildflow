"""AI Assistant Service for content discovery.

Per design.md §8: AI Assistant Integration
Per tasks.md T700: Create Assistant Service

Capabilities:
- Answer questions using indexed content (RAG)
- Recommend content based on query and context
- Explain how to use selected content items
- External search fallback when internal results are insufficient

Constraints:
- MUST respect visibility boundaries
- MUST cite sources for all recommendations
- MUST NOT fabricate content references
- MUST prefer internal indexed knowledge
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx

from app.config import get_settings
from app.services.search_service import SearchFilters, SearchResult, SearchService
from app.services.youtube_search_service import (
    YouTubeSearchService,
    get_youtube_search_service,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class Citation:
    """Content citation in assistant response."""

    content_id: str
    title: str
    relevance: float
    description: Optional[str] = None
    description_kr: Optional[str] = None
    url: Optional[str] = None
    title_kr: Optional[str] = None
    source_type: str = "github"  # github or youtube
    thumbnail_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "content_id": self.content_id,
            "title": self.title,
            "title_kr": self.title_kr,
            "relevance": self.relevance,
            "description": self.description,
            "description_kr": self.description_kr,
            "url": self.url,
            "source_type": self.source_type,
            "thumbnail_url": self.thumbnail_url,
        }


@dataclass
class SuggestedContent:
    """Suggested content item from assistant."""

    content_id: str
    title: str
    description: Optional[str]
    relevance: float
    reason: Optional[str] = None  # Why it was suggested
    url: Optional[str] = None  # GitHub repo URL or YouTube URL
    title_kr: Optional[str] = None
    description_kr: Optional[str] = None
    source_type: str = "github"  # github or youtube
    thumbnail_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "content_id": self.content_id,
            "title": self.title,
            "title_kr": self.title_kr,
            "description": self.description,
            "description_kr": self.description_kr,
            "relevance": self.relevance,
            "reason": self.reason,
            "url": self.url,
            "source_type": self.source_type,
            "thumbnail_url": self.thumbnail_url,
        }


@dataclass
class ExternalResult:
    """External search result (fallback)."""

    title: str
    url: str
    snippet: str
    source_type: str = "external"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source_type": self.source_type,
            "disclaimer": "External content not verified by BuildFlow",
        }


@dataclass
class ConversationMessage:
    """Message in conversation history."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AssistantResponse:
    """Complete assistant response."""

    response: str
    citations: List[Citation] = field(default_factory=list)
    suggested_content: List[SuggestedContent] = field(default_factory=list)
    external_results: List[ExternalResult] = field(default_factory=list)
    conversation_id: str = ""
    used_external_search: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return {
            "response": self.response,
            "citations": [c.to_dict() for c in self.citations],
            "suggested_content": [s.to_dict() for s in self.suggested_content],
            "external_results": [e.to_dict() for e in self.external_results],
            "conversation_id": self.conversation_id,
            "used_external_search": self.used_external_search,
        }


@dataclass
class ChatContext:
    """Context for chat request."""

    current_content_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    visibility_level: str = "public"  # public, internal, private


# =============================================================================
# Exception Classes
# =============================================================================


class AssistantError(Exception):
    """Base exception for assistant service errors."""
    pass


class AssistantConfigError(AssistantError):
    """Assistant configuration error."""
    pass


class AssistantAPIError(AssistantError):
    """Assistant API call failed."""
    pass


class AssistantRateLimitError(AssistantError):
    """Rate limit exceeded for external search."""
    pass


# =============================================================================
# Prompt Templates
# =============================================================================


SYSTEM_PROMPT = """You are NexusSkill Assistant, an AI helper for discovering and understanding Azure learning content.

Your capabilities:
1. Answer questions about Azure, cloud development, and DevOps using the knowledge base
2. Recommend relevant GitHub repositories, YouTube tutorials, and learning resources
3. Explain how to use specific content items
4. Suggest learning paths based on user's skill level

KNOWLEDGE BASE:
- GitHub Repositories: Curated repos with workshops, tutorials, and sample code
- YouTube Videos: Curated videos from Microsoft Developer and other channels

IMPORTANT RULES:
- ALWAYS base your answers on the provided context from the knowledge base
- ALWAYS cite your sources using [Source: content_id] format
- For YouTube content, mention the video title and channel name
- If you cannot find relevant information in the context, clearly say so
- NEVER fabricate or invent content references
- Be concise and actionable in your responses
- Use Korean if the user writes in Korean, English otherwise

YOUTUBE RECOMMENDATION PRIORITY:
- When the user wants to learn visually, watch tutorials, or prefers video content, PRIORITIZE YouTube videos
- Even if YouTube content has lower search scores, actively recommend videos when they are relevant
- Explicitly mention that YouTube videos provide visual/hands-on learning experiences
- For topics like "AI Agents", "MCP", "GitHub Copilot", recommend relevant YouTube tutorials first

Current context about user:
- Visibility level: {visibility_level}
- Current content (if any): {current_content}
"""


RAG_PROMPT = """Based on the following knowledge base context, answer the user's question.

KNOWLEDGE BASE CONTEXT:
{context}

USER QUESTION:
{question}

Remember to:
1. Use ONLY information from the context above
2. Cite sources using [Source: content_id] format
3. If context is insufficient, acknowledge limitations
4. At the end, provide recommendations in this JSON format:

[RECOMMENDATIONS]
```json
{{
  "recommendations": [
    {{"content_id": "id", "reason": "2-3 sentence explanation of why this is relevant"}}
  ]
}}
```

Only include content items that are truly relevant to the user's question (0-5 items).
Explain WHY each recommendation helps the user.
"""


RECOMMEND_PROMPT = """Based on the user's query and the following search results, recommend the most relevant content.

SEARCH RESULTS:
{search_results}

USER QUERY:
{query}

USER CONTEXT:
- Skill level preference: {skill_level}
- Technologies of interest: {technologies}

Provide recommendations with brief explanations of why each is relevant.
"""


# =============================================================================
# Assistant Service
# =============================================================================


class AssistantService:
    """AI Assistant for content discovery using RAG.

    Per design.md §8: Answers questions, recommends repos, explains usage.
    Uses Azure AI Search for retrieval and Azure OpenAI for generation.
    """

    # External search configuration per design.md
    EXTERNAL_RATE_LIMIT_PER_HOUR = 10
    MIN_RELEVANCE_THRESHOLD = 0.5
    MIN_INTERNAL_RESULTS = 3

    # Trusted domains for external search
    TRUSTED_DOMAINS = [
        "docs.microsoft.com",
        "learn.microsoft.com",
        "github.com",
        "dev.to",
        "medium.com",
        "stackoverflow.com",
    ]

    def __init__(
        self,
        search_service: Optional[SearchService] = None,
        youtube_search_service: Optional[YouTubeSearchService] = None,
        openai_endpoint: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        openai_deployment: Optional[str] = None,
    ):
        """
        Initialize assistant service.

        Args:
            search_service: SearchService instance for GitHub content (buildflow-content)
            youtube_search_service: YouTubeSearchService instance for YouTube content (buildflow-youtube)
            openai_endpoint: Azure OpenAI endpoint
            openai_api_key: Azure OpenAI API key
            openai_deployment: Azure OpenAI deployment name
        """
        self.search_service = search_service or SearchService()
        self.youtube_search_service = youtube_search_service or get_youtube_search_service()
        self.openai_endpoint = openai_endpoint or settings.azure_openai_endpoint
        self.openai_api_key = openai_api_key or settings.azure_openai_api_key
        self.openai_deployment = openai_deployment or settings.azure_openai_deployment
        self.api_version = settings.azure_openai_api_version

        # In-memory conversation storage (would use Cosmos in production)
        self._conversations: Dict[str, List[ConversationMessage]] = {}

        # Rate limiting for external search
        self._external_search_usage: Dict[str, List[datetime]] = {}

        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if assistant is configured."""
        return bool(
            self.openai_endpoint
            and self.openai_api_key
            and self.search_service.is_configured
        )

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # =========================================================================
    # Main Chat Interface
    # =========================================================================

    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[ChatContext] = None,
    ) -> AssistantResponse:
        """
        Process user message and generate response.

        Per design.md POST /api/v1/assistant/chat specification.

        Args:
            message: User's message
            conversation_id: Optional conversation ID for history
            context: Optional context (current content, filters, etc.)

        Returns:
            AssistantResponse with answer, citations, and suggestions
        """
        if not self.is_configured:
            raise AssistantConfigError("Assistant service is not configured")

        context = context or ChatContext()

        # Get or create conversation
        if conversation_id and conversation_id in self._conversations:
            conversation = self._conversations[conversation_id]
        else:
            conversation_id = str(uuid4())
            conversation = []
            self._conversations[conversation_id] = conversation

        # Add user message to history
        conversation.append(ConversationMessage(role="user", content=message))

        try:
            # Step 1: Search for relevant content
            search_results = await self._retrieve_context(
                query=message,
                context=context,
            )

            # Step 2: Check if we need external fallback
            relevant_results = [
                r for r in search_results if r.score >= self.MIN_RELEVANCE_THRESHOLD
            ]

            external_results: List[ExternalResult] = []
            used_external = False

            if len(relevant_results) < self.MIN_INTERNAL_RESULTS:
                # Try external search fallback
                if self._can_use_external_search(context.user_id):
                    external_results = await self._external_search_fallback(
                        query=message,
                        user_id=context.user_id,
                    )
                    used_external = bool(external_results)

            # Step 3: Generate response using LLM (includes recommendation reasons)
            response_text, citations, reasons = await self._generate_response(
                message=message,
                search_results=search_results,
                conversation=conversation,
                context=context,
            )

            # Step 4: Extract suggested content with reasons (0-5 items with dynamic threshold)
            suggested = self._extract_suggestions(search_results, reasons=reasons)

            # Step 5: Build response
            response = AssistantResponse(
                response=response_text,
                citations=citations,
                suggested_content=suggested,
                external_results=external_results,
                conversation_id=conversation_id,
                used_external_search=used_external,
            )

            # Add assistant response to history
            conversation.append(
                ConversationMessage(role="assistant", content=response_text)
            )

            # Limit conversation history to 10 messages (5 exchanges)
            if len(conversation) > 10:
                conversation[:] = conversation[-10:]

            return response

        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise AssistantAPIError(f"Failed to process chat: {e}")

    # =========================================================================
    # RAG Retrieval
    # =========================================================================

    async def _retrieve_context(
        self,
        query: str,
        context: ChatContext,
        limit: int = 10,
    ) -> List[SearchResult]:
        """
        Retrieve relevant content from both GitHub and YouTube search indexes.

        Performs ensemble search across:
        - buildflow-content (GitHub repositories)
        - buildflow-youtube (YouTube videos)

        Args:
            query: Search query
            context: Chat context with visibility settings
            limit: Maximum results per index

        Returns:
            Combined list of search results from both indexes
        """
        # Build filters based on context for GitHub content
        filters = SearchFilters()

        # Apply visibility filter
        if context.visibility_level == "public":
            filters.visibility = "public"
        # internal/private users can see internal content

        # Apply any additional filters from context
        if context.filters:
            if "difficulty" in context.filters:
                filters.difficulty_level = context.filters["difficulty"]
            if "categories" in context.filters:
                filters.categories = context.filters["categories"]
            if "technologies" in context.filters:
                filters.technologies = context.filters["technologies"]

        # Perform parallel searches on both indexes
        import asyncio

        # GitHub content search
        github_task = self.search_service.hybrid_search(
            query=query,
            filters=filters,
            limit=limit,
        )

        # YouTube content search (build filters)
        youtube_filters = {}
        if context.filters:
            if "categories" in context.filters:
                youtube_filters["category"] = context.filters["categories"][0] if context.filters["categories"] else None
            if "level" in context.filters:
                youtube_filters["level"] = context.filters["level"]

        logger.info(f"[Ensemble Search] Query: {query}")
        logger.info(f"[Ensemble Search] YouTube service configured: {self.youtube_search_service.is_configured}")

        # YouTube uses keyword-only search (no vector) for better score comparability
        youtube_task = self.youtube_search_service.search(
            query=query,
            filters=youtube_filters if youtube_filters else None,
            top=limit,
            use_vector=False,  # Keyword search only for consistent scoring
        )

        # Wait for both searches
        github_results, youtube_results = await asyncio.gather(
            github_task,
            youtube_task,
            return_exceptions=True,
        )

        logger.info(f"[Ensemble Search] GitHub results type: {type(github_results)}")
        logger.info(f"[Ensemble Search] YouTube results type: {type(youtube_results)}")

        # Combine results
        combined_results: List[SearchResult] = []

        # Add GitHub results
        if not isinstance(github_results, Exception):
            logger.info(f"[Ensemble Search] GitHub found {len(github_results.items)} results")
            combined_results.extend(github_results.items)
        else:
            logger.warning(f"GitHub search failed: {github_results}")

        # Convert YouTube results to SearchResult format
        if not isinstance(youtube_results, Exception):
            logger.info(f"[Ensemble Search] YouTube found {len(youtube_results.results)} results")
            for yt_result in youtube_results.results:
                # Convert YouTubeSearchResult to SearchResult
                search_result = SearchResult(
                    id=yt_result.id,
                    title=yt_result.title,
                    title_kr=yt_result.title_kr,
                    description=yt_result.description,
                    description_kr=yt_result.description_kr,
                    summary=None,  # YouTube doesn't have summary in search result
                    summary_kr=None,
                    categories=yt_result.categories,
                    technologies=yt_result.technologies,
                    difficulty_level=yt_result.level,
                    score=yt_result.score,
                    source_type="youtube",  # Mark as YouTube content
                    source_url=yt_result.source_url,
                    thumbnail_url=yt_result.thumbnail_url,
                    channel_name=yt_result.channel_name,
                    duration_minutes=yt_result.duration_minutes,
                    view_count=yt_result.view_count,
                )
                combined_results.append(search_result)
        else:
            logger.warning(f"YouTube search failed: {youtube_results}")

        # Sort by score (descending) and limit total results
        combined_results.sort(key=lambda x: x.score, reverse=True)
        return combined_results[:limit * 2]  # Return up to 2x limit for ensemble

    def _format_context_for_llm(
        self,
        search_results: List[SearchResult],
    ) -> str:
        """Format search results as context for LLM.

        Includes both GitHub repositories and YouTube videos.
        """
        if not search_results:
            return "No relevant content found in the knowledge base."

        context_parts = []
        for i, result in enumerate(search_results, 1):
            # Base info
            source_type = getattr(result, 'source_type', 'github')
            source_label = "📺 YouTube Video" if source_type == "youtube" else "📁 GitHub Repository"

            part = f"""
[{i}] {source_label}
Content ID: {result.id}
Title: {result.title}
"""
            # Add YouTube-specific info
            if source_type == "youtube":
                channel = getattr(result, 'channel_name', None)
                duration = getattr(result, 'duration_minutes', None)
                views = getattr(result, 'view_count', 0)
                if channel:
                    part += f"Channel: {channel}\n"
                if duration:
                    part += f"Duration: {duration} minutes\n"
                if views:
                    part += f"Views: {views:,}\n"
                part += f"URL: {result.source_url or 'N/A'}\n"

            # Common info
            part += f"""Description: {result.description or 'N/A'}
Summary: {result.summary or 'N/A'}
Categories: {', '.join(result.categories) if result.categories else 'N/A'}
Technologies: {', '.join(result.technologies) if result.technologies else 'N/A'}
Difficulty: {result.difficulty_level or 'N/A'}
Relevance Score: {result.score:.2f}
"""
            context_parts.append(part.strip())

        return "\n\n".join(context_parts)

    # =========================================================================
    # Response Generation
    # =========================================================================

    async def _generate_response(
        self,
        message: str,
        search_results: List[SearchResult],
        conversation: List[ConversationMessage],
        context: ChatContext,
    ) -> tuple[str, List[Citation], Dict[str, str]]:
        """
        Generate response using Azure OpenAI.

        Args:
            message: User's message
            search_results: Retrieved content
            conversation: Conversation history
            context: Chat context

        Returns:
            Tuple of (response text, citations, recommendation reasons)
        """
        # Prepare current content description
        current_content_desc = "None"
        if context.current_content_id:
            # Find in search results
            for r in search_results:
                if r.id == context.current_content_id:
                    current_content_desc = f"{r.title} ({r.id})"
                    break

        # Build system message
        system_message = SYSTEM_PROMPT.format(
            visibility_level=context.visibility_level,
            current_content=current_content_desc,
        )

        # Build RAG prompt
        knowledge_context = self._format_context_for_llm(search_results)
        rag_prompt = RAG_PROMPT.format(
            context=knowledge_context,
            question=message,
        )

        # Build messages for API
        messages = [
            {"role": "system", "content": system_message},
        ]

        # Add conversation history (last 6 messages for context)
        for msg in conversation[-6:]:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Add RAG-enhanced current message
        messages.append({
            "role": "user",
            "content": rag_prompt,
        })

        # Call Azure OpenAI
        response_text = await self._call_openai(messages)

        # Extract citations from response
        citations = self._extract_citations(response_text, search_results)

        # Extract recommendation reasons from response
        reasons = self._extract_recommendation_reasons(response_text)

        # Clean response text (remove the JSON block)
        clean_response = self._clean_response_text(response_text)

        return clean_response, citations, reasons

    async def _call_openai(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """Call Azure OpenAI API."""
        url = (
            f"{self.openai_endpoint}openai/deployments/{self.openai_deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )

        payload = {
            "messages": messages,
            "max_completion_tokens": 1500,
        }

        headers = {
            "Content-Type": "application/json",
            "api-key": self.openai_api_key or "",
        }

        try:
            client = await self.get_client()
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                raise AssistantAPIError(f"OpenAI API error: {response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"OpenAI request failed: {e}")
            raise AssistantAPIError(f"OpenAI request failed: {e}")

    def _extract_citations(
        self,
        response_text: str,
        search_results: List[SearchResult],
    ) -> List[Citation]:
        """Extract citations from response text."""
        citations = []
        seen_ids = set()

        # Look for [Source: content_id] patterns
        import re
        pattern = r'\[Source:\s*([^\]]+)\]'
        matches = re.findall(pattern, response_text)

        for match in matches:
            content_id = match.strip()
            if content_id in seen_ids:
                continue
            seen_ids.add(content_id)

            # Find in search results
            for result in search_results:
                if result.id == content_id:
                    citations.append(Citation(
                        content_id=result.id,
                        title=result.title,
                        title_kr=result.title_kr,
                        relevance=result.score,
                        description=result.description,
                        description_kr=result.description_kr,
                        url=result.source_url,
                        source_type=getattr(result, 'source_type', 'github'),
                        thumbnail_url=getattr(result, 'thumbnail_url', None),
                    ))
                    break

        # Also add top results mentioned even without explicit citation
        for result in search_results[:3]:
            if result.id not in seen_ids and result.score >= 0.7:
                # Check if title is mentioned
                if result.title.lower() in response_text.lower():
                    citations.append(Citation(
                        content_id=result.id,
                        title=result.title,
                        title_kr=result.title_kr,
                        relevance=result.score,
                        description=result.description,
                        description_kr=result.description_kr,
                        url=result.source_url,
                        source_type=getattr(result, 'source_type', 'github'),
                        thumbnail_url=getattr(result, 'thumbnail_url', None),
                    ))

        return citations

    def _extract_recommendation_reasons(
        self,
        response_text: str,
    ) -> Dict[str, str]:
        """
        Extract recommendation reasons from LLM response.

        Parses the JSON block in [RECOMMENDATIONS] section.

        Returns:
            Dict mapping content_id to reason text
        """
        import json
        import re

        reasons: Dict[str, str] = {}

        # Look for [RECOMMENDATIONS] section with JSON
        pattern = r'\[RECOMMENDATIONS\]\s*```json\s*(.*?)\s*```'
        match = re.search(pattern, response_text, re.DOTALL)

        if not match:
            # Try alternative pattern without code block
            pattern = r'\[RECOMMENDATIONS\]\s*(\{.*?\})'
            match = re.search(pattern, response_text, re.DOTALL)

        if match:
            try:
                json_str = match.group(1).strip()
                data = json.loads(json_str)
                recommendations = data.get("recommendations", [])
                for rec in recommendations:
                    content_id = rec.get("content_id")
                    reason = rec.get("reason")
                    if content_id and reason:
                        reasons[content_id] = reason
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse recommendation JSON: {e}")
            except Exception as e:
                logger.warning(f"Error extracting recommendations: {e}")

        return reasons

    def _clean_response_text(
        self,
        response_text: str,
    ) -> str:
        """
        Remove the [RECOMMENDATIONS] JSON block from response text.

        Returns clean text for display to user.
        """
        import re

        # Remove [RECOMMENDATIONS] section with JSON code block
        pattern = r'\n*\[RECOMMENDATIONS\]\s*```json\s*.*?```\s*'
        cleaned = re.sub(pattern, '', response_text, flags=re.DOTALL)

        # Remove alternative pattern
        pattern = r'\n*\[RECOMMENDATIONS\]\s*\{.*?\}\s*'
        cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)

        return cleaned.strip()

    def _calculate_dynamic_threshold(
        self,
        search_results: List[SearchResult],
    ) -> float:
        """
        Calculate dynamic relevance threshold based on score distribution.

        Strategy:
        - If top score is high (>=0.8), use stricter threshold
        - If scores are spread out, use adaptive threshold based on gap analysis
        - If all scores are low, use lower threshold to still provide some results
        """
        if not search_results:
            return 0.5

        scores = [r.score for r in search_results]
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)

        # High confidence results - use stricter threshold
        if max_score >= 0.8:
            return max(0.6, avg_score + 0.1)

        # Medium confidence - adaptive threshold
        if max_score >= 0.5:
            # Use 60% of max score as threshold
            return max(0.35, max_score * 0.6)

        # Low confidence - be more lenient to provide some results
        return max(0.2, max_score * 0.5)

    def _extract_suggestions(
        self,
        search_results: List[SearchResult],
        max_suggestions: int = 5,
        reasons: Optional[Dict[str, str]] = None,
    ) -> List[SuggestedContent]:
        """
        Extract content suggestions with dynamic threshold.

        Args:
            search_results: Search results to filter
            max_suggestions: Maximum number of suggestions (0-5)
            reasons: Optional dict mapping content_id to reason text

        Returns:
            List of suggested content (0-5 items)
        """
        if not search_results:
            return []

        # Calculate dynamic threshold
        threshold = self._calculate_dynamic_threshold(search_results)
        logger.debug(f"Dynamic threshold calculated: {threshold:.2f}")

        suggestions = []
        reasons = reasons or {}

        for result in search_results[:max_suggestions]:
            if result.score >= threshold:
                suggestions.append(SuggestedContent(
                    content_id=result.id,
                    title=result.title,
                    title_kr=result.title_kr,
                    description=result.description,
                    description_kr=result.description_kr,
                    relevance=result.score,
                    reason=reasons.get(result.id),
                    url=result.source_url,
                    source_type=getattr(result, 'source_type', 'github'),
                    thumbnail_url=getattr(result, 'thumbnail_url', None),
                ))

        return suggestions

    # =========================================================================
    # External Search Fallback
    # =========================================================================

    def _can_use_external_search(self, user_id: Optional[str]) -> bool:
        """Check if user can use external search (rate limiting)."""
        if not user_id:
            return False

        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Clean old entries
        if user_id in self._external_search_usage:
            self._external_search_usage[user_id] = [
                t for t in self._external_search_usage[user_id]
                if t > hour_ago
            ]

        usage_count = len(self._external_search_usage.get(user_id, []))
        return usage_count < self.EXTERNAL_RATE_LIMIT_PER_HOUR

    async def _external_search_fallback(
        self,
        query: str,
        user_id: Optional[str],
    ) -> List[ExternalResult]:
        """
        Perform external search via Bing Web Search API.

        Per design.md fallback_behavior specification.

        Args:
            query: Search query
            user_id: User ID for rate limiting

        Returns:
            List of external results (max 3)
        """
        # Record usage
        if user_id:
            if user_id not in self._external_search_usage:
                self._external_search_usage[user_id] = []
            self._external_search_usage[user_id].append(datetime.utcnow())

        logger.info(f"Performing external search fallback for: {query}")

        # For now, return empty results (Bing Search API integration would go here)
        # In production, this would call Azure Cognitive Services Bing Search API
        # and filter results to trusted domains

        # Placeholder for Bing Search API integration
        # bing_api_key = settings.bing_search_api_key
        # if not bing_api_key:
        #     return []

        # For demo, return placeholder indicating external search attempted
        return []

    # =========================================================================
    # Conversation Management
    # =========================================================================

    def get_conversation(
        self,
        conversation_id: str,
    ) -> Optional[List[ConversationMessage]]:
        """Get conversation history."""
        return self._conversations.get(conversation_id)

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear conversation history."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False

    # =========================================================================
    # Content-Specific Queries
    # =========================================================================

    async def explain_content(
        self,
        content_id: str,
        question: Optional[str] = None,
        context: Optional[ChatContext] = None,
    ) -> AssistantResponse:
        """
        Explain how to use a specific content item.

        Args:
            content_id: Content ID to explain
            question: Optional specific question about the content
            context: Chat context

        Returns:
            Explanation with suggestions
        """
        context = context or ChatContext(current_content_id=content_id)
        context.current_content_id = content_id

        # Build query
        if question:
            message = f"Regarding content {content_id}: {question}"
        else:
            message = f"Please explain how to use and get started with content {content_id}. What are the prerequisites and learning outcomes?"

        return await self.chat(
            message=message,
            context=context,
        )

    async def recommend(
        self,
        query: str,
        skill_level: Optional[str] = None,
        technologies: Optional[List[str]] = None,
        context: Optional[ChatContext] = None,
    ) -> AssistantResponse:
        """
        Get content recommendations based on query.

        Args:
            query: What the user wants to learn
            skill_level: beginner/intermediate/advanced
            technologies: Specific technologies of interest
            context: Chat context

        Returns:
            Recommendations with explanations
        """
        context = context or ChatContext()

        if context.filters is None:
            context.filters = {}

        if skill_level:
            context.filters["difficulty"] = skill_level
        if technologies:
            context.filters["technologies"] = technologies

        message = f"I want to learn: {query}"
        if skill_level:
            message += f" (skill level: {skill_level})"
        if technologies:
            message += f" (technologies: {', '.join(technologies)})"

        return await self.chat(
            message=message,
            context=context,
        )


# =============================================================================
# Singleton / Factory
# =============================================================================


_assistant_service: Optional[AssistantService] = None


def get_assistant_service() -> AssistantService:
    """Get singleton assistant service instance."""
    global _assistant_service
    if _assistant_service is None:
        _assistant_service = AssistantService()
    return _assistant_service
