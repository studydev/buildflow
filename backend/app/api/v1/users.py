"""Users API endpoints."""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.dependencies import get_current_user
from app.models.user import UserPublic
from app.schemas import APIResponse, Meta
from app.schemas.user import UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=APIResponse,
    summary="Get Current User",
    description="Get the current authenticated user's profile.",
    responses={
        200: {"description": "User profile returned successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def get_me(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> JSONResponse:
    """
    Get the current user's profile.
    
    Returns the authenticated user's information including:
    - User ID
    - Email
    - Display name
    - Role
    - Account creation date
    """
    correlation_id = request.state.correlation_id
    
    response = APIResponse(
        success=True,
        data=UserResponse(
            id=current_user.id,
            email=current_user.email,
            display_name=current_user.display_name,
            role=current_user.role,
            created_at=current_user.created_at,
        ),
        meta=Meta.create(correlation_id),
    )
    
    return JSONResponse(content=response.model_dump(mode="json"))
