"""Cosmos DB client and connection management."""

import logging
from typing import Any, Dict, List, Optional

from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.database import DatabaseProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.config import get_settings

logger = logging.getLogger(__name__)

# Singleton instances
_cosmos_client: Optional[CosmosClient] = None
_database: Optional[DatabaseProxy] = None
_mock_data: Dict[str, List[Dict[str, Any]]] = {}


# =============================================================================
# Mock Container for Development without Cosmos DB
# =============================================================================

class MockContainerProxy:
    """In-memory mock container for development without Cosmos DB."""

    def __init__(self, container_name: str):
        self.container_name = container_name
        if container_name not in _mock_data:
            _mock_data[container_name] = []

    @property
    def _items(self) -> List[Dict[str, Any]]:
        return _mock_data[self.container_name]

    def create_item(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Create an item in the mock container."""
        self._items.append(body.copy())
        return body

    def read_item(self, item: str, partition_key: str) -> Dict[str, Any]:
        """Read an item by ID and partition key."""
        for stored_item in self._items:
            if stored_item.get("id") == item:
                return stored_item
        raise CosmosResourceNotFoundError(message="Not found")

    def upsert_item(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert (create or update) an item."""
        item_id = body.get("id")
        for i, stored_item in enumerate(self._items):
            if stored_item.get("id") == item_id:
                self._items[i] = body.copy()
                return body
        self._items.append(body.copy())
        return body

    def delete_item(self, item: str, partition_key: str) -> None:
        """Delete an item by ID."""
        for i, stored_item in enumerate(self._items):
            if stored_item.get("id") == item:
                del self._items[i]
                return
        raise CosmosResourceNotFoundError(message="Not found")

    def query_items(
        self,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
        partition_key: Optional[str] = None,
        enable_cross_partition_query: bool = False,
    ) -> List[Dict[str, Any]]:
        """Simple query implementation for mock container."""
        params_dict = {p["name"]: p["value"] for p in (parameters or [])}

        # Handle COUNT queries
        if "COUNT(1)" in query.upper():
            count = sum(1 for item in self._items if self._matches_filters(item, params_dict, query))
            return [count]

        # Filter items based on query parameters
        results = [item for item in self._items if self._matches_filters(item, params_dict, query)]

        # Handle OFFSET/LIMIT
        if "@offset" in params_dict and "@limit" in params_dict:
            offset = params_dict["@offset"]
            limit = params_dict["@limit"]
            results = results[offset:offset + limit]

        return results

    def _matches_filters(self, item: Dict[str, Any], params: Dict[str, Any], query: str) -> bool:
        """Check if item matches query filters."""
        query_lower = query.lower()

        # Check user_id filter
        if "@user_id" in params:
            if item.get("user_id") != params["@user_id"]:
                return False

        # Check contributor_id filter
        if "@contributor_id" in params:
            if item.get("contributor_id") != params["@contributor_id"]:
                return False

        # Check type filter
        if "@type" in params:
            if item.get("type") != params["@type"]:
                return False
        elif "c.type = 'analysis_request'" in query_lower:
            if item.get("type") != "analysis_request":
                return False

        # Check status filter
        if "@status" in params:
            if item.get("status") != params["@status"]:
                return False

        # Check id filter
        if "@id" in params:
            if item.get("id") != params["@id"]:
                return False

        # Check source_url filter
        if "@source_url" in params:
            if item.get("source_url") != params["@source_url"]:
                return False

        # Check category filter with ARRAY_CONTAINS
        if "@category" in params:
            categories = item.get("categories", [])
            if params["@category"] not in categories:
                return False

        # Check search filter with CONTAINS
        if "@search" in params:
            search_term = params["@search"].lower()
            title = (item.get("title") or "").lower()
            description = (item.get("description") or "").lower()
            if search_term not in title and search_term not in description:
                return False

        return True


def is_mock_mode() -> bool:
    """Check if running in mock mode (no Cosmos DB connection)."""
    settings = get_settings()
    return not settings.cosmos_connection_string


def get_cosmos_client() -> CosmosClient:
    """
    Get or create the Cosmos DB client singleton.

    Uses connection string from settings. For local development,
    connects to the Cosmos DB emulator.
    """
    global _cosmos_client

    if _cosmos_client is None:
        settings = get_settings()

        if not settings.cosmos_connection_string:
            raise RuntimeError(
                "COSMOS_CONNECTION_STRING is not set. "
                "Set it in .env or start the Cosmos DB emulator."
            )

        _cosmos_client = CosmosClient.from_connection_string(
            settings.cosmos_connection_string
        )
        logger.info("Cosmos DB client initialized")

    return _cosmos_client


def get_database() -> DatabaseProxy:
    """
    Get or create the database singleton.

    Creates the database if it doesn't exist.
    """
    global _database

    if _database is None:
        settings = get_settings()
        client = get_cosmos_client()

        _database = client.create_database_if_not_exists(
            id=settings.cosmos_database_name
        )
        logger.info("Connected to database: %s", settings.cosmos_database_name)

    return _database


def get_container(container_name: str, partition_key_path: str = "/id"):
    """
    Get a container, creating it if it doesn't exist.

    In mock mode (no COSMOS_CONNECTION_STRING), returns a MockContainerProxy.

    Args:
        container_name: Name of the container
        partition_key_path: Path to the partition key (default: /id)

    Returns:
        ContainerProxy or MockContainerProxy for the specified container
    """
    # Use mock container if no Cosmos DB connection
    if is_mock_mode():
        logger.debug("Using mock container for: %s", container_name)
        return MockContainerProxy(container_name)

    database = get_database()

    container = database.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path=partition_key_path),
    )
    logger.debug("Got container: %s", container_name)

    return container


# Container name constants
class Containers:
    """Container name constants."""

    USERS = "users"
    CONTENTS = "contents"
    OTP_CODES = "otp_codes"  # For OTP storage if needed
    ANALYSIS_REQUESTS = "analysis_requests"
    # YouTube containers
    YOUTUBE_ANALYSIS = "youtube_analysis"
    YOUTUBE_CONTENTS = "youtube_contents"


# =============================================================================
# Generic CRUD Operations
# =============================================================================


async def create_item(
    container_name: str,
    item: dict,
    partition_key_path: str = "/id",
) -> dict:
    """
    Create an item in the specified container.

    Args:
        container_name: Target container name
        item: Item data (must include 'id' field)
        partition_key_path: Partition key path for the container

    Returns:
        Created item with Cosmos metadata
    """
    container = get_container(container_name, partition_key_path)
    return container.create_item(body=item)


async def read_item(
    container_name: str,
    item_id: str,
    partition_key: Optional[str] = None,
    partition_key_path: str = "/id",
) -> Optional[dict]:
    """
    Read an item by ID.

    Args:
        container_name: Target container name
        item_id: Item ID
        partition_key: Partition key value (defaults to item_id if None)
        partition_key_path: Partition key path for the container

    Returns:
        Item data or None if not found
    """
    container = get_container(container_name, partition_key_path)
    pk = partition_key if partition_key is not None else item_id

    try:
        return container.read_item(item=item_id, partition_key=pk)
    except CosmosResourceNotFoundError:
        return None


async def upsert_item(
    container_name: str,
    item: dict,
    partition_key_path: str = "/id",
) -> dict:
    """
    Upsert (create or update) an item.

    Args:
        container_name: Target container name
        item: Item data (must include 'id' field)
        partition_key_path: Partition key path for the container

    Returns:
        Upserted item with Cosmos metadata
    """
    container = get_container(container_name, partition_key_path)
    return container.upsert_item(body=item)


async def delete_item(
    container_name: str,
    item_id: str,
    partition_key: Optional[str] = None,
    partition_key_path: str = "/id",
) -> bool:
    """
    Delete an item by ID.

    Args:
        container_name: Target container name
        item_id: Item ID
        partition_key: Partition key value (defaults to item_id if None)
        partition_key_path: Partition key path for the container

    Returns:
        True if deleted, False if not found
    """
    container = get_container(container_name, partition_key_path)
    pk = partition_key if partition_key is not None else item_id

    try:
        container.delete_item(item=item_id, partition_key=pk)
        return True
    except CosmosResourceNotFoundError:
        return False


async def query_items(
    container_name: str,
    query: str,
    parameters: Optional[list] = None,
    partition_key_path: str = "/id",
) -> list[dict]:
    """
    Query items using SQL.

    Args:
        container_name: Target container name
        query: Cosmos SQL query string
        parameters: Query parameters
        partition_key_path: Partition key path for the container

    Returns:
        List of matching items
    """
    container = get_container(container_name, partition_key_path)

    items = container.query_items(
        query=query,
        parameters=parameters or [],
        enable_cross_partition_query=True,
    )

    return list(items)


# =============================================================================
# Connection Management
# =============================================================================


def close_connection() -> None:
    """Close the Cosmos DB connection and reset singletons."""
    global _cosmos_client, _database

    if _cosmos_client is not None:
        # CosmosClient doesn't have explicit close, but we reset singletons
        _cosmos_client = None
        _database = None
        logger.info("Cosmos DB connection closed")


async def health_check() -> dict:
    """
    Check Cosmos DB connection health.

    Returns:
        Dict with connection status and details
    """
    try:
        client = get_cosmos_client()
        database = get_database()

        # List containers to verify connection
        containers = list(database.list_containers())

        return {
            "status": "healthy",
            "database": database.id,
            "containers": len(containers),
        }
    except Exception as e:
        logger.error("Cosmos DB health check failed: %s", str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
        }
