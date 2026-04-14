import logging
from datetime import datetime, timezone
import gspread
from google.oauth2.service_account import Credentials
from config import (
    GOOGLE_CREDENTIALS_FILE, GOOGLE_SPREADSHEET_ID,
    SHEET_CHANNELS, SHEET_VIDEOS, SHEET_LEADS, SHEET_RUN_LOG, SHEET_TOP10,
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ------------------------------------------------------------------
# Recommended column indexes for each sheet
# ------------------------------------------------------------------

CHANNEL_HEADERS = [
    "channel_id", "title", "custom_url", "country",
    "subscriber_count", "view_count", "video_count",
    "published_at", "description",
    "thumbnail_default", "thumbnail_medium", "thumbnail_high",
    "banner_url", "keywords",
    "email", "email_source",
    "scraped_at",
]

VIDEO_HEADERS = [
    "video_id", "channel_id", "title",
    "published_at", "duration",
    "view_count", "like_count", "comment_count",
    "category_id", "category_name", "live_broadcast_status",
    "tags", "description",
    "thumbnail_default", "thumbnail_medium", "thumbnail_high",
    "email", "email_source",
    "scraped_at",
]

LEAD_HEADERS = [
    "email", "source_type", "source_id", "source_title",
    "channel_id", "subscriber_count", "country",
    "discovered_at",
]

RUN_LOG_HEADERS = [
    "run_id", "started_at", "finished_at",
    "keyword", "channels_processed", "videos_processed",
    "leads_found", "quota_used", "status", "notes",
]

TOP10_HEADERS = [
    "rank", "video_id", "title", "channel_title",
    "published_at", "view_count", "like_count", "comment_count",
    "duration", "category_name", "region",
    "video_url", "thumbnail_high",
    "fetched_at",
]


class SheetsClient:
    def __init__(self):
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
        )
        self.client = gspread.Client(auth=creds)
        self.spreadsheet = self.client.open_by_key(GOOGLE_SPREADSHEET_ID)
        self._ensure_sheets()

    # ------------------------------------------------------------------
    # Sheet setup
    # ------------------------------------------------------------------

    def _ensure_sheets(self):
        """Create sheets with headers if they do not exist."""
        existing = {ws.title for ws in self.spreadsheet.worksheets()}
        for name, headers in [
            (SHEET_CHANNELS, CHANNEL_HEADERS),
            (SHEET_VIDEOS, VIDEO_HEADERS),
            (SHEET_LEADS, LEAD_HEADERS),
            (SHEET_RUN_LOG, RUN_LOG_HEADERS),
            (SHEET_TOP10, TOP10_HEADERS),
        ]:
            if name not in existing:
                ws = self.spreadsheet.add_worksheet(title=name, rows=5000, cols=len(headers))
                ws.append_row(headers, value_input_option="RAW")
                self._format_header(ws)
                logger.info(f"Created sheet: {name}")
            else:
                logger.info(f"Sheet already exists: {name}")

    def _format_header(self, ws: gspread.Worksheet):
        """Bold and freeze the header row."""
        ws.format("1:1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)

    # ------------------------------------------------------------------
    # Existing ID lookup (deduplication)
    # ------------------------------------------------------------------

    def _get_existing_ids(self, sheet_name: str, id_column: str) -> set:
        ws = self.spreadsheet.worksheet(sheet_name)
        headers = ws.row_values(1)
        if id_column not in headers:
            return set()
        col_idx = headers.index(id_column) + 1
        values = ws.col_values(col_idx)[1:]   # skip header
        return set(v for v in values if v)

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def write_channels(self, channels: list[dict]) -> int:
        """Append new channels, skip duplicates. Returns count written."""
        ws = self.spreadsheet.worksheet(SHEET_CHANNELS)
        existing_ids = self._get_existing_ids(SHEET_CHANNELS, "channel_id")
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for ch in channels:
            if ch.get("channel_id") in existing_ids:
                logger.info(f"Skip duplicate channel: {ch.get('channel_id')}")
                continue
            ch["scraped_at"] = now
            rows.append([str(ch.get(h) or "") for h in CHANNEL_HEADERS])
        if rows:
            ws.append_rows(rows, value_input_option="RAW")
        logger.info(f"Wrote {len(rows)} new channels")
        return len(rows)

    def write_videos(self, videos: list[dict]) -> int:
        """Append new videos, skip duplicates. Returns count written."""
        ws = self.spreadsheet.worksheet(SHEET_VIDEOS)
        existing_ids = self._get_existing_ids(SHEET_VIDEOS, "video_id")
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for v in videos:
            if v.get("video_id") in existing_ids:
                continue
            v["scraped_at"] = now
            rows.append([str(v.get(h) or "") for h in VIDEO_HEADERS])
        if rows:
            ws.append_rows(rows, value_input_option="RAW")
        logger.info(f"Wrote {len(rows)} new videos")
        return len(rows)

    def write_leads(self, leads: list[dict]) -> int:
        """Append new unique email leads. Returns count written."""
        ws = self.spreadsheet.worksheet(SHEET_LEADS)
        existing_emails = self._get_existing_ids(SHEET_LEADS, "email")
        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for lead in leads:
            if not lead.get("email") or lead["email"] in existing_emails:
                continue
            existing_emails.add(lead["email"])
            lead["discovered_at"] = now
            rows.append([str(lead.get(h) or "") for h in LEAD_HEADERS])
        if rows:
            ws.append_rows(rows, value_input_option="RAW")
        logger.info(f"Wrote {len(rows)} new leads")
        return len(rows)

    def write_run_log(self, log: dict):
        """Append a run summary row to Run_Log sheet."""
        ws = self.spreadsheet.worksheet(SHEET_RUN_LOG)
        ws.append_row(
            [str(log.get(h) or "") for h in RUN_LOG_HEADERS],
            value_input_option="RAW",
        )

    def write_top10(self, videos: list[dict]) -> int:
        """Overwrite Top10_Entertainment sheet with today's ranked list.

        The sheet is cleared first so each run reflects the latest snapshot.
        Returns the number of rows written.
        """
        ws = self.spreadsheet.worksheet(SHEET_TOP10)
        # Clear existing data below header
        ws.clear()
        ws.append_row(TOP10_HEADERS, value_input_option="RAW")
        self._format_header(ws)

        now = datetime.now(timezone.utc).isoformat()
        rows = []
        for v in videos:
            v["fetched_at"] = now
            rows.append([str(v.get(h) or "") for h in TOP10_HEADERS])

        if rows:
            ws.append_rows(rows, value_input_option="RAW")
        logger.info(f"Wrote {len(rows)} rows to {SHEET_TOP10}")
        return len(rows)
