from __future__ import annotations

import argparse
import json
import os
import sys

import gspread
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.deps import build_google_creds
from src.config import settings
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.repositories.supabase_b2_repository import SupabaseB2Repository
from src.services.b2_test_report_service import B2TestReportService

DEFAULT_RECIPIENT = "kirby.lee@laeebly.com"
_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def build_service(*, enable_google: bool, enable_email: bool, max_clips: int) -> B2TestReportService:
    repository = SupabaseB2Repository(
        supabase_url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
        timeout=60.0,
    )
    sheets_client = None
    if enable_google:
        creds = build_google_creds(settings.GOOGLE_CREDENTIALS_FILE, _SCOPES)
        sheets_client = gspread.authorize(creds)

    email_notifier = None
    if enable_email:
        email_notifier = EmailNotifier(
            sender_email=settings.SENDER_EMAIL,
            use_ses=settings.USE_SES,
        )

    return B2TestReportService(
        repository=repository,
        sheets_client=sheets_client,
        email_notifier=email_notifier,
        max_clips_per_identifier=max_clips,
    )


def main() -> None:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Run B-2 test report workflow.")
    parser.add_argument("--check-db", action="store_true")
    parser.add_argument("--recipient", default=DEFAULT_RECIPIENT)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--create-sheets", action="store_true")
    parser.add_argument("--share-sheets", action="store_true")
    parser.add_argument("--send-email", action="store_true")
    parser.add_argument("--max-clips", type=int, default=int(os.getenv("B2_TEST_MAX_CLIPS", "2000")))
    parser.add_argument("--triggered-by", choices=["manual", "schedule", "api"], default="manual")
    args = parser.parse_args()

    if args.check_db:
        base = settings.SUPABASE_URL.rstrip("/")
        headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Prefer": "count=exact",
        }
        tables = [
            "b2_content_catalog",
            "b2_rights_holders",
            "b2_clip_reports",
            "b2_clip_reports_test",
            "b2_clip_report_runs",
            "b2_clip_reports_daily",
            "b2_clip_reports_year",
            "v_b2_clip_reports_daily_latest",
            "v_b2_clip_reports_daily_history",
        ]
        status: dict[str, object] = {"supabase_url": base, "tables": {}}
        for table in tables:
            response = requests.get(
                f"{base}/rest/v1/{table}?select=*&limit=1",
                headers=headers,
                timeout=20,
            )
            if response.ok:
                count = response.headers.get("content-range", "").split("/")[-1]
                status["tables"][table] = {"status": "ok", "rows": count}
            else:
                status["tables"][table] = {
                    "status": response.status_code,
                    "message": response.text[:200],
                }
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return

    enable_google = args.create_sheets
    enable_email = args.send_email
    service = build_service(
        enable_google=enable_google,
        enable_email=enable_email,
        max_clips=args.max_clips,
    )

    result: dict[str, object] = {}
    if args.seed:
        result["seed"] = service.seed_requested_rows(recipient_email=args.recipient)

    rows = []
    if args.collect:
        rows = service.collect_enabled_reports(triggered_by=args.triggered_by)
        result["collected_rows"] = len(rows)

    sheet_urls = {}
    if args.create_sheets:
        sheet_urls = service.publish_holder_sheets(
            rows,
            share_with=args.recipient if args.share_sheets else None,
        )
        result["sheet_urls"] = sheet_urls

    if args.send_email:
        result["email_sent"] = service.send_email(
            recipient=args.recipient,
            rows=rows,
            holder_sheet_urls=sheet_urls,
            looker_urls=service.get_enabled_looker_urls(),
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
