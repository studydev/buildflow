"""Assistant API endpoints.

Per tasks.md T701: POST /api/v1/assistant/chat endpoint implementation.
Per design.md §8: AI Assistant Integration specification.

Provides:
- Chat with AI assistant using RAG
- Conversation history management
- Content explanations and recommendations
- Visibility enforcement per user level
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError
from app.dependencies import get_current_user_optional, get_current_user_required
from app.models.user import UserPublic
from app.schemas import APIResponse, Meta
from app.services.assistant_service import (
    AssistantService,
    AssistantError,
    AssistantConfigError,
    AssistantAPIError,
    ChatContext,
    get_assistant_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class ChatContextRequest(BaseModel):
    """Context for chat request."""
    
    current_content_id: Optional[str] = Field(
        None,
        description="ID of content currently being viewed",
    )
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Filters to apply (difficulty, categories, technologies)",
    )


class ChatRequest(BaseModel):
    """Chat request payload.
    
    Per design.md §8 Assistant API specification.
    """
    
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's message to the assistant",
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Optional conversation ID for continuing a conversation",
    )
    context: Optional[ChatContextRequest] = Field(
        None,
        description="Optional context for the request",
    )


class CitationResponse(BaseModel):
    """Citation in assistant response."""
    
    content_id: str
    title: str
    relevance: float
    snippet: Optional[str] = None
    url: Optional[str] = None


class SuggestedContentResponse(BaseModel):
    """Suggested content in response."""
    
    content_id: str
    title: str
    description: Optional[str] = None
    relevance: float
    reason: Optional[str] = None


class ExternalResultResponse(BaseModel):
    """External search result."""
    
    title: str
    url: str
    snippet: str
    source_type: str = "external"
    disclaimer: str = "External content not verified by BuildFlow"


class ChatResponseData(BaseModel):
    """Chat response data.
    
    Per design.md §8 response specification.
    """
    
    response: str = Field(..., description="Assistant's response")
    citations: List[CitationResponse] = Field(
        default_factory=list,
        description="Sources cited in the response",
    )
    suggested_content: List[SuggestedContentResponse] = Field(
        default_factory=list,
        description="Related content suggestions",
    )
    external_results: List[ExternalResultResponse] = Field(
        default_factory=list,
        description="External search results (if fallback used)",
    )
    conversation_id: str = Field(..., description="Conversation ID for continuation")
    used_external_search: bool = Field(
        False,
        description="Whether external search was used",
    )


class ExplainRequest(BaseModel):
    """Request to explain specific content."""
    
    content_id: str = Field(..., description="Content ID to explain")
    question: Optional[str] = Field(
        None,
        description="Specific question about the content",
    )


class RecommendRequest(BaseModel):
    """Request for recommendations."""
    
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="What the user wants to learn",
    )
    skill_level: Optional[str] = Field(
        None,
        description="User's skill level: beginner, intermediate, advanced",
    )
    technologies: Optional[List[str]] = Field(
        None,
        description="Technologies of interest",
    )


# =============================================================================
# Dependencies
# =============================================================================


async def get_assistant() -> AssistantService:
    """Get assistant service dependency."""
    return get_assistant_service()


def get_visibility_level(user: Optional[UserPublic]) -> str:
    """Determine visibility level based on user.
    
    Per design.md visibility_rules:
    - Anonymous users: Cannot use assistant (401)
    - Authenticated users: internal access
    - Contributors: private access (their own content)
    """
    if not user:
        return "public"
    if user.role == "admin":
        return "private"
    if user.role == "contributor":
        return "internal"
    return "public"


# =============================================================================
# Chat Endpoints
# =============================================================================


@router.post(
    "/chat",
    response_model=APIResponse[ChatResponseData],
    status_code=status.HTTP_200_OK,
    summary="Chat with AI assistant",
    description="""
    Send a message to the BuildFlow AI Assistant and receive an intelligent response.
    
    The assistant uses RAG (Retrieval-Augmented Generation) to answer questions
    based on indexed content. It can:
    
    - Answer questions about Azure, cloud development, and DevOps
    - Recommend relevant repositories and learning resources
    - Explain how to use specific content items
    - Suggest learning paths based on skill level
    
    **Visibility Rules**:
    - Authenticated users required (401 if not authenticated)
    - Response content filtered based on user's access level
    
    **Rate Limits**:
    - External search fallback: 10 per user per hour
    """,
    responses={
        401: {"description": "Authentication required"},
        503: {"description": "Assistant service unavailable"},
    },
)
async def chat(
    request: ChatRequest,
    user: UserPublic = Depends(get_current_user_required),
    assistant: AssistantService = Depends(get_assistant),
) -> APIResponse[ChatResponseData]:
    """Process chat message and return AI-generated response."""
    
    # Build chat context
    context = ChatContext(
        user_id=str(user.id) if hasattr(user, 'id') else None,
        visibility_level=get_visibility_level(user),
    )
    
    if request.context:
        context.current_content_id = request.context.current_content_id
        context.filters = request.context.filters
    
    try:
        response = await assistant.chat(
            message=request.message,
            conversation_id=request.conversation_id,
            context=context,
        )
        
        # Convert to response format
        response_data = ChatResponseData(
            response=response.response,
            citations=[
                CitationResponse(
                    content_id=c.content_id,
                    title=c.title,
                    relevance=c.relevance,
                    snippet=c.snippet,
                    url=c.url,
                )
                for c in response.citations
            ],
            suggested_content=[
                SuggestedContentResponse(
                    content_id=s.content_id,
                    title=s.title,
                    description=s.description,
                    relevance=s.relevance,
                    reason=s.reason,
                )
                for s in response.suggested_content
            ],
            external_results=[
                ExternalResultResponse(
                    title=e.title,
                    url=e.url,
                    snippet=e.snippet,
                    source_type=e.source_type,
                )
                for e in response.external_results
            ],
            conversation_id=response.conversation_id,
            used_external_search=response.used_external_search,
        )
        
        return APIResponse(
            success=True,
            data=response_data,
            meta=Meta(
                request_id="",  # Would be set by middleware
            ),
        )
        
    except AssistantConfigError as e:
        logger.error(f"Assistant not configured: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant service is not available",
        )
    except AssistantAPIError as e:
        logger.error(f"Assistant API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process your request",
        )


@router.post(
    "/explain",
    response_model=APIResponse[ChatResponseData],
    status_code=status.HTTP_200_OK,
    summary="Explain specific content",
    description="""
    Get an explanation of how to use specific content.
    
    The assistant will explain:
    - What the content is about
    - Prerequisites needed
    - How to get started
    - Expected learning outcomes
    
    Optionally include a specific question about the content.
    """,
)
async def explain_content(
    request: ExplainRequest,
    user: UserPublic = Depends(get_current_user_required),
    assistant: AssistantService = Depends(get_assistant),
) -> APIResponse[ChatResponseData]:
    """Explain a specific content item."""
    
    context = ChatContext(
        user_id=str(user.id) if hasattr(user, 'id') else None,
        visibility_level=get_visibility_level(user),
        current_content_id=request.content_id,
    )
    
    try:
        response = await assistant.explain_content(
            content_id=request.content_id,
            question=request.question,
            context=context,
        )
        
        response_data = ChatResponseData(
            response=response.response,
            citations=[
                CitationResponse(
                    content_id=c.content_id,
                    title=c.title,
                    relevance=c.relevance,
                    snippet=c.snippet,
                    url=c.url,
                )
                for c in response.citations
            ],
            suggested_content=[
                SuggestedContentResponse(
                    content_id=s.content_id,
                    title=s.title,
                    description=s.description,
                    relevance=s.relevance,
                    reason=s.reason,
                )
                for s in response.suggested_content
            ],
            external_results=[],
            conversation_id=response.conversation_id,
            used_external_search=response.used_external_search,
        )
        
        return APIResponse(
            success=True,
            data=response_data,
            meta=Meta(request_id=""),
        )
        
    except AssistantConfigError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant service is not available",
        )
    except AssistantAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process your request",
        )


@router.post(
    "/recommend",
    response_model=APIResponse[ChatResponseData],
    status_code=status.HTTP_200_OK,
    summary="Get content recommendations",
    description="""
    Get personalized content recommendations based on learning goals.
    
    Specify what you want to learn, and optionally filter by:
    - Skill level (beginner, intermediate, advanced)
    - Specific technologies
    
    The assistant will recommend relevant content with explanations.
    """,
)
async def recommend_content(
    request: RecommendRequest,
    user: UserPublic = Depends(get_current_user_required),
    assistant: AssistantService = Depends(get_assistant),
) -> APIResponse[ChatResponseData]:
    """Get content recommendations."""
    
    context = ChatContext(
        user_id=str(user.id) if hasattr(user, 'id') else None,
        visibility_level=get_visibility_level(user),
    )
    
    try:
        response = await assistant.recommend(
            query=request.query,
            skill_level=request.skill_level,
            technologies=request.technologies,
            context=context,
        )
        
        response_data = ChatResponseData(
            response=response.response,
            citations=[
                CitationResponse(
                    content_id=c.content_id,
                    title=c.title,
                    relevance=c.relevance,
                    snippet=c.snippet,
                    url=c.url,
                )
                for c in response.citations
            ],
            suggested_content=[
                SuggestedContentResponse(
                    content_id=s.content_id,
                    title=s.title,
                    description=s.description,
                    relevance=s.relevance,
                    reason=s.reason,
                )
                for s in response.suggested_content
            ],
            external_results=[],
            conversation_id=response.conversation_id,
            used_external_search=response.used_external_search,
        )
        
        return APIResponse(
            success=True,
            data=response_data,
            meta=Meta(request_id=""),
        )
        
    except AssistantConfigError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Assistant service is not available",
        )
    except AssistantAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process your request",
        )


# =============================================================================
# Conversation Management
# =============================================================================


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear conversation history",
    description="Delete a conversation and its history.",
)
async def clear_conversation(
    conversation_id: str,
    user: UserPublic = Depends(get_current_user_required),
    assistant: AssistantService = Depends(get_assistant),
) -> None:
    """Clear a conversation's history."""
    
    # Note: In production, verify user owns this conversation
    success = assistant.clear_conversation(conversation_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
