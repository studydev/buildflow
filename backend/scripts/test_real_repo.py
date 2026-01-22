#!/usr/bin/env python3
"""Script to test full pipeline with real GitHub repo."""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.github_service import GitHubService
from app.services.llm_service import LLMService


async def test_real_repo(url: str):
    """Test full extraction pipeline with a real GitHub repo."""
    settings = get_settings()

    print("=" * 60)
    print("Real GitHub Repo Extraction Test")
    print("=" * 60)
    print(f"\n📦 Repository: {url}")

    # Step 1: Fetch from GitHub
    print("\n" + "-" * 40)
    print("Step 1: Fetching from GitHub...")

    github_service = GitHubService(token=settings.github_token)

    try:
        repo_info = await github_service.fetch_repo_with_readme(url)
        print("✅ Fetched successfully!")
        print(f"   Owner: {repo_info.owner}")
        print(f"   Repo: {repo_info.repo}")
        print(f"   Language: {repo_info.language}")
        print(f"   Languages: {repo_info.languages}")
        print(f"   Stars: {repo_info.stars}")
        print(f"   Forks: {repo_info.forks}")
        print(f"   Watchers: {repo_info.watchers}")
        print(f"   Topics: {repo_info.topics_str}")
        print(f"   License: {repo_info.license}")
        print(f"   Contributors: {repo_info.contributors_str}")
        print(f"   Created: {repo_info.created_at}")
        print(f"   Last Push: {repo_info.pushed_at}")
        print(f"   Demo URL: {repo_info.demo_url}")
        print(f"   Video URL: {repo_info.video_url}")
        print(f"   Homepage: {repo_info.homepage_url}")

        if repo_info.readme_content:
            print(f"\n📄 README Preview ({len(repo_info.readme_content)} chars):")
            print("-" * 40)
            print(repo_info.readme_content[:500])
            if len(repo_info.readme_content) > 500:
                print("...")
        else:
            print("\n⚠️  No README found")
            return False

    except Exception as e:
        print(f"❌ GitHub fetch failed: {e}")
        return False

    # Step 2: Extract metadata with LLM
    print("\n" + "-" * 40)
    print("Step 2: Extracting metadata with LLM...")

    if not settings.azure_openai_api_key:
        print("❌ Azure OpenAI not configured")
        return False

    llm_service = LLMService()

    try:
        result = await llm_service.extract_metadata(
            readme_content=repo_info.readme_content,
            repo_description=repo_info.description,
            repo_topics=repo_info.topics,
            repo_language=repo_info.language,
            repo_stars=repo_info.stars,
        )

        print("\n✅ Extraction successful!")
        print("=" * 60)

        print("\n📝 Title (English):")
        print(f"   {result.title}")

        print("\n📝 Title (Korean):")
        print(f"   {result.title_kr}")

        print("\n📝 Description (English):")
        print(f"   {result.description}")

        print("\n📝 Description (Korean):")
        print(f"   {result.description_kr}")

        print(f"\n📦 Content Type: {result.content_type}")
        print(f"📊 Level: {result.level}")
        print(f"⏱️  Duration: {result.duration_minutes} minutes")
        print(f"🏷️  Categories: {result.categories}")
        print(f"🔧 Technologies: {result.technologies}")

        if result.prerequisites:
            print("\n📋 Prerequisites:")
            for prereq in result.prerequisites[:5]:
                print(f"   - {prereq}")

        if result.learning_objectives:
            print("\n🎯 Learning Objectives:")
            for obj in result.learning_objectives[:5]:
                print(f"   - {obj}")

        # Validation
        print("\n" + "=" * 60)
        print("Validation:")
        print("-" * 40)

        # Check if fields have correct language
        def has_korean(text):
            return text and any('\uac00' <= c <= '\ud7a3' for c in text)

        def is_mostly_english(text):
            if not text:
                return False
            alpha_chars = [c for c in text if c.isalpha()]
            if not alpha_chars:
                return True
            ascii_alpha = sum(1 for c in alpha_chars if ord(c) < 128)
            return ascii_alpha / len(alpha_chars) > 0.7

        checks = {
            "title is in English": is_mostly_english(result.title),
            "title_kr has Korean": has_korean(result.title_kr),
            "description is in English": is_mostly_english(result.description),
            "description_kr has Korean": has_korean(result.description_kr),
        }

        all_valid = True
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
            if not passed:
                all_valid = False

        print(f"\n{'✅ All bilingual fields are correct!' if all_valid else '⚠️  Some fields may need review'}")

        return all_valid

    except Exception as e:
        print(f"❌ LLM extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Test URL - can be overridden via command line
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://github.com/hyounsookim/mystock"

    success = asyncio.run(test_real_repo(test_url))
    sys.exit(0 if success else 1)
