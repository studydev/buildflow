"""Script to create YouTube search index in Azure AI Search.

Usage:
    cd backend
    python -m scripts.seed_youtube_search_index
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")


async def main():
    """Create YouTube search index."""
    from app.services.youtube_search_service import YOUTUBE_INDEX_NAME, YouTubeSearchService

    print(f"Creating YouTube search index: {YOUTUBE_INDEX_NAME}")

    service = YouTubeSearchService()

    if not service.is_configured:
        print("ERROR: Azure Search not configured. Check AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY in .env.local")
        sys.exit(1)

    try:
        result = await service.create_index()
        print(f"Index created/updated successfully: {YOUTUBE_INDEX_NAME}")
        print(f"Result: {result}")
    except Exception as e:
        print(f"ERROR: Failed to create index: {e}")
        sys.exit(1)
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
