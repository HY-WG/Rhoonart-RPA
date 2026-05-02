from __future__ import annotations

import json
import os
import sys

import gspread

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.deps import build_google_creds
from src.config import settings
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.repositories.supabase_b2_repository import SupabaseB2Repository
from src.services.b2_test_report_service import B2TestReportService

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
DEFAULT_RECIPIENT = "kirby.lee@laeebly.com"


def _build_service(max_clips: int) -> B2TestReportService:
    creds = build_google_creds(settings.GOOGLE_CREDENTIALS_FILE, _SCOPES)
    return B2TestReportService(
        repository=SupabaseB2Repository(
            supabase_url=settings.SUPABASE_URL,
            service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
            timeout=60.0,
        ),
        sheets_client=gspread.authorize(creds),
        email_notifier=EmailNotifier(
            sender_email=settings.SENDER_EMAIL,
            use_ses=settings.USE_SES,
        ),
        max_clips_per_identifier=max_clips,
    )


def handler(event: dict, context) -> dict:
    del context
    recipient = event.get("recipient", DEFAULT_RECIPIENT)
    max_clips = int(event.get("max_clips", os.getenv("B2_TEST_MAX_CLIPS", "2000")))
    share_sheets = bool(event.get("share_sheets", True))
    send_email = bool(event.get("send_email", True))
    seed = bool(event.get("seed", True))
    triggered_by = event.get("triggered_by", "schedule")

    service = _build_service(max_clips)
    result: dict[str, object] = {}
    if seed:
        result["seed"] = service.seed_requested_rows(recipient_email=recipient)
    rows = service.collect_enabled_reports(triggered_by=triggered_by)
    result["collected_rows"] = len(rows)
    sheet_urls = service.publish_holder_sheets(
        rows,
        share_with=recipient if share_sheets else None,
    )
    result["sheet_urls"] = sheet_urls
    if send_email:
        result["email_sent"] = service.send_email(
            recipient=recipient,
            rows=rows,
            holder_sheet_urls=sheet_urls,
            looker_urls=service.get_enabled_looker_urls(),
        )
    return {"statusCode": 200, "body": json.dumps(result, ensure_ascii=False)}
