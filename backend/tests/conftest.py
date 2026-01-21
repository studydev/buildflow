"""Pytest configuration and fixtures."""

import os
import subprocess
from pathlib import Path

import pytest


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
