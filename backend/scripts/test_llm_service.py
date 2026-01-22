#!/usr/bin/env python3
"""Script to test Azure OpenAI LLM service."""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.llm_service import LLMService


async def test_llm():
    """Test Azure OpenAI LLM service."""
    settings = get_settings()

    print("=" * 60)
    print("Azure OpenAI LLM Test")
    print("=" * 60)

    # Check configuration
    print(f"\nAzure OpenAI Endpoint: {settings.azure_openai_endpoint or 'Not configured'}")
    print(f"Deployment Name: {settings.azure_openai_deployment or 'Not configured'}")
    print(f"API Key: {'Configured' if settings.azure_openai_api_key else 'Not configured'}")

    if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
        print("\n❌ Azure OpenAI is not configured. Set AZURE_OPENAI_* environment variables.")
        return False

    # Sample README for testing
    sample_readme = """
# LAB510: The Power of GitHub Copilot in VS Code

## Session Description
Dive deep into the power of GitHub Copilot within VS Code. This hands-on lab
will guide you through maximizing GitHub Copilot's potential for your daily
coding tasks. Get firsthand experience at how Copilot can transform your
workflow with agent mode, boost productivity, and enhance code quality.

## Prerequisites
- Visual Studio Code
- GitHub Copilot subscription
- Basic programming knowledge

## Topics Covered
- Code generation with Copilot
- Agent mode for complex tasks
- Best practices for prompting
- Integrating Copilot into workflows

## Duration
75 minutes
"""

    print("\n📄 Testing metadata extraction from README...")
    print("-" * 40)

    try:
        service = LLMService()
        result = await service.extract_metadata(sample_readme)

        print("\n✅ LLM extraction successful!")
        print("-" * 40)
        print(f"Title (EN): {result.title}")
        print(f"Title (KR): {result.title_kr}")
        print(f"Description (EN): {result.description}")
        print(f"Description (KR): {result.description_kr}")
        print(f"Content Type: {result.content_type}")
        print(f"Level: {result.level}")
        print(f"Categories: {result.categories}")
        print(f"Technologies: {result.technologies}")

        return True

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_llm())
    sys.exit(0 if success else 1)
