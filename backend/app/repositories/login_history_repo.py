"""LoginHistory repository for login audit trail in Cosmos DB."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.db.cosmos import get_container
from app.models.login_history import LoginHistory

logger = logging.getLogger(__name__)

# Container configuration
CONTAINER_NAME = "login_history"
PARTITION_KEY_PATH = "/email"


class LoginHistoryRepository:
    """Repository for LoginHistory CRUD operations in Cosmos DB."""

    def __init__(self) -> None:
        """Initialize the repository."""
        self._container = None

    @property
    def container(self):
        """Lazy load the container (no TTL - permanent storage)."""
        if self._container is None:
            self._container = get_container(
                CONTAINER_NAME,
                PARTITION_KEY_PATH,
            )
        return self._container

    async def create(self, history: LoginHistory) -> LoginHistory:
        """
        Create a new login history record.
        
        Args:
            history: LoginHistory to create
            
        Returns:
            Created LoginHistory
        """
        item = history.to_cosmos_item()
        result = self.container.create_item(body=item)
        logger.info("Created login history for email: %s", history.email)
        return LoginHistory.from_cosmos_item(result)

    async def query_by_email(
        self,
        email: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[LoginHistory]:
        """
        Query login history by email.
        
        Args:
            email: Email address
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of LoginHistory records, ordered by logged_in_at desc
        """
        email = email.lower()
        query = """
            SELECT * FROM c 
            WHERE c.email = @email 
            AND c.type = 'login_history'
            ORDER BY c.logged_in_at DESC
            OFFSET @offset LIMIT @limit
        """
        parameters = [
            {"name": "@email", "value": email},
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        
        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            partition_key=email,
        ))
        
        return [LoginHistory.from_cosmos_item(item) for item in items]

    async def get_last_login(self, email: str) -> Optional[LoginHistory]:
        """
        Get the most recent login record for an email.
        
        Args:
            email: Email address
            
        Returns:
            Most recent LoginHistory or None
        """
        records = await self.query_by_email(email, limit=1)
        return records[0] if records else None

    async def count_by_email(self, email: str) -> int:
        """
        Count total login records for an email.
        
        Args:
            email: Email address
            
        Returns:
            Total count of login records
        """
        email = email.lower()
        query = """
            SELECT VALUE COUNT(1) FROM c 
            WHERE c.email = @email 
            AND c.type = 'login_history'
        """
        parameters = [{"name": "@email", "value": email}]
        
        items = list(self.container.query_items(
            query=query,
            parameters=parameters,
            partition_key=email,
        ))
        
        return items[0] if items else 0


# Singleton instance
_repository: Optional[LoginHistoryRepository] = None


def get_login_history_repository() -> LoginHistoryRepository:
    """Get or create LoginHistoryRepository singleton."""
    global _repository
    if _repository is None:
        _repository = LoginHistoryRepository()
    return _repository
