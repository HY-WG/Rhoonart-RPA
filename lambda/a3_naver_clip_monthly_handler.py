# -*- coding: utf-8 -*-
"""A-3 Lambda entrypoint for monthly Naver Clip onboarding."""
from __future__ import annotations

import os
import sys

import gspread

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.deps import build_google_creds
from src.core.error_handler import task_handler
from src.core.logger import CoreLogger
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.repositories.sheet_repository import (
    SheetLogRepository,
    SheetNaverClipApplicantRepository,
)
from src.handlers.a3_naver_clip_monthly import (
    RunMode,
    TASK_ID,
    TASK_NAME,
    run as a3_run,
)
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

NAVER_APPLICANT_SHEET_ID = os.environ.get(
    "NAVER_APPLICANT_SHEET_ID",
    os.environ.get("NAVER_FORM_ID", ""),
)
LOG_SHEET_ID = os.environ.get("LOG_SHEET_ID", NAVER_APPLICANT_SHEET_ID)
CREDS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")

SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CHANNEL = os.environ["SLACK_ERROR_CHANNEL"]
SLACK_CONFIRM_CHANNEL = os.environ.get("NAVER_SLACK_CHANNEL", SLACK_ERROR_CHANNEL)

NAVER_MANAGER_EMAIL = os.environ["NAVER_MANAGER_EMAIL"]
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
USE_SES = os.environ.get("USE_SES", "true").lower() == "true"

APPLICANT_TAB = os.environ.get(
    "NAVER_APPLICANT_TAB",
    os.environ.get("TAB_NAVER_FORM", "NAVER_APPLICANTS"),
)
LOG_TAB = os.environ.get("TAB_LOG", "로그 기록")


def _build_deps():
    creds = build_google_creds(CREDS_FILE, SCOPES)
    client = gspread.authorize(creds)

    applicant_sheet = client.open_by_key(NAVER_APPLICANT_SHEET_ID)
    log_sheet = client.open_by_key(LOG_SHEET_ID)

    applicant_repo = SheetNaverClipApplicantRepository(
        applicant_sheet.worksheet(APPLICANT_TAB)
    )
    log_repo = SheetLogRepository(log_sheet.worksheet(LOG_TAB))
    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CHANNEL)
    email_notifier = EmailNotifier(sender_email=SENDER_EMAIL, use_ses=USE_SES)
    return applicant_repo, log_repo, slack_notifier, email_notifier


def handler(event: dict, context) -> dict:
    raw_mode = event.get("mode", "send")
    try:
        mode = RunMode(raw_mode)
    except ValueError as exc:
        raise ValueError(f"unsupported mode: {raw_mode!r}") from exc

    applicant_repo, log_repo, slack_notifier, email_notifier = _build_deps()

    @task_handler(
        task_id=TASK_ID,
        task_name=TASK_NAME,
        trigger_type=TriggerType.CRON,
        trigger_source=f"EventBridge cron (mode={mode.value})",
        log_repo=log_repo,
        slack_notifier=slack_notifier,
    )
    def _run(*_):
        return a3_run(
            form_repo=applicant_repo,
            log_repo=log_repo,
            slack_notifier=slack_notifier,
            email_notifier=email_notifier,
            mode=mode,
            manager_email=NAVER_MANAGER_EMAIL,
            slack_channel=SLACK_CONFIRM_CHANNEL,
        )

    return _run(event, context)


if __name__ == "__main__":
    import sys as _sys

    selected_mode = _sys.argv[1] if len(_sys.argv) > 1 else "send"
    print(handler({"mode": selected_mode}, None))
