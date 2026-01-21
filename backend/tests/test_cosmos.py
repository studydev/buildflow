"""Test Cosmos DB client module."""

import pytest

from app.db import cosmos


class TestCosmosModule:
    """Tests for Cosmos DB module (without actual connection)."""

    def test_containers_constants_defined(self):
        """Container name constants should be defined."""
        assert cosmos.Containers.USERS == "users"
        assert cosmos.Containers.CONTENTS == "contents"
        assert cosmos.Containers.OTP_CODES == "otp_codes"

    def test_get_cosmos_client_raises_without_connection_string(self):
        """Should raise error if COSMOS_CONNECTION_STRING is not set."""
        # Reset singleton
        cosmos._cosmos_client = None
        cosmos._database = None
        
        with pytest.raises(RuntimeError) as exc_info:
            cosmos.get_cosmos_client()
        
        assert "COSMOS_CONNECTION_STRING is not set" in str(exc_info.value)

    def test_close_connection_resets_singletons(self):
        """close_connection should reset the singleton instances."""
        # Set dummy values
        cosmos._cosmos_client = "dummy"
        cosmos._database = "dummy"
        
        cosmos.close_connection()
        
        assert cosmos._cosmos_client is None
        assert cosmos._database is None


class TestCosmosOperations:
    """Tests for CRUD operations (would need emulator to actually run)."""

    @pytest.mark.skip(reason="Requires Cosmos DB emulator running")
    async def test_create_and_read_item(self):
        """Test creating and reading an item."""
        test_item = {
            "id": "test-123",
            "name": "Test Item",
            "type": "test",
        }
        
        # Create
        created = await cosmos.create_item("test_container", test_item)
        assert created["id"] == "test-123"
        
        # Read
        read = await cosmos.read_item("test_container", "test-123")
        assert read is not None
        assert read["name"] == "Test Item"
        
        # Cleanup
        await cosmos.delete_item("test_container", "test-123")

    @pytest.mark.skip(reason="Requires Cosmos DB emulator running")
    async def test_health_check(self):
        """Test Cosmos DB health check."""
        result = await cosmos.health_check()
        assert result["status"] == "healthy"
        assert "database" in result
