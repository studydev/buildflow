"""GitHub metadata updater.

Fetches latest stars, forks, and last_commit_date for all GitHub content
from the GitHub REST API and updates Cosmos DB + AI Search.

Rate Limit:
  - Authenticated: 5,000 requests/hour
  - Safety: 1.5s delay between requests (GitHub secondary rate limit)
  - Monitors X-RateLimit-Remaining header; pauses if < 100
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import httpx
from azure.cosmos import CosmosClient, PartitionKey

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
COSMOS_CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING", "")
COSMOS_DATABASE_NAME = os.getenv("COSMOS_DATABASE_NAME", "buildflow")
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "")
SEARCH_INDEX_NAME = "buildflow-content"

# Rate-limit safety
REQUEST_DELAY_SECONDS = 1.5  # Delay between GitHub API calls
RATE_LIMIT_PAUSE_THRESHOLD = 100  # Pause when remaining < this


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _github_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "BuildFlow-MetadataRefresh/1.0",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def _parse_github_url(url: str) -> Optional[Tuple[str, str]]:
    """Extract (owner, repo) from a GitHub URL. Returns None on failure."""
    import re
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url.strip())
    return (m.group(1), m.group(2)) if m else None


# ─── Cosmos DB helpers ───────────────────────────────────────────────────────

def _get_container(database, container_name: str, pk_path: str = "/id"):
    return database.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path=pk_path),
    )


# ─── AI Search helpers ──────────────────────────────────────────────────────

async def _update_search_document(
    client: httpx.AsyncClient,
    content_id: str,
    stars: int,
    forks: int,
    last_commit_date: Optional[str],
) -> bool:
    """Merge-update a document in AI Search index."""
    if not AZURE_SEARCH_ENDPOINT or not AZURE_SEARCH_API_KEY:
        return False

    url = f"{AZURE_SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX_NAME}/docs/index?api-version=2024-07-01"
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_SEARCH_API_KEY,
    }
    doc: Dict[str, Any] = {
        "@search.action": "mergeOrUpload",
        "id": content_id,
        "stars": stars,
    }
    if last_commit_date:
        doc["last_commit_date"] = last_commit_date

    try:
        resp = await client.post(url, json={"value": [doc]}, headers=headers)
        if resp.status_code in (200, 201):
            return True
        logger.warning(f"AI Search update failed for {content_id}: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"AI Search update error for {content_id}: {e}")
    return False


# ─── Main logic ──────────────────────────────────────────────────────────────

async def refresh_github_metadata() -> Dict[str, Any]:
    """
    Refresh metadata for all GitHub contents.

    Returns summary dict with counts of successes, failures, and skips.
    """
    if not COSMOS_CONNECTION_STRING:
        return {"error": "COSMOS_CONNECTION_STRING not configured"}

    # Cosmos DB setup
    cosmos_client = CosmosClient.from_connection_string(COSMOS_CONNECTION_STRING)
    database = cosmos_client.create_database_if_not_exists(id=COSMOS_DATABASE_NAME)
    contents_container = _get_container(database, "contents")
    analysis_container = _get_container(database, "analysis_requests")

    # Fetch all GitHub content items
    query = "SELECT c.id, c.source_url, c.source_type, c.contributor_id, c.analysis_request_id, c.stars, c.forks FROM c WHERE c.source_type = 'github'"
    items = list(contents_container.query_items(
        query=query,
        enable_cross_partition_query=True,
    ))

    total = len(items)
    logger.info(f"Found {total} GitHub contents to refresh")

    if total == 0:
        return {"total": 0, "updated": 0, "failed": 0, "skipped": 0}

    updated = 0
    failed = 0
    skipped = 0
    rate_limit_remaining = 5000

    async with httpx.AsyncClient(timeout=30.0, headers=_github_headers()) as http_client:
        for i, item in enumerate(items):
            content_id: str = item.get("id", "")
            source_url = item.get("source_url", "")
            parsed = _parse_github_url(source_url)

            if not content_id or not parsed:
                logger.warning(f"[{i+1}/{total}] Invalid URL for {content_id}: {source_url}")
                skipped += 1
                continue

            owner, repo = parsed

            # Check rate limit
            if rate_limit_remaining < RATE_LIMIT_PAUSE_THRESHOLD:
                logger.warning(f"Rate limit low ({rate_limit_remaining}), pausing 60s...")
                await asyncio.sleep(60)

            try:
                # Fetch repo metadata from GitHub API
                resp = await http_client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}")
                rate_limit_remaining = int(resp.headers.get("X-RateLimit-Remaining", "5000"))

                if resp.status_code == 403 and rate_limit_remaining == 0:
                    logger.error("GitHub rate limit exceeded, stopping.")
                    break

                if resp.status_code == 404:
                    logger.warning(f"[{i+1}/{total}] Repo not found: {owner}/{repo}")
                    skipped += 1
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)
                    continue

                if resp.status_code != 200:
                    logger.warning(f"[{i+1}/{total}] GitHub API {resp.status_code} for {owner}/{repo}")
                    failed += 1
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)
                    continue

                data = resp.json()
                new_stars = data.get("stargazers_count", 0)
                new_forks = data.get("forks_count", 0)
                pushed_at = data.get("pushed_at")

                # Parse last_commit_date
                last_commit_dt = None
                last_commit_iso = None
                if pushed_at:
                    last_commit_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                    last_commit_iso = last_commit_dt.isoformat()

                # Skip if nothing changed
                old_stars = item.get("stars") or 0
                old_forks = item.get("forks") or 0
                if new_stars == old_stars and new_forks == old_forks:
                    logger.debug(f"[{i+1}/{total}] No change for {owner}/{repo}")
                    skipped += 1
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)
                    continue

                # ── Update 1: Cosmos DB contents container ───────────────
                full_item = contents_container.read_item(
                    item=content_id,
                    partition_key=content_id,
                )
                full_item["stars"] = new_stars
                full_item["forks"] = new_forks
                if last_commit_iso:
                    full_item["last_commit_date"] = last_commit_iso
                full_item["updated_at"] = datetime.now(timezone.utc).isoformat()
                contents_container.upsert_item(body=full_item)

                # ── Update 2: Cosmos DB analysis_requests container ──────
                analysis_request_id = item.get("analysis_request_id")
                if analysis_request_id:
                    try:
                        ar_query = "SELECT * FROM c WHERE c.id = @id"
                        ar_params = [{"name": "@id", "value": analysis_request_id}]
                        ar_items = list(analysis_container.query_items(
                            query=ar_query,
                            parameters=ar_params,
                            enable_cross_partition_query=True,
                        ))
                        if ar_items:
                            ar_item = ar_items[0]
                            if ar_item.get("result"):
                                ar_item["result"]["stars"] = new_stars
                                ar_item["result"]["forks"] = new_forks
                                if last_commit_iso:
                                    ar_item["result"]["last_commit_date"] = last_commit_iso
                                analysis_container.upsert_item(body=ar_item)
                    except Exception as e:
                        logger.warning(f"Failed to update analysis_request {analysis_request_id}: {e}")

                # ── Update 3: AI Search index ────────────────────────────
                await _update_search_document(
                    http_client, content_id, new_stars, new_forks, last_commit_iso
                )

                updated += 1
                logger.info(
                    f"[{i+1}/{total}] Updated {owner}/{repo}: "
                    f"stars {old_stars}→{new_stars}, forks {old_forks}→{new_forks} "
                    f"(remaining: {rate_limit_remaining})"
                )

            except Exception as e:
                logger.error(f"[{i+1}/{total}] Error refreshing {owner}/{repo}: {e}")
                failed += 1

            # Rate limit: 1.5s between requests
            await asyncio.sleep(REQUEST_DELAY_SECONDS)

    summary = {
        "total": total,
        "updated": updated,
        "failed": failed,
        "skipped": skipped,
        "rate_limit_remaining": rate_limit_remaining,
    }
    logger.info(f"GitHub refresh complete: {summary}")
    return summary
