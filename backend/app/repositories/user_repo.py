"""User repository for Cosmos DB operations."""

import logging
from datetime import datetime, timezone
from typing import Optional

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.config import get_settings
from app.db.cosmos import Containers, get_container
from app.models.user import User
from app.models.enums import UserRole

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for User CRUD operations in Cosmos DB."""
    
    CONTAINER_NAME = Containers.USERS
    PARTITION_KEY_PATH = "/id"
    
    def __init__(self) -> None:
        """Initialize the repository."""
        self._container = None
    
    @property
    def container(self):
        """Lazy load the container."""
        if self._container is None:
            self._container = get_container(
                self.CONTAINER_NAME,
                self.PARTITION_KEY_PATH,
            )
        return self._container
    
    async def create(self, user: User) -> User:
        """
        Create a new user.
        
        Args:
            user: User to create
        
        Returns:
            Created user with Cosmos metadata
        """
        item = user.to_cosmos_item()
        created = self.container.create_item(body=item)
        logger.info("Created user: %s", user.id)
        return User.from_cosmos_item(created)
    
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User ID (also partition key)
        
        Returns:
            User if found, None otherwise
        """
        try:
            item = self.container.read_item(
                item=user_id,
                partition_key=user_id,
            )
            return User.from_cosmos_item(item)
        except CosmosResourceNotFoundError:
            return None
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.
        
        Args:
            email: User email
        
        Returns:
            User if found, None otherwise
        """
        query = "SELECT * FROM c WHERE c.email = @email AND c.type = 'user'"
        parameters = [{"name": "@email", "value": email}]
        
        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ))
        
        if not items:
            return None
        
        return User.from_cosmos_item(items[0])
    
    async def update(self, user: User) -> User:
        """
        Update an existing user.
        
        Args:
            user: User with updated fields
        
        Returns:
            Updated user
        """
        # Update timestamp
        user = user.model_copy(
            update={"updated_at": datetime.now(timezone.utc)}
        )
        
        item = user.to_cosmos_item()
        updated = self.container.upsert_item(body=item)
        logger.info("Updated user: %s", user.id)
        return User.from_cosmos_item(updated)
    
    async def delete(self, user_id: str) -> bool:
        """
        Delete a user by ID.
        
        Args:
            user_id: User ID to delete
        
        Returns:
            True if deleted, False if not found
        """
        try:
            self.container.delete_item(
                item=user_id,
                partition_key=user_id,
            )
            logger.info("Deleted user: %s", user_id)
            return True
        except CosmosResourceNotFoundError:
            return False
    
    async def update_last_login(self, user_id: str) -> Optional[User]:
        """
        Update user's last login timestamp.
        
        Args:
            user_id: User ID
        
        Returns:
            Updated user or None if not found
        """
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        updated_user = user.update_login()
        return await self.update(updated_user)
    
    async def get_or_create_by_email(self, email: str) -> tuple[User, bool]:
        """
        Get existing user or create new one by email.
        
        Args:
            email: User email
        
        Returns:
            Tuple of (user, created) where created is True if new user
        """
        existing = await self.get_by_email(email)
        if existing:
            return existing, False
        
        # In development mode, new users get contributor role for testing
        settings = get_settings()
        role = UserRole.CONTRIBUTOR if settings.debug else UserRole.USER
        
        new_user = User(email=email, role=role)
        created = await self.create(new_user)
        return created, True


# Singleton instance
_user_repo: Optional[UserRepository] = None


def get_user_repository() -> UserRepository:
    """Get the UserRepository singleton."""
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepository()
    return _user_repo
