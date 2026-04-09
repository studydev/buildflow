"""YouTube metadata updater.

Fetches latest view_count, like_count, comment_count for all YouTube content
from the YouTube Data API v3 and updates Cosmos DB + AI Search.

Quota:
  - Free tier: 10,000 units/day
  - videos.list cost: 1 unit per call
  - Batch optimization: up to 50 video IDs per request → 100 videos = 2 units
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from azure.cosmos import CosmosClient, PartitionKey

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
COSMOS_CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING", "")
COSMOS_DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME", "buildflow")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "")
YOUTUBE_SEARCH_INDEX_NAME = "buildflow-youtube"

# Batch size for YouTube API (max 50 IDs per request)
BATCH_SIZE = 50
BATCH_DELAY_SECONDS = 0.5  # Delay between batch calls


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL."""
    import re
    patterns = [
        r"(?:v=|/)([a-zA-Z0-9_-]{11})(?:[&?]|$)",
        r"^([a-zA-Z0-9_-]{11})$",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _get_container(database, container_name: str, pk_path: str = "/id"):
    return database.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path=pk_path),
    )


# ─── AI Search helpers ──────────────────────────────────────────────────────

async def _update_search_documents_batch(
    client: httpx.AsyncClient,
    updates: List[Dict[str, Any]],
) -> int:
    """Batch merge-update documents in YouTube AI Search index."""
    if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_API_KEY or not updates:
        return 0

    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{YOUTUBE_SEARCH_INDEX_NAME}/docs/index?api-version=2024-07-01"
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_SEARCH_API_KEY,
    }

    docs = []
    for u in updates:
        doc: Dict[str, Any] = {
            "@search.action": "mergeOrUpload",
            "id": u["id"],
            "view_count": u["view_count"],
            "like_count": u["like_count"],
        }
        docs.append(doc)

    try:
        resp = await client.post(url, json={"value": docs}, headers=headers)
        if resp.status_code in (200, 201):
            return len(docs)
        logger.warning(f"AI Search batch update failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"AI Search batch update error: {e}")
    return 0


# ─── Main logic ──────────────────────────────────────────────────────────────

async def refresh_youtube_metadata() -> Dict[str, Any]:
    """
    Refresh metadata for all YouTube contents.

    Uses batch YouTube API calls (50 IDs per request) for quota efficiency.
    Updates: youtube_analysis, youtube_contents, and AI Search index.

    Returns summary dict with counts.
    """
    if not COSMOS_CONNECTION_STRING:
        return {"error": "COSMOS_CONNECTION_STRING not configured"}
    if not YOUTUBE_API_KEY:
        return {"error": "YOUTUBE_API_KEY not configured"}

    # Cosmos DB setup
    cosmos_client = CosmosClient.from_connection_string(COSMOS_CONNECTION_STRING)
    database = cosmos_client.create_database_if_not_exists(id=COSMOS_DATABASE_NAME)
    yt_contents_container = _get_container(database, "youtube_contents")
    yt_analysis_container = _get_container(database, "youtube_analysis")

    # Fetch all YouTube content items
    query = (
        "SELECT c.id, c.source_url, c.video_id, c.contributor_id, "
        "c.analysis_request_id, c.view_count, c.like_count, c.comment_count, "
        "c.duration_seconds, c.status "
        "FROM c WHERE c.source_type = 'youtube'"
    )
    items = list(yt_contents_container.query_items(
        query=query,
        enable_cross_partition_query=True,
    ))

    total = len(items)
    logger.info(f"Found {total} YouTube contents to refresh")

    if total == 0:
        return {"total": 0, "updated": 0, "failed": 0, "skipped": 0, "quota_used": 0}

    # Build video_id → content_items mapping
    video_id_map: Dict[str, List[Dict]] = {}
    skipped = 0
    for item in items:
        vid = item.get("video_id") or _extract_video_id(item.get("source_url", ""))
        if not vid:
            logger.warning(f"Cannot extract video_id for content {item.get('id')}")
            skipped += 1
            continue
        video_id_map.setdefault(vid, []).append(item)

    unique_video_ids = list(video_id_map.keys())
    logger.info(f"Unique video IDs to query: {len(unique_video_ids)}")

    updated = 0
    failed = 0
    quota_used = 0
    search_updates: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        # Process in batches of 50
        for batch_start in range(0, len(unique_video_ids), BATCH_SIZE):
            batch_ids = unique_video_ids[batch_start:batch_start + BATCH_SIZE]

            try:
                # YouTube API batch request
                resp = await http_client.get(
                    f"{YOUTUBE_API_BASE}/videos",
                    params={
                        "part": "statistics",
                        "id": ",".join(batch_ids),
                        "key": YOUTUBE_API_KEY,
                    },
                )
                quota_used += 1

                if resp.status_code == 403:
                    error_data = resp.json()
                    if "quotaExceeded" in str(error_data):
                        logger.error("YouTube API quota exceeded, stopping.")
                        break
                    logger.error(f"YouTube API forbidden: {error_data}")
                    failed += len(batch_ids)
                    continue

                if resp.status_code != 200:
                    logger.warning(f"YouTube API {resp.status_code}: {resp.text[:200]}")
                    failed += len(batch_ids)
                    continue

                api_data = resp.json()
                api_items = {v["id"]: v for v in api_data.get("items", [])}

                for vid in batch_ids:
                    api_item = api_items.get(vid)
                    if not api_item:
                        logger.warning(f"Video not found in API response: {vid}")
                        failed += 1
                        continue

                    stats = api_item.get("statistics", {})
                    new_view = int(stats.get("viewCount", 0))
                    new_like = int(stats.get("likeCount", 0))
                    new_comment = int(stats.get("commentCount", 0))

                    for content_item in video_id_map[vid]:
                        content_id = content_item["id"]
                        old_view = content_item.get("view_count", 0) or 0
                        old_like = content_item.get("like_count", 0) or 0

                        # Skip if nothing changed
                        if new_view == old_view and new_like == old_like:
                            skipped += 1
                            continue

                        try:
                            # ── Update 1: youtube_contents container ─────
                            full_item = yt_contents_container.read_item(
                                item=content_id,
                                partition_key=content_id,
                            )
                            full_item["view_count"] = new_view
                            full_item["like_count"] = new_like
                            full_item["comment_count"] = new_comment
                            full_item["updated_at"] = datetime.now(timezone.utc).isoformat()
                            yt_contents_container.upsert_item(body=full_item)

                            # ── Update 2: youtube_analysis container ─────
                            analysis_id = content_item.get("analysis_request_id")
                            if analysis_id:
                                try:
                                    ar_query = "SELECT * FROM c WHERE c.id = @id"
                                    ar_params = [{"name": "@id", "value": analysis_id}]
                                    ar_items = list(yt_analysis_container.query_items(
                                        query=ar_query,
                                        parameters=ar_params,
                                        enable_cross_partition_query=True,
                                    ))
                                    if ar_items:
                                        ar_item = ar_items[0]
                                        if ar_item.get("result"):
                                            ar_item["result"]["view_count"] = new_view
                                            ar_item["result"]["like_count"] = new_like
                                            ar_item["result"]["comment_count"] = new_comment
                                            yt_analysis_container.upsert_item(body=ar_item)
                                except Exception as e:
                                    logger.warning(f"Failed to update youtube_analysis {analysis_id}: {e}")

                            # ── Collect for AI Search batch update ────────
                            if content_item.get("status") == "published":
                                search_updates.append({
                                    "id": content_id,
                                    "view_count": new_view,
                                    "like_count": new_like,
                                    "comment_count": new_comment,
                                })

                            updated += 1
                            logger.info(
                                f"Updated YouTube {vid} (content {content_id}): "
                                f"views {old_view}→{new_view}, likes {old_like}→{new_like}"
                            )

                        except Exception as e:
                            logger.error(f"Error updating content {content_id}: {e}")
                            failed += 1

            except Exception as e:
                logger.error(f"Error in YouTube batch request: {e}")
                failed += len(batch_ids)

            # Delay between batch calls
            await asyncio.sleep(BATCH_DELAY_SECONDS)

        # ── Batch update AI Search ───────────────────────────────────────
        if search_updates:
            # Process in batches of 1000 (AI Search limit)
            for si in range(0, len(search_updates), 1000):
                batch = search_updates[si:si + 1000]
                search_updated = await _update_search_documents_batch(http_client, batch)
                logger.info(f"AI Search batch updated {search_updated} YouTube documents")

    summary = {
        "total": total,
        "updated": updated,
        "failed": failed,
        "skipped": skipped,
        "quota_used": quota_used,
        "unique_videos": len(unique_video_ids),
    }
    logger.info(f"YouTube refresh complete: {summary}")
    return summary
