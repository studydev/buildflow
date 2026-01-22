"""LoginHistory model for login audit trail."""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LoginHistory(BaseModel):
    """Login history record stored in Cosmos DB.
    
    Records successful login events for audit and tracking.
    
    Container: login_history
    Partition Key: /email
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str  # lowercase, partition key
    user_id: str  # Associated user ID
    logged_in_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_agent: Optional[str] = None  # Browser User-Agent
    ip_address: Optional[str] = None  # Client IP address

    def to_cosmos_item(self) -> dict:
        """Convert to Cosmos DB item format."""
        return {
            "id": self.id,
            "email": self.email,
            "user_id": self.user_id,
            "logged_in_at": self.logged_in_at.isoformat(),
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "type": "login_history",
        }

    @classmethod
    def from_cosmos_item(cls, item: dict) -> "LoginHistory":
        """Create LoginHistory from Cosmos DB item."""
        return cls(
            id=item["id"],
            email=item["email"],
            user_id=item["user_id"],
            logged_in_at=datetime.fromisoformat(item["logged_in_at"]),
            user_agent=item.get("user_agent"),
            ip_address=item.get("ip_address"),
        )
