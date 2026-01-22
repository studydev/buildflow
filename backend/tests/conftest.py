"""Pytest configuration and fixtures."""

import subprocess
from pathlib import Path

import pytest


class MockEmailService:
    """Mock email service that never sends real emails."""

    async def send_otp(self, email: str, otp: str) -> bool:
        """Mock OTP send - always succeeds without sending."""
        return True

    async def send_welcome(self, email: str, name: str) -> bool:
        """Mock welcome email - always succeeds without sending."""
        return True


@pytest.fixture(scope="session", autouse=True)
def mock_email_service():
    """
    Replace email service with mock to prevent real email sending during tests.

    This prevents:
    - Sending emails to non-existent addresses during tests
    - Damaging email sender reputation
    - Azure Communication Services costs during testing
    """
    import app.services.email_service as email_module

    # Store original
    original_service = email_module._email_service
    original_get_service = email_module.get_email_service

    # Replace with mock
    mock_service = MockEmailService()
    email_module._email_service = mock_service
    email_module.get_email_service = lambda: mock_service

    yield mock_service

    # Restore original
    email_module._email_service = original_service
    email_module.get_email_service = original_get_service


@pytest.fixture(scope="session", autouse=True)
def setup_test_jwt_keys():
    """Generate RSA keys for JWT testing if they don't exist."""
    keys_dir = Path("keys")
    private_key_path = keys_dir / "private.pem"
    public_key_path = keys_dir / "public.pem"

    # Create keys directory if it doesn't exist
    keys_dir.mkdir(exist_ok=True)

    # Generate keys if they don't exist
    if not private_key_path.exists() or not public_key_path.exists():
        # Generate private key
        subprocess.run(
            ["openssl", "genrsa", "-out", str(private_key_path), "2048"],
            check=True,
            capture_output=True,
        )
        # Generate public key
        subprocess.run(
            ["openssl", "rsa", "-in", str(private_key_path), "-pubout", "-out", str(public_key_path)],
            check=True,
            capture_output=True,
        )
        print(f"\n✓ Generated test RSA keys in {keys_dir}/")

    yield

    # Cleanup is optional - keys can be reused
    # If you want to clean up after tests:
    # if private_key_path.exists():
    #     private_key_path.unlink()
    # if public_key_path.exists():
    #     public_key_path.unlink()


@pytest.fixture
def test_user_data():
    """Standard test user data."""
    return {
        "id": "test-user-123",
        "email": "test@example.com",
        "role": "user",
    }


@pytest.fixture
def test_contributor_data():
    """Standard test contributor data."""
    return {
        "id": "test-contributor-456",
        "email": "contributor@example.com",
        "role": "contributor",
    }
