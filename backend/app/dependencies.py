"""FastAPI dependencies for authentication and authorization."""

import logging
from typing import Optional

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, ForbiddenError
from app.core.security import TokenPayload, verify_access_token
from app.models.enums import UserRole
from app.models.user import User, UserPublic
from app.repositories.user_repo import get_user_repository

logger = logging.getLogger(__name__)

# HTTP Bearer token extractor
oauth2_scheme = HTTPBearer(auto_error=False)


async def get_current_user_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_scheme),
) -> TokenPayload:
    """
    Extract and verify JWT token from Authorization header.

    Returns the decoded token payload.

    Raises:
        AuthenticationError: If token is missing, invalid, or expired
    """
    if credentials is None:
        raise AuthenticationError(message="Missing authentication token")

    token = credentials.credentials

    try:
        payload = verify_access_token(token)
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError(message="Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token: %s", e)
        raise AuthenticationError(message="Invalid authentication token")


async def get_current_user(
    token: TokenPayload = Depends(get_current_user_token),
) -> UserPublic:
    """
    Get the current authenticated user.

    Returns a UserPublic model with user info from the token.
    For MVP, constructs user from token claims without DB lookup.

    In production, this would verify user still exists and is active.
    """
    # For MVP without Cosmos, create user from token claims
    # In production: look up user in DB and check is_active
    try:
        repo = get_user_repository()
        user = await repo.get_by_id(token.sub)

        if user is None:
            # User was deleted after token issued
            raise AuthenticationError(message="User not found")

        if not user.is_active:
            raise AuthenticationError(message="User account is disabled")

        return UserPublic.from_user(user)
    except RuntimeError:
        # Cosmos not available - use token claims
        from datetime import datetime, timezone

        return UserPublic(
            id=token.sub,
            email=token.email,
            display_name=None,
            role=UserRole(token.role),
            created_at=datetime.now(timezone.utc),
        )


async def get_current_active_user(
    user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """
    Get the current active user.

    This is a convenience dependency that ensures user is active.
    Same as get_current_user for MVP but can add additional checks.
    """
    return user


def require_role(required_role: UserRole):
    """
    Dependency factory for role-based access control.

    Args:
        required_role: The minimum role required to access the endpoint

    Returns:
        Dependency function that checks user role

    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(
            user: UserPublic = Depends(require_role(UserRole.CONTRIBUTOR))
        ):
            ...
    """
    async def role_checker(
        user: UserPublic = Depends(get_current_user),
    ) -> UserPublic:
        # Role hierarchy: contributor > user
        role_hierarchy = {
            UserRole.USER: 0,
            UserRole.CONTRIBUTOR: 1,
        }

        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)

        if user_level < required_level:
            raise ForbiddenError(
                message=f"This action requires {required_role.value} role"
            )

        return user

    return role_checker


# Convenience dependencies
RequireUser = Depends(get_current_user)
RequireContributor = Depends(require_role(UserRole.CONTRIBUTOR))

# Alias for backward compatibility
get_current_user_required = get_current_active_user


# Function-based dependency for contributors
async def require_contributor(
    user: UserPublic = Depends(get_current_user),
) -> User:
    """
    Require the current user to have contributor role.

    Returns a User model (not UserPublic) for API endpoints that need user.id.
    """
    role_hierarchy = {
        UserRole.USER: 0,
        UserRole.CONTRIBUTOR: 1,
    }

    user_level = role_hierarchy.get(user.role, 0)
    required_level = role_hierarchy.get(UserRole.CONTRIBUTOR, 0)

    if user_level < required_level:
        raise ForbiddenError(
            message="This action requires contributor role"
        )

    # Convert UserPublic back to User for the ID
    return User(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        created_at=user.created_at,
    )
