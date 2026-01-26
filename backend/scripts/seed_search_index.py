#!/usr/bin/env python3
"""Azure AI Search Index Management Script.

This script creates the search index and indexes all existing content from CosmosDB.

Usage:
    # Create index only
    python -m scripts.seed_search_index --create-index

    # Index all content (creates index if not exists)
    python -m scripts.seed_search_index --index-all

    # Delete index
    python -m scripts.seed_search_index --delete-index

    # Reindex specific content by ID
    python -m scripts.seed_search_index --reindex <content-id>
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.db.cosmos import get_cosmos_client
from app.services.llm_service import get_llm_service
from app.services.search_service import get_search_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_index() -> bool:
    """Create or update the search index."""
    search_service = get_search_service()

    if not search_service.is_configured:
        logger.error("Azure AI Search is not configured. Check AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY")
        return False

    try:
        await search_service.create_or_update_index()
        logger.info("✅ Search index created/updated successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create index: {e}")
        return False


async def delete_index() -> bool:
    """Delete the search index."""
    search_service = get_search_service()

    if not search_service.is_configured:
        logger.error("Azure AI Search is not configured")
        return False

    try:
        await search_service.delete_index()
        logger.info("✅ Search index deleted")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete index: {e}")
        return False


def build_embedding_text(content: dict) -> str:
    """Build text for embedding generation.

    Combines title, description, and technologies (English + Korean).
    """
    parts = [
        content.get("title", ""),
        content.get("title_kr") or "",
        content.get("description", ""),
        content.get("description_kr") or "",
        " ".join(content.get("technologies") or []),
    ]
    return " ".join(filter(None, parts))


def format_datetime_for_search(dt_value) -> Optional[str]:
    """Format datetime for Azure AI Search (ISO8601 with Z suffix).

    Args:
        dt_value: datetime string or datetime object

    Returns:
        ISO8601 formatted string with Z suffix, or None
    """
    if not dt_value:
        return None

    if isinstance(dt_value, str):
        # Already a string, ensure it ends with Z
        if dt_value.endswith("Z"):
            return dt_value
        if "+" in dt_value:
            # Has timezone info, convert to Z format
            return dt_value.split("+")[0] + "Z"
        # No timezone, assume UTC
        return dt_value + "Z"
    else:
        # datetime object
        return dt_value.strftime("%Y-%m-%dT%H:%M:%SZ")


async def index_all_content() -> tuple[int, int]:
    """Index all published content from CosmosDB.

    Returns:
        Tuple of (success_count, failure_count)
    """
    settings = get_settings()
    search_service = get_search_service()
    llm_service = get_llm_service()

    if not search_service.is_configured:
        logger.error("Azure AI Search is not configured")
        return 0, 0

    # Ensure index exists
    try:
        await search_service.create_or_update_index()
    except Exception as e:
        logger.error(f"Failed to ensure index exists: {e}")
        return 0, 0

    # Get Cosmos DB client
    cosmos_client = get_cosmos_client()
    database = cosmos_client.get_database_client(settings.cosmos_database_name)
    container = database.get_container_client("contents")

    # Query all published content
    query = "SELECT * FROM c WHERE c.status = 'published'"

    success_count = 0
    failure_count = 0

    logger.info("Loading content from CosmosDB...")

    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    total = len(items)
    logger.info(f"Found {total} published content items")

    for i, item in enumerate(items, 1):
        content_id = item.get("id")
        title = item.get("title", "Untitled")

        try:
            logger.info(f"[{i}/{total}] Indexing: {title[:50]}...")

            # Generate embedding
            embedding = None
            embedding_text = build_embedding_text(item)

            if llm_service.is_configured and embedding_text.strip():
                try:
                    embedding = await llm_service.generate_embedding(embedding_text)
                    logger.debug(f"  Generated embedding ({len(embedding)} dimensions)")
                except Exception as e:
                    logger.warning(f"  ⚠️ Embedding generation failed: {e}")

            # Build search document with all UI fields
            doc = {
                "@search.action": "mergeOrUpload",
                "id": content_id,
                # Searchable text fields
                "title": item.get("title"),
                "title_kr": item.get("title_kr"),
                "description": item.get("description"),
                "description_kr": item.get("description_kr"),
                "summary": item.get("summary_short") or item.get("summary_long"),
                "summary_kr": item.get("summary_kr"),
                # Collections
                "categories": item.get("categories") or [],
                "technologies": item.get("technologies") or [],
                # Filterable fields
                "difficulty_level": item.get("level") or item.get("difficulty_level"),
                "visibility": "public" if item.get("status") == "published" else "internal",
                "content_type": item.get("content_type"),
                # Metrics
                "popularity_score": item.get("popularity_score") or 0.0,
                "stars": item.get("stars") or 0,
                "view_count": item.get("view_count") or 0,
                "duration_minutes": item.get("duration_minutes"),
                # UI display fields - URLs
                "source_url": item.get("source_url"),
                "video_url": item.get("video_url"),
                "thumbnail_url": item.get("thumbnail_url"),
                "icon": item.get("icon"),
                # Learning content
                "learning_outcomes": item.get("learning_outcomes") or [],
                "learning_outcomes_kr": item.get("learning_outcomes_kr") or [],
                "prerequisites": item.get("prerequisites") or [],
                "prerequisites_kr": item.get("prerequisites_kr") or [],
            }

            # Add dates if present (formatted for Azure AI Search)
            if item.get("last_commit_date"):
                doc["last_commit_date"] = format_datetime_for_search(item["last_commit_date"])
            if item.get("created_at"):
                doc["created_at"] = format_datetime_for_search(item["created_at"])

            # Add embedding if generated
            if embedding:
                doc["content_vector"] = embedding

            # Remove None values
            doc = {k: v for k, v in doc.items() if v is not None}

            # Upsert to search index
            await search_service.upsert_documents([doc])
            success_count += 1
            logger.info("  ✅ Indexed successfully")

        except Exception as e:
            failure_count += 1
            logger.error(f"  ❌ Failed to index {content_id}: {e}")

    return success_count, failure_count


async def reindex_content(content_id: str) -> bool:
    """Reindex a specific content item.

    Args:
        content_id: Content UUID to reindex

    Returns:
        True if successful
    """
    settings = get_settings()
    search_service = get_search_service()
    llm_service = get_llm_service()

    if not search_service.is_configured:
        logger.error("Azure AI Search is not configured")
        return False

    # Get content from CosmosDB
    cosmos_client = get_cosmos_client()
    database = cosmos_client.get_database_client(settings.cosmos_database_name)
    container = database.get_container_client("contents")

    try:
        item = container.read_item(item=content_id, partition_key=content_id)
    except Exception as e:
        logger.error(f"Content not found: {content_id}")
        return False

    logger.info(f"Reindexing: {item.get('title', 'Untitled')}")

    # Generate embedding
    embedding = None
    embedding_text = build_embedding_text(item)

    if llm_service.is_configured and embedding_text.strip():
        try:
            embedding = await llm_service.generate_embedding(embedding_text)
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")

    # Build and upsert document with all UI fields
    doc = {
        "@search.action": "mergeOrUpload",
        "id": content_id,
        # Searchable text fields
        "title": item.get("title"),
        "title_kr": item.get("title_kr"),
        "description": item.get("description"),
        "description_kr": item.get("description_kr"),
        "summary": item.get("summary_short") or item.get("summary_long"),
        "summary_kr": item.get("summary_kr"),
        # Collections
        "categories": item.get("categories") or [],
        "technologies": item.get("technologies") or [],
        # Filterable fields
        "difficulty_level": item.get("level") or item.get("difficulty_level"),
        "visibility": "public" if item.get("status") == "published" else "internal",
        "content_type": item.get("content_type"),
        # Metrics
        "popularity_score": item.get("popularity_score") or 0.0,
        "stars": item.get("stars") or 0,
        "view_count": item.get("view_count") or 0,
        "duration_minutes": item.get("duration_minutes"),
        # UI display fields - URLs
        "source_url": item.get("source_url"),
        "video_url": item.get("video_url"),
        "thumbnail_url": item.get("thumbnail_url"),
        "icon": item.get("icon"),
        # Learning content
        "learning_outcomes": item.get("learning_outcomes") or [],
        "learning_outcomes_kr": item.get("learning_outcomes_kr") or [],
        "prerequisites": item.get("prerequisites") or [],
        "prerequisites_kr": item.get("prerequisites_kr") or [],
    }

    if item.get("last_commit_date"):
        doc["last_commit_date"] = format_datetime_for_search(item["last_commit_date"])
    if item.get("created_at"):
        doc["created_at"] = format_datetime_for_search(item["created_at"])
    if embedding:
        doc["content_vector"] = embedding

    doc = {k: v for k, v in doc.items() if v is not None}

    try:
        await search_service.upsert_documents([doc])
        logger.info("✅ Reindexed successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to reindex: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Azure AI Search Index Management"
    )
    parser.add_argument(
        "--create-index",
        action="store_true",
        help="Create or update the search index"
    )
    parser.add_argument(
        "--delete-index",
        action="store_true",
        help="Delete the search index"
    )
    parser.add_argument(
        "--index-all",
        action="store_true",
        help="Index all published content from CosmosDB"
    )
    parser.add_argument(
        "--reindex",
        type=str,
        metavar="CONTENT_ID",
        help="Reindex a specific content by ID"
    )

    args = parser.parse_args()

    # Check configuration
    settings = get_settings()
    search_service = get_search_service()

    logger.info("=" * 60)
    logger.info("Azure AI Search Index Management")
    logger.info("=" * 60)
    logger.info(f"Endpoint: {settings.azure_search_endpoint or 'NOT SET'}")
    logger.info(f"Index: {settings.azure_search_index_name}")
    logger.info(f"Configured: {search_service.is_configured}")
    logger.info("=" * 60)

    if not search_service.is_configured:
        logger.error("❌ Azure AI Search is not configured!")
        logger.error("Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY in .env.local")
        sys.exit(1)

    try:
        if args.delete_index:
            success = await delete_index()
            sys.exit(0 if success else 1)

        if args.create_index:
            success = await create_index()
            sys.exit(0 if success else 1)

        if args.index_all:
            success_count, failure_count = await index_all_content()
            logger.info("=" * 60)
            logger.info(f"Indexing complete: {success_count} succeeded, {failure_count} failed")
            logger.info("=" * 60)
            sys.exit(0 if failure_count == 0 else 1)

        if args.reindex:
            success = await reindex_content(args.reindex)
            sys.exit(0 if success else 1)

        # Default: show help
        parser.print_help()

    finally:
        # Cleanup
        await search_service.close()


if __name__ == "__main__":
    asyncio.run(main())
