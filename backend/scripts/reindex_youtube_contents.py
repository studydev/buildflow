#!/usr/bin/env python3
"""Script to reindex existing YouTube contents into Azure AI Search."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(".env.local")

from app.repositories.youtube_repo import get_youtube_content_repo
from app.services.youtube_search_service import get_youtube_search_service


async def main():
    """Reindex all published YouTube contents."""
    repo = get_youtube_content_repo()
    search_service = get_youtube_search_service()

    print(f"Search service configured: {search_service.is_configured}")
    print(f"Endpoint: {search_service.endpoint}")
    print(f"Index: {search_service.index_name}")
    print()

    contents = await repo.list_published(limit=100, offset=0)
    print(f"Found {len(contents)} published YouTube contents in CosmosDB")
    print()

    indexed = 0
    failed = 0

    for content in contents:
        try:
            result = await search_service.index_content(content)
            print(f"  Indexed: {content.id}")
            print(f"    Title: {content.title[:60] if content.title else 'No title'}...")
            indexed += 1
        except Exception as e:
            print(f"  Failed: {content.id} - {e}")
            failed += 1

    await search_service.close()

    print()
    print(f"Done! Indexed: {indexed}, Failed: {failed}")

    # Verify
    print()
    print("Verifying index...")
    search_service2 = get_youtube_search_service()
    result = await search_service2.search(query="*", top=10)
    print(f"Documents in index: {result.total_count}")
    await search_service2.close()


if __name__ == "__main__":
    asyncio.run(main())
