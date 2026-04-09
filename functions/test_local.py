#!/usr/bin/env python3
"""
Local test runner for Azure Functions metadata refresh.

Fetches credentials from Azure CLI and runs the updaters locally.
Usage:
  python test_local.py              # Run both
  python test_local.py github       # GitHub only
  python test_local.py youtube      # YouTube only
  python test_local.py github --dry # Dry run (read only, no updates)
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def az_cli(cmd: str) -> str:
    """Run an az CLI command and return stdout."""
    result = subprocess.run(
        f"az {cmd}",
        shell=True,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ⚠ az CLI error: {result.stderr.strip()}")
        return ""
    return result.stdout.strip()


def load_env_from_dotenv():
    """Load environment variables from backend/.env.local if available."""
    dotenv_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "backend", ".env.local"
    )
    if os.path.exists(dotenv_path):
        with open(dotenv_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())
        return True
    return False


def load_env_from_azure():
    """Load environment variables from .env.local first, then Azure CLI as fallback."""
    rg = "rg-buildflow-dev"

    # Try .env.local first
    if load_env_from_dotenv():
        print("🔑 Loaded credentials from backend/.env.local")
        for name in ("COSMOS_CONNECTION_STRING", "COSMOS_DATABASE_NAME",
                      "GITHUB_TOKEN", "YOUTUBE_API_KEY",
                      "AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_API_KEY"):
            val = os.environ.get(name, "")
            if val:
                masked = val[:8] + "..." if len(val) > 8 else "***"
                print(f"  ✅ {name}: {masked}")
            else:
                print(f"  ⚠ {name}: (empty)")
        print()
        return

    print("🔑 Loading credentials from Azure CLI (no .env.local found)...")

    # Cosmos DB
    cosmos_name = az_cli(
        f"cosmosdb list --resource-group {rg} --query \"[0].name\" -o tsv"
    )
    if cosmos_name:
        conn_str = az_cli(
            f"cosmosdb keys list --name {cosmos_name} --resource-group {rg} "
            f"--type connection-strings --query \"connectionStrings[0].connectionString\" -o tsv"
        )
        if conn_str:
            os.environ["COSMOS_CONNECTION_STRING"] = conn_str
            print(f"  ✅ Cosmos DB: {cosmos_name}")
        else:
            print("  ❌ Failed to get Cosmos DB connection string")
    else:
        print("  ❌ No Cosmos DB account found")

    os.environ["COSMOS_DATABASE_NAME"] = "buildflow"

    # Function App settings (GitHub Token, YouTube API Key, Search)
    func_name = az_cli(
        f"functionapp list --resource-group {rg} "
        f"--query \"[?contains(name, 'func-')].name\" -o tsv"
    )
    if func_name:
        settings = az_cli(
            f"functionapp config appsettings list --name {func_name} "
            f"--resource-group {rg} -o json"
        )
        if settings:
            for item in json.loads(settings):
                name = item.get("name", "")
                value = item.get("value", "")
                if name in ("GITHUB_TOKEN", "YOUTUBE_API_KEY",
                            "AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_API_KEY"):
                    if value:
                        os.environ[name] = value
                        masked = value[:8] + "..." if len(value) > 8 else "***"
                        print(f"  ✅ {name}: {masked}")
                    else:
                        print(f"  ⚠ {name}: (empty)")

    print()


async def run_test(source: str, dry_run: bool = False):
    """Run the metadata refresh test."""
    load_env_from_azure()

    # Verify minimum requirements
    if not os.environ.get("COSMOS_CONNECTION_STRING"):
        print("❌ COSMOS_CONNECTION_STRING is required. Aborting.")
        sys.exit(1)

    start = datetime.now(timezone.utc)
    print(f"🚀 Starting metadata refresh test at {start.isoformat()}")
    print(f"   Source: {source}, Dry run: {dry_run}")
    print("=" * 60)

    # Add functions directory to path
    func_dir = os.path.dirname(os.path.abspath(__file__))
    if func_dir not in sys.path:
        sys.path.insert(0, func_dir)

    github_result = None
    youtube_result = None

    if source in ("both", "github"):
        print("\n📦 GitHub Metadata Refresh")
        print("-" * 40)

        if dry_run:
            # Dry run: only read, don't update
            from github_updater import (
                GITHUB_API_BASE,
                _github_headers,
                _parse_github_url,
            )
            from azure.cosmos import CosmosClient, PartitionKey
            import httpx

            cosmos_client = CosmosClient.from_connection_string(
                os.environ["COSMOS_CONNECTION_STRING"]
            )
            database = cosmos_client.create_database_if_not_exists(
                id=os.environ.get("COSMOS_DATABASE_NAME", "buildflow")
            )
            container = database.create_container_if_not_exists(
                id="contents",
                partition_key=PartitionKey(path="/id"),
            )
            query = "SELECT c.id, c.source_url, c.source_type, c.stars, c.forks, c.title FROM c WHERE c.source_type = 'github'"
            items = list(container.query_items(query=query, enable_cross_partition_query=True))
            print(f"  Found {len(items)} GitHub contents")

            # Test one item
            if items:
                item = items[0]
                parsed = _parse_github_url(item.get("source_url", ""))
                if parsed:
                    owner, repo = parsed
                    async with httpx.AsyncClient(timeout=30.0, headers=_github_headers()) as client:
                        resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}")
                        remaining = resp.headers.get("X-RateLimit-Remaining", "?")
                        if resp.status_code == 200:
                            data = resp.json()
                            print(f"  Sample: {owner}/{repo}")
                            print(f"    Title: {item.get('title', 'N/A')[:50]}")
                            print(f"    Stars: {item.get('stars', 0)} → {data.get('stargazers_count', 0)}")
                            print(f"    Forks: {item.get('forks', 0)} → {data.get('forks_count', 0)}")
                            print(f"    Last push: {data.get('pushed_at', 'N/A')}")
                            print(f"    Rate limit remaining: {remaining}")
                        else:
                            print(f"  ⚠ GitHub API returned {resp.status_code}")

            github_result = {"mode": "dry_run", "total": len(items)}
        else:
            from github_updater import refresh_github_metadata
            github_result = await refresh_github_metadata()

        print(f"\n  Result: {json.dumps(github_result, indent=2)}")

    if source in ("both", "youtube"):
        print("\n📺 YouTube Metadata Refresh")
        print("-" * 40)

        if not os.environ.get("YOUTUBE_API_KEY"):
            print("  ⚠ YOUTUBE_API_KEY not set, skipping YouTube refresh")
            youtube_result = {"skipped": True, "reason": "No API key"}
        elif dry_run:
            from youtube_updater import _extract_video_id
            from azure.cosmos import CosmosClient, PartitionKey
            import httpx

            cosmos_client = CosmosClient.from_connection_string(
                os.environ["COSMOS_CONNECTION_STRING"]
            )
            database = cosmos_client.create_database_if_not_exists(
                id=os.environ.get("COSMOS_DATABASE_NAME", "buildflow")
            )
            container = database.create_container_if_not_exists(
                id="youtube_contents",
                partition_key=PartitionKey(path="/id"),
            )
            query = "SELECT c.id, c.source_url, c.video_id, c.view_count, c.like_count, c.title FROM c WHERE c.source_type = 'youtube'"
            items = list(container.query_items(query=query, enable_cross_partition_query=True))
            print(f"  Found {len(items)} YouTube contents")

            # Test one batch
            if items:
                video_ids = []
                for it in items[:5]:
                    vid = it.get("video_id") or _extract_video_id(it.get("source_url", ""))
                    if vid:
                        video_ids.append((vid, it))

                if video_ids:
                    ids_str = ",".join(v[0] for v in video_ids)
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.get(
                            "https://www.googleapis.com/youtube/v3/videos",
                            params={
                                "part": "statistics",
                                "id": ids_str,
                                "key": os.environ["YOUTUBE_API_KEY"],
                            },
                        )
                        if resp.status_code == 200:
                            api_data = resp.json()
                            api_items = {v["id"]: v for v in api_data.get("items", [])}
                            for vid, it in video_ids:
                                api_item = api_items.get(vid, {})
                                stats = api_item.get("statistics", {})
                                print(f"  Sample: {it.get('title', 'N/A')[:50]}")
                                print(f"    Views: {it.get('view_count', 0)} → {stats.get('viewCount', '?')}")
                                print(f"    Likes: {it.get('like_count', 0)} → {stats.get('likeCount', '?')}")
                            print(f"  Quota used: 1 unit (for {len(video_ids)} videos)")
                        elif resp.status_code == 403:
                            print(f"  ⚠ YouTube API quota/auth error: {resp.text[:200]}")
                        else:
                            print(f"  ⚠ YouTube API returned {resp.status_code}")

            youtube_result = {"mode": "dry_run", "total": len(items)}
        else:
            from youtube_updater import refresh_youtube_metadata
            youtube_result = await refresh_youtube_metadata()

        print(f"\n  Result: {json.dumps(youtube_result, indent=2)}")

    end = datetime.now(timezone.utc)
    duration = (end - start).total_seconds()
    print("\n" + "=" * 60)
    print(f"✅ Test completed in {duration:.1f}s")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "both"
    dry_run = "--dry" in sys.argv

    if source not in ("both", "github", "youtube"):
        print("Usage: python test_local.py [both|github|youtube] [--dry]")
        sys.exit(1)

    asyncio.run(run_test(source, dry_run))
