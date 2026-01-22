#!/usr/bin/env python3
"""Script to test Azure OpenAI embedding generation."""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.llm_service import LLMService


async def test_embedding():
    """Test Azure OpenAI embedding generation."""
    settings = get_settings()

    print("=" * 60)
    print("Azure OpenAI Embedding Test (text-embedding-3-small)")
    print("=" * 60)

    # Check configuration
    endpoint = settings.azure_openai_endpoint
    embedding_deployment = getattr(settings, 'azure_openai_embedding_deployment', 'text-embedding-3-small')

    print(f"\nEndpoint: {endpoint or 'Not configured'}")
    print(f"Embedding Deployment: {embedding_deployment}")
    print(f"API Key: {'Configured' if settings.azure_openai_api_key else 'Not configured'}")

    if not endpoint or not settings.azure_openai_api_key:
        print("\n❌ Azure OpenAI is not configured.")
        return False

    # Test text for embedding
    test_text = """
    LAB510: The Power of GitHub Copilot in VS Code.
    Dive deep into the power of GitHub Copilot within VS Code.
    This hands-on lab will guide you through maximizing GitHub Copilot's potential
    for your daily coding tasks. Topics include code generation, agent mode,
    and best practices for prompting.
    """

    print(f"\n📄 Test text ({len(test_text)} chars):")
    print("-" * 40)
    print(test_text.strip()[:200] + "...")

    try:
        service = LLMService()
        print("\n🔄 Generating embedding...")

        embedding = await service.generate_embedding(test_text)

        print("\n✅ Embedding generated successfully!")
        print("-" * 40)
        print(f"Dimension: {len(embedding)}")
        print(f"First 5 values: {embedding[:5]}")
        print(f"Last 5 values: {embedding[-5:]}")
        print(f"Min value: {min(embedding):.6f}")
        print(f"Max value: {max(embedding):.6f}")

        # Check dimension
        if len(embedding) == 1536:
            print("\n✅ Correct dimension (1536) for text-embedding-3-small")
        else:
            print(f"\n⚠️  Unexpected dimension: {len(embedding)} (expected 1536)")

        return True

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_embedding())
    sys.exit(0 if success else 1)
