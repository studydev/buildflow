"""LoginAttempt repository for OTP storage in Cosmos DB."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.db.cosmos import get_container
from app.models.login_attempt import LoginAttempt

logger = logging.getLogger(__name__)

# Container configuration
CONTAINER_NAME = "login_attempts"
PARTITION_KEY_PATH = "/email"


class LoginAttemptRepository:
    """Repository for LoginAttempt CRUD operations in Cosmos DB."""

    def __init__(self) -> None:
        """Initialize the repository."""
        self._container = None

    @property
    def container(self):
        """Lazy load the container with TTL enabled."""
        if self._container is None:
            self._container = get_container(
                CONTAINER_NAME,
                PARTITION_KEY_PATH,
                default_ttl=300,  # 5 minutes TTL for auto-cleanup
            )
        return self._container

    async def upsert(self, attempt: LoginAttempt) -> LoginAttempt:
        """
        Upsert a login attempt (create or replace).

        This ensures only one OTP exists per email at any time.

        Args:
            attempt: LoginAttempt to upsert

        Returns:
            Upserted LoginAttempt
        """
        item = attempt.to_cosmos_item()
        result = self.container.upsert_item(body=item)
        logger.info("Upserted login attempt for email: %s", attempt.email)
        return LoginAttempt.from_cosmos_item(result)

    async def get_by_email(self, email: str) -> Optional[LoginAttempt]:
        """
        Get login attempt by email.

        Args:
            email: Email address (lowercase)

        Returns:
            LoginAttempt if found and not expired, None otherwise
        """
        email = email.lower()
        query = """
            SELECT * FROM c
            WHERE c.email = @email
            AND c.type = 'login_attempt'
        """
        parameters = [{"name": "@email", "value": email}]

        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            partition_key=email,
        ))

        if not items:
            return None

        attempt = LoginAttempt.from_cosmos_item(items[0])

        # Check if expired (application-level check in addition to TTL)
        if attempt.is_expired():
            return None

        return attempt

    async def delete(self, email: str) -> bool:
        """
        Delete login attempt by email.

        Args:
            email: Email address

        Returns:
            True if deleted, False if not found
        """
        email = email.lower()

        # First, find the document to get its ID
        attempt = await self.get_by_email(email)
        if attempt is None:
            return False

        try:
            self.container.delete_item(
                item=attempt.id,
                partition_key=email,
            )
            logger.info("Deleted login attempt for email: %s", email)
            return True
        except CosmosResourceNotFoundError:
            return False

    async def can_request_new_otp(self, email: str, rate_limit_minutes: int = 3) -> tuple[bool, int]:
        """
        Check if a new OTP can be requested for the email.

        Args:
            email: Email address
            rate_limit_minutes: Minimum minutes between OTP requests

        Returns:
            Tuple of (can_request, seconds_remaining)
            - (True, 0) if new OTP can be requested
            - (False, seconds) if rate limited
        """
        attempt = await self.get_by_email(email)

        if attempt is None:
            return True, 0

        # Calculate time since last OTP request
        now = datetime.now(timezone.utc)
        elapsed = now - attempt.created_at
        rate_limit = timedelta(minutes=rate_limit_minutes)

        if elapsed >= rate_limit:
            return True, 0

        remaining = rate_limit - elapsed
        return False, int(remaining.total_seconds())


# Singleton instance
_repository: Optional[LoginAttemptRepository] = None


def get_login_attempt_repository() -> LoginAttemptRepository:
    """Get or create LoginAttemptRepository singleton."""
    global _repository
    if _repository is None:
        _repository = LoginAttemptRepository()
    return _repository
