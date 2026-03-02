"""Azure Functions – Daily Metadata Refresh (Timer Trigger).

Runs daily at KST 02:00 (UTC 17:00) to refresh:
  1. GitHub content: stars, forks, last_commit_date
  2. YouTube content: view_count, like_count, comment_count

Uses Python v2 programming model for Azure Functions.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import azure.functions as func

from github_updater import refresh_github_metadata
from youtube_updater import refresh_youtube_metadata

# ─── App setup ───────────────────────────────────────────────────────────────

app = func.FunctionApp()
logger = logging.getLogger(__name__)


# ─── Timer Trigger ───────────────────────────────────────────────────────────
# CRON expression: "0 0 17 * * *" → every day at 17:00 UTC = 02:00 KST
# Format: {second} {minute} {hour} {day} {month} {day-of-week}

@app.timer_trigger(
    schedule="0 0 17 * * *",
    arg_name="timer",
    run_on_startup=False,
)
def daily_metadata_refresh(timer: func.TimerRequest) -> None:
    """
    Daily metadata refresh for GitHub and YouTube content.

    Runs at KST 02:00 (UTC 17:00) every day.
    Updates stars/forks/views/likes across Cosmos DB and AI Search.
    """
    start_time = datetime.now(timezone.utc)
    logger.info(f"=== Daily Metadata Refresh started at {start_time.isoformat()} ===")

    if timer.past_due:
        logger.warning("Timer is past due! Running catch-up refresh.")

    # Run both updaters
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        github_result = loop.run_until_complete(refresh_github_metadata())
        youtube_result = loop.run_until_complete(refresh_youtube_metadata())
    finally:
        loop.close()

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    summary = {
        "started_at": start_time.isoformat(),
        "finished_at": end_time.isoformat(),
        "duration_seconds": round(duration, 1),
        "github": github_result,
        "youtube": youtube_result,
    }

    logger.info(f"=== Daily Metadata Refresh complete in {duration:.1f}s ===")
    logger.info(f"Summary: {json.dumps(summary, indent=2)}")


# ─── HTTP Trigger (Manual Run) ───────────────────────────────────────────────
# For testing and manual execution via HTTP request

@app.route(
    route="refresh-metadata",
    methods=["POST"],
    auth_level=func.AuthLevel.FUNCTION,
)
def manual_metadata_refresh(req: func.HttpRequest) -> func.HttpResponse:
    """
    Manual trigger for metadata refresh.

    POST /api/refresh-metadata
    Optional query param: source=github|youtube (default: both)
    Requires function key for authentication.
    """
    start_time = datetime.now(timezone.utc)
    source = req.params.get("source", "both")
    logger.info(f"Manual metadata refresh triggered: source={source}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        github_result = None
        youtube_result = None

        if source in ("both", "github"):
            github_result = loop.run_until_complete(refresh_github_metadata())

        if source in ("both", "youtube"):
            youtube_result = loop.run_until_complete(refresh_youtube_metadata())
    finally:
        loop.close()

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    summary = {
        "started_at": start_time.isoformat(),
        "finished_at": end_time.isoformat(),
        "duration_seconds": round(duration, 1),
        "github": github_result,
        "youtube": youtube_result,
    }

    return func.HttpResponse(
        body=json.dumps(summary, indent=2),
        mimetype="application/json",
        status_code=200,
    )
