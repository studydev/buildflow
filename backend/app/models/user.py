"""User model for authentication and authorization."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class User(BaseModel):
    """User entity stored in Cosmos DB."""
    
    # Primary key and partition key
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # User info
    email: EmailStr
    display_name: Optional[str] = None
    
    # Role
    role: UserRole = UserRole.USER
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: Optional[datetime] = None
    
    # Status
    is_active: bool = True
    
    def to_cosmos_item(self) -> dict:
        """Convert to Cosmos DB item format."""
        return {
            "id": self.id,
            "email": self.email,
            "displayName": self.display_name,
            "role": self.role.value,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "lastLoginAt": self.last_login_at.isoformat() if self.last_login_at else None,
            "isActive": self.is_active,
            # Cosmos DB document type for querying
            "type": "user",
        }
    
    @classmethod
    def from_cosmos_item(cls, item: dict) -> "User":
        """Create User from Cosmos DB item."""
        return cls(
            id=item["id"],
            email=item["email"],
            display_name=item.get("displayName"),
            role=UserRole(item["role"]),
            created_at=datetime.fromisoformat(item["createdAt"]),
            updated_at=datetime.fromisoformat(item["updatedAt"]),
            last_login_at=(
                datetime.fromisoformat(item["lastLoginAt"])
                if item.get("lastLoginAt")
                else None
            ),
            is_active=item.get("isActive", True),
        )
    
    def update_login(self) -> "User":
        """Update last login timestamp."""
        now = datetime.now(timezone.utc)
        return self.model_copy(
            update={
                "last_login_at": now,
                "updated_at": now,
            }
        )
    
    def promote_to_contributor(self) -> "User":
        """Promote user to contributor role."""
        return self.model_copy(
            update={
                "role": UserRole.CONTRIBUTOR,
                "updated_at": datetime.now(timezone.utc),
            }
        )


class UserPublic(BaseModel):
    """Public user info (returned in API responses)."""
    
    id: str
    email: EmailStr
    display_name: Optional[str] = None
    role: UserRole
    created_at: datetime
    
    @classmethod
    def from_user(cls, user: User) -> "UserPublic":
        """Create from User model."""
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            created_at=user.created_at,
        )
