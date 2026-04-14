"""
find_lead.py — YouTube Lead Extraction RPA
------------------------------------------
Crawls YouTube channels and videos by keyword,
extracts metadata and email addresses,
then writes results to Google Spreadsheet.

Usage:
    python find_lead.py

Config:
    All parameters are loaded from .env (see config.py)
"""

import logging
import uuid
from datetime import datetime, timezone

from config import (
    SEARCH_KEYWORD, MAX_CHANNELS, MIN_SUBSCRIBER_COUNT,
)
from youtube_client import YouTubeClient
from sheets_client import SheetsClient

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("find_lead.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Lead builder
# ------------------------------------------------------------------

def build_leads(channels: list[dict], videos: list[dict]) -> list[dict]:
    """Collect all email addresses found across channels and videos."""
    leads = []

    for ch in channels:
        if ch.get("email"):
            for email in ch["email"].split("|"):
                leads.append({
                    "email": email.strip(),
                    "source_type": "channel",
                    "source_id": ch.get("channel_id"),
                    "source_title": ch.get("title"),
                    "channel_id": ch.get("channel_id"),
                    "subscriber_count": ch.get("subscriber_count"),
                    "country": ch.get("country"),
                })

    for v in videos:
        if v.get("email"):
            for email in v["email"].split("|"):
                leads.append({
                    "email": email.strip(),
                    "source_type": "video",
                    "source_id": v.get("video_id"),
                    "source_title": v.get("title"),
                    "channel_id": v.get("channel_id"),
                    "subscriber_count": None,
                    "country": None,
                })

    return leads


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    run_id = str(uuid.uuid4())[:8]
    started_at = datetime.now(timezone.utc).isoformat()
    logger.info(f"=== Run {run_id} started at {started_at} ===")
    logger.info(f"Keyword: '{SEARCH_KEYWORD}' | Max channels: {MAX_CHANNELS} | Min subscribers: {MIN_SUBSCRIBER_COUNT}")

    status = "success"
    notes = ""
    channels_written = 0
    videos_written = 0
    leads_written = 0
    quota_used = 0
    yt = None
    sheets = None

    try:
        yt = YouTubeClient()
        sheets = SheetsClient()

        # Step 1: Search channel IDs
        logger.info("Step 1: Searching channels...")
        channel_ids = yt.search_channels(SEARCH_KEYWORD, max_results=MAX_CHANNELS)

        # Step 2: Fetch full channel metadata
        logger.info(f"Step 2: Fetching metadata for {len(channel_ids)} channels...")
        channels = yt.fetch_channels(channel_ids)

        # Step 3: Filter by minimum subscriber count
        before_filter = len(channels)
        channels = [
            ch for ch in channels
            if ch.get("subscriber_count") is None
            or int(ch.get("subscriber_count") or 0) >= MIN_SUBSCRIBER_COUNT
        ]
        logger.info(f"Step 3: Filtered {before_filter - len(channels)} channels below subscriber threshold. Remaining: {len(channels)}")

        # Step 4: Write channels to Spreadsheet
        logger.info("Step 4: Writing channels to Spreadsheet...")
        channels_written = sheets.write_channels(channels)

        # Step 5: Fetch videos for each channel
        logger.info("Step 5: Fetching videos per channel...")
        all_videos = []
        for ch in channels:
            ch_id = ch.get("channel_id")
            try:
                videos = yt.fetch_videos_for_channel(ch_id)
                all_videos.extend(videos)
                logger.info(f"  Channel {ch_id}: {len(videos)} videos fetched")
            except RuntimeError as e:
                logger.error(f"  Quota halt during video fetch: {e}")
                status = "partial"
                notes = str(e)
                break

        # Step 6: Write videos to Spreadsheet
        logger.info(f"Step 6: Writing {len(all_videos)} videos to Spreadsheet...")
        videos_written = sheets.write_videos(all_videos)

        # Step 7: Extract and write leads
        logger.info("Step 7: Extracting and writing leads...")
        leads = build_leads(channels, all_videos)
        leads_written = sheets.write_leads(leads)

        quota_used = yt.quota_used

    except RuntimeError as e:
        logger.error(f"Fatal error: {e}")
        status = "failed"
        notes = str(e)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        status = "failed"
        notes = str(e)

    finally:
        finished_at = datetime.now(timezone.utc).isoformat()

        # Step 8: Write run log
        try:
            if sheets:
                run_log = {
                    "run_id": run_id,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "keyword": SEARCH_KEYWORD,
                    "channels_processed": channels_written,
                    "videos_processed": videos_written,
                    "leads_found": leads_written,
                    "quota_used": quota_used,
                    "status": status,
                    "notes": notes,
                }
                sheets.write_run_log(run_log)
        except Exception as log_err:
            logger.warning(f"Could not write run log: {log_err}")

        logger.info(
            f"=== Run {run_id} finished | "
            f"Status: {status} | "
            f"Channels: {channels_written} | "
            f"Videos: {videos_written} | "
            f"Leads: {leads_written} | "
            f"Quota used: {quota_used} ==="
        )


if __name__ == "__main__":
    main()
