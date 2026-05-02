# -*- coding: utf-8 -*-
"""B-2 Lambda entrypoint for Naver Clip performance reporting."""

from __future__ import annotations

import json
import os
import sys

import gspread

from src.api.deps import build_google_creds

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.error_handler import task_handler
from src.core.logger import CoreLogger
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.repositories.b2_sheet_performance_repository import B2SheetPerformanceRepository
from src.core.repositories.sheet_repository import SheetLogRepository
from src.core.repositories.supabase_b2_repository import SupabaseNaverRepository
from src.handlers.b2_weekly_report import TASK_ID, TASK_NAME, run as b2_run
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CONTENT_SHEET_ID = os.environ["CONTENT_SHEET_ID"]
PERFORMANCE_SHEET_ID = os.environ.get("PERFORMANCE_SHEET_ID", CONTENT_SHEET_ID)
LOG_SHEET_ID = os.environ.get("LOG_SHEET_ID", CONTENT_SHEET_ID)
CREDS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH = os.environ["SLACK_ERROR_CHANNEL"]
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
USE_SES = os.environ.get("USE_SES", "true").lower() == "true"
NAVER_REPORT_REPOSITORY_TYPE = os.environ.get("NAVER_REPORT_REPOSITORY_TYPE", "supabase")

TAB_CONTENT = os.environ.get("TAB_CONTENT_B2", "A3_작품리스트의 사본")
TAB_STATS = os.environ.get("TAB_B2_REPORTS", "A3_NAVERCLIP_성과보고")
TAB_RIGHTS = os.environ.get("TAB_RIGHTS", "A3_작품 관리의 사본")
TAB_MANAGEMENT = os.environ.get("TAB_CONTENT_MANAGEMENT", "A3_작품 관리의 사본")
TAB_LOG = os.environ.get("TAB_LOG", "COMMON_log_records")


def _build_sheet_perf_repo() -> B2SheetPerformanceRepository:
    creds = build_google_creds(CREDS_FILE, _SCOPES)
    gc = gspread.authorize(creds)

    workbook = gc.open_by_key(CONTENT_SHEET_ID)
    return B2SheetPerformanceRepository(
        content_ws=workbook.worksheet(TAB_CONTENT),
        stats_ws=workbook.worksheet(TAB_STATS),
        rights_ws=workbook.worksheet(TAB_RIGHTS),
        management_ws=workbook.worksheet(TAB_MANAGEMENT),
    )


def _build_supabase_perf_repo() -> SupabaseNaverRepository:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Naver reports")
    return SupabaseNaverRepository(
        supabase_url=supabase_url,
        service_role_key=service_role_key,
    )


def _build_deps():
    creds = build_google_creds(CREDS_FILE, _SCOPES)
    gc = gspread.authorize(creds)

    log_book = gc.open_by_key(LOG_SHEET_ID)
    perf_repo = _build_sheet_perf_repo() if NAVER_REPORT_REPOSITORY_TYPE == "sheets" else _build_supabase_perf_repo()
    log_repo = SheetLogRepository(log_book.worksheet(TAB_LOG))

    email_notifier = EmailNotifier(sender_email=SENDER_EMAIL, use_ses=USE_SES)
    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)
    return perf_repo, log_repo, email_notifier, slack_notifier


def handler(event: dict, context) -> dict:
    if "body" in event and isinstance(event["body"], str):
        try:
            body = json.loads(event["body"])
            event = {**event, **body}
        except json.JSONDecodeError:
            pass

    source = event.get("source", "http")
    trigger_type = TriggerType.CRON if source == "cron" else TriggerType.HTTP
    trigger_source = "EventBridge weekly cron" if source == "cron" else "HTTP Request"

    perf_repo, log_repo, email_notifier, slack_notifier = _build_deps()

    @task_handler(
        task_id=TASK_ID,
        task_name=TASK_NAME,
        trigger_type=trigger_type,
        trigger_source=trigger_source,
        log_repo=log_repo,
        slack_notifier=slack_notifier,
    )
    def _run(*_):
        return b2_run(
            perf_repo=perf_repo,
            log_repo=log_repo,
            email_notifier=email_notifier,
            slack_notifier=slack_notifier,
            headless=True,
            send_notifications=bool(event.get("send_notifications", True)),
        )

    result = _run(event, context)
    return {"statusCode": 200, "body": json.dumps(result, ensure_ascii=False)}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    print(handler({"source": "manual", "send_notifications": False}, None))
