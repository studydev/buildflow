#!/usr/bin/env python3
"""Script to test GitHub API fetch with the configured token."""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.github_service import GitHubService


async def test_fetch():
    """Test fetching a GitHub repository."""
    settings = get_settings()

    print("=" * 60)
    print("GitHub API Test")
    print("=" * 60)

    # Check if token is configured
    token = settings.github_token
    if token:
        print(f"✅ GitHub Token configured: {token[:8]}...{token[-4:]}")
    else:
        print("⚠️  No GitHub Token configured (will use unauthenticated requests)")

    # Test URL
    test_url = "https://github.com/microsoft/ignite25-LAB510-the-power-of-github-copilot-in-vs-code"
    print(f"\n📦 Fetching: {test_url}")

    # Create service and fetch
    service = GitHubService(token=token)

    try:
        repo_info = await service.fetch_repo_with_readme(test_url)

        print("\n✅ Successfully fetched repository!")
        print("-" * 40)
        print(f"Owner: {repo_info.owner}")
        print(f"Repo: {repo_info.repo}")
        print(f"Description: {repo_info.description}")
        print(f"Language: {repo_info.language}")
        print(f"Stars: {repo_info.stars}")
        print(f"Forks: {repo_info.forks}")
        print(f"Topics: {repo_info.topics}")
        print(f"License: {repo_info.license}")

        if repo_info.readme_content:
            readme_preview = repo_info.readme_content[:500]
            print(f"\n📄 README Preview ({len(repo_info.readme_content)} chars):")
            print("-" * 40)
            print(readme_preview)
            if len(repo_info.readme_content) > 500:
                print("...")
        else:
            print("\n⚠️  No README content found")

        # Check rate limit
        print("\n" + "=" * 60)
        print("Checking rate limit...")
        rate_limit = await service._check_rate_limit()
        print(f"Rate Limit: {rate_limit['remaining']}/{rate_limit['limit']}")
        print(f"Resets at: {rate_limit['reset']}")

        return True

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_fetch())
    sys.exit(0 if success else 1)
