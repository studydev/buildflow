"""Test User model and repository."""

from datetime import datetime, timezone

import pytest

from app.models.enums import UserRole
from app.models.user import User, UserPublic


class TestUserModel:
    """Tests for User model."""

    def test_user_creation_with_defaults(self):
        """User should be created with default values."""
        user = User(email="test@example.com")

        assert user.email == "test@example.com"
        assert user.id is not None
        assert len(user.id) == 36  # UUID format
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert user.display_name is None

    def test_user_creation_with_all_fields(self):
        """User should accept all fields."""
        user = User(
            id="custom-id",
            email="test@example.com",
            display_name="Test User",
            role=UserRole.CONTRIBUTOR,
            is_active=True,
        )

        assert user.id == "custom-id"
        assert user.display_name == "Test User"
        assert user.role == UserRole.CONTRIBUTOR

    def test_to_cosmos_item(self):
        """Should convert to Cosmos DB item format."""
        user = User(
            id="user-123",
            email="test@example.com",
            display_name="Test User",
            role=UserRole.CONTRIBUTOR,
        )

        item = user.to_cosmos_item()

        assert item["id"] == "user-123"
        assert item["email"] == "test@example.com"
        assert item["displayName"] == "Test User"
        assert item["role"] == "contributor"
        assert item["type"] == "user"
        assert "createdAt" in item
        assert "updatedAt" in item

    def test_from_cosmos_item(self):
        """Should create User from Cosmos DB item."""
        item = {
            "id": "user-456",
            "email": "cosmos@example.com",
            "displayName": "Cosmos User",
            "role": "contributor",
            "createdAt": "2024-01-01T00:00:00+00:00",
            "updatedAt": "2024-01-02T00:00:00+00:00",
            "lastLoginAt": "2024-01-02T12:00:00+00:00",
            "isActive": True,
        }

        user = User.from_cosmos_item(item)

        assert user.id == "user-456"
        assert user.email == "cosmos@example.com"
        assert user.display_name == "Cosmos User"
        assert user.role == UserRole.CONTRIBUTOR
        assert user.last_login_at is not None

    def test_update_login(self):
        """Should update last login timestamp."""
        user = User(email="test@example.com")
        original_updated = user.updated_at

        updated_user = user.update_login()

        assert updated_user.last_login_at is not None
        assert updated_user.updated_at >= original_updated
        # Original should be unchanged (immutable)
        assert user.last_login_at is None

    def test_promote_to_contributor(self):
        """Should promote user to contributor role."""
        user = User(email="test@example.com", role=UserRole.USER)

        promoted = user.promote_to_contributor()

        assert promoted.role == UserRole.CONTRIBUTOR
        assert user.role == UserRole.USER  # Original unchanged


class TestUserPublic:
    """Tests for UserPublic model."""

    def test_from_user(self):
        """Should create public user from User model."""
        user = User(
            id="user-789",
            email="public@example.com",
            display_name="Public User",
            role=UserRole.CONTRIBUTOR,
        )

        public = UserPublic.from_user(user)

        assert public.id == "user-789"
        assert public.email == "public@example.com"
        assert public.display_name == "Public User"
        assert public.role == UserRole.CONTRIBUTOR

    def test_public_user_excludes_sensitive_fields(self):
        """Public user should not expose sensitive fields."""
        public = UserPublic(
            id="user-123",
            email="test@example.com",
            role=UserRole.USER,
            created_at=datetime.now(timezone.utc),
        )

        # Check that sensitive fields are not present
        public_dict = public.model_dump()
        assert "is_active" not in public_dict
        assert "updated_at" not in public_dict
        assert "last_login_at" not in public_dict


class TestUserRepository:
    """Tests for UserRepository (requires Cosmos DB)."""

    @pytest.mark.skip(reason="Requires Cosmos DB emulator")
    async def test_create_and_get_user(self):
        """Should create and retrieve user."""
        from app.repositories.user_repo import get_user_repository

        repo = get_user_repository()
        user = User(email="repo-test@example.com")

        created = await repo.create(user)
        assert created.id == user.id

        retrieved = await repo.get_by_id(user.id)
        assert retrieved is not None
        assert retrieved.email == "repo-test@example.com"

        # Cleanup
        await repo.delete(user.id)

    @pytest.mark.skip(reason="Requires Cosmos DB emulator")
    async def test_get_by_email(self):
        """Should find user by email."""
        from app.repositories.user_repo import get_user_repository

        repo = get_user_repository()
        user = User(email="find-by-email@example.com")

        await repo.create(user)

        found = await repo.get_by_email("find-by-email@example.com")
        assert found is not None
        assert found.id == user.id

        # Cleanup
        await repo.delete(user.id)

    @pytest.mark.skip(reason="Requires Cosmos DB emulator")
    async def test_get_or_create_new_user(self):
        """Should create new user if not exists."""
        from app.repositories.user_repo import get_user_repository

        repo = get_user_repository()

        user, created = await repo.get_or_create_by_email("new-user@example.com")

        assert created is True
        assert user.email == "new-user@example.com"

        # Second call should return existing
        user2, created2 = await repo.get_or_create_by_email("new-user@example.com")
        assert created2 is False
        assert user2.id == user.id

        # Cleanup
        await repo.delete(user.id)
