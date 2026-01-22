"""LoginAttempt model for OTP authentication."""

import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LoginAttempt(BaseModel):
    """OTP authentication attempt stored in Cosmos DB.
    
    Each email can have at most one pending LoginAttempt.
    TTL is used for automatic cleanup after expiration.
    
    Container: login_attempts
    Partition Key: /email
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str  # lowercase, partition key
    otp_code_hash: str  # SHA256 hash of OTP code
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime  # created_at + 3 minutes
    ttl: int = 300  # Cosmos DB TTL in seconds (5 min buffer for cleanup)

    @staticmethod
    def hash_otp(otp_code: str) -> str:
        """Hash OTP code using SHA256."""
        return hashlib.sha256(otp_code.encode()).hexdigest()

    def verify_otp(self, otp_code: str) -> bool:
        """Verify if the provided OTP matches the stored hash."""
        return self.otp_code_hash == self.hash_otp(otp_code)

    def is_expired(self) -> bool:
        """Check if the OTP has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def to_cosmos_item(self) -> dict:
        """Convert to Cosmos DB item format."""
        return {
            "id": self.id,
            "email": self.email,
            "otp_code_hash": self.otp_code_hash,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "ttl": self.ttl,
            "type": "login_attempt",
        }

    @classmethod
    def from_cosmos_item(cls, item: dict) -> "LoginAttempt":
        """Create LoginAttempt from Cosmos DB item."""
        return cls(
            id=item["id"],
            email=item["email"],
            otp_code_hash=item["otp_code_hash"],
            created_at=datetime.fromisoformat(item["created_at"]),
            expires_at=datetime.fromisoformat(item["expires_at"]),
            ttl=item.get("ttl", 300),
        )
