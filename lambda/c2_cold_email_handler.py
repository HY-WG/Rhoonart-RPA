# -*- coding: utf-8 -*-
"""C-2 Lambda entrypoint for cold email delivery."""
from __future__ import annotations

import os
import sys

import gspread
from src.api.deps import build_google_creds

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.error_handler import task_handler
from src.core.logger import CoreLogger
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.repositories.sheet_repository import SheetLeadRepository, SheetLogRepository
from src.core.repositories.supabase_repository import SupabaseLeadRepository, SupabaseLogRepository
from src.handlers.c2_cold_email import TASK_ID, TASK_NAME, run as c2_run
from src.models.lead import Genre
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

C_LEAD_REPOSITORY_TYPE = os.environ.get("C_LEAD_REPOSITORY_TYPE", "supabase").lower()
LEAD_SHEET_ID = os.environ.get("LEAD_SHEET_ID", "")
LOG_SHEET_ID = os.environ.get("LOG_SHEET_ID", LEAD_SHEET_ID)
CREDS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")

SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH = os.environ["SLACK_ERROR_CHANNEL"]

SENDER_EMAIL = os.environ["SENDER_EMAIL"]
SENDER_NAME = os.environ.get("SENDER_NAME", "루나트")
USE_SES = os.environ.get("USE_SES", "true").lower() == "true"

TAB_LEADS = os.environ.get("TAB_LEADS", "리드")
TAB_LOG = os.environ.get("TAB_LOG", "로그")

DEFAULT_BATCH_SIZE = int(os.environ.get("C2_BATCH_SIZE", "50"))
DEFAULT_MIN_VIEWS = int(os.environ.get("C2_MIN_MONTHLY_VIEWS", "0"))

_GENRE_MAP = {
    "예능": Genre.ENTERTAINMENT,
    "드라마·영화": Genre.DRAMA_MOVIE,
    "드라마/영화": Genre.DRAMA_MOVIE,
    "기타": Genre.OTHER,
}


def _build_deps():
    if C_LEAD_REPOSITORY_TYPE == "supabase":
        from supabase import create_client  # type: ignore

        supabase_url = os.environ["SUPABASE_URL"]
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
        client = create_client(supabase_url, supabase_key)
        lead_repo = SupabaseLeadRepository(client)
        log_repo = SupabaseLogRepository(client)
    else:
        creds = build_google_creds(CREDS_FILE, _SCOPES)
        gc = gspread.authorize(creds)
        lead_sh = gc.open_by_key(LEAD_SHEET_ID)
        log_sh = gc.open_by_key(LOG_SHEET_ID)
        lead_repo = SheetLeadRepository(lead_sh.worksheet(TAB_LEADS))
        log_repo = SheetLogRepository(log_sh.worksheet(TAB_LOG))

    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)
    email_notifier = EmailNotifier(sender_email=SENDER_EMAIL, use_ses=USE_SES)
    return lead_repo, log_repo, slack_notifier, email_notifier


def handler(event: dict, context) -> dict:
    batch_size = int(event.get("batch_size", DEFAULT_BATCH_SIZE))
    min_views = int(event.get("min_monthly_views", DEFAULT_MIN_VIEWS))
    raw_genre = event.get("genre")
    raw_platform = event.get("platform")
    dry_run = str(event.get("dry_run", "true")).lower() == "true"

    genre = _GENRE_MAP.get(raw_genre) if raw_genre else None
    platform = raw_platform if raw_platform else None

    if raw_genre and genre is None:
        raise ValueError(f"알 수 없는 genre 값: {raw_genre!r}. 예능 / 드라마·영화 / 기타 중 하나여야 합니다.")

    lead_repo, log_repo, slack_notifier, email_notifier = _build_deps()

    @task_handler(
        task_id=TASK_ID,
        task_name=TASK_NAME,
        trigger_type=TriggerType.MANUAL,
        trigger_source=event.get("_trigger_source", "manual"),
        log_repo=log_repo,
        slack_notifier=slack_notifier,
    )
    def _run(*_):
        return c2_run(
            lead_repo=lead_repo,
            log_repo=log_repo,
            email_notifier=email_notifier,
            slack_notifier=slack_notifier,
            sender_name=SENDER_NAME,
            batch_size=batch_size,
            genre=genre,
            min_monthly_views=min_views,
            platform=platform,
            dry_run=dry_run,
        )

    return _run(event, context)


if __name__ == "__main__":
    result = handler({}, None)
    print(result)
