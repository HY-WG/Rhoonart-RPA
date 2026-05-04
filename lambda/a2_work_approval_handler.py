# -*- coding: utf-8 -*-
"""A-2 Lambda 엔트리포인트."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gspread
from googleapiclient.discovery import build

from src.api.deps import build_google_creds
from src.core.error_handler import task_handler
from src.core.logger import CoreLogger
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.repositories.sheet_repository import SheetLogRepository
from src.handlers.a2_work_approval import TASK_ID, TASK_NAME, run as a2_run
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
]

CREATOR_SHEET_ID = os.environ["CREATOR_SHEET_ID"]
DRIVE_FOLDER_ID = os.environ["DRIVE_FOLDER_ID"]
SLACK_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH = os.environ["SLACK_ERROR_CHANNEL"]
SLACK_APPROVAL_CH = os.environ.get("SLACK_APPROVAL_CHANNEL", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "hoyoungy2@gmail.com")
CREDS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
LOG_SHEET_ID = os.environ.get("LOG_SHEET_ID", CREATOR_SHEET_ID)
ADMIN_API_BASE_URL = os.environ.get("ADMIN_API_BASE_URL", "")
USE_SES = os.environ.get("USE_SES", "true").lower() == "true"
TAB_LOG = os.environ.get("TAB_LOG", "로그 기록")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")


def _build_deps():
    creds = build_google_creds(CREDS_FILE, _SCOPES)

    sheets_client = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds)
    log_spreadsheet = sheets_client.open_by_key(LOG_SHEET_ID)
    log_repo = SheetLogRepository(log_spreadsheet.worksheet(TAB_LOG))

    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)
    email_notifier = EmailNotifier(sender_email=SENDER_EMAIL, use_ses=USE_SES)

    supabase_client = None
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            from supabase import create_client  # type: ignore
            supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as exc:
            log.warning("[A-2] Supabase 클라이언트 초기화 실패: %s", exc)

    return sheets_client, drive_service, log_repo, slack_notifier, email_notifier, supabase_client


def handler(event: dict, context) -> dict[str, object]:
    """Slack Event API payload를 받아 A-2 로직을 실행한다."""
    body = event.get("body", event)
    if isinstance(body, str):
        body = json.loads(body)

    if body.get("type") == "url_verification":
        log.info("[A-2] Slack URL verification challenge 수신")
        return {
            "statusCode": 200,
            "body": json.dumps({"challenge": body["challenge"]}, ensure_ascii=False),
        }

    slack_event = body.get("event", {})
    if slack_event.get("type") != "message" or slack_event.get("subtype"):
        return {"statusCode": 200, "body": "ignored"}

    slack_channel_id = slack_event.get("channel", "")
    if SLACK_APPROVAL_CH and slack_channel_id != SLACK_APPROVAL_CH:
        log.debug("[A-2] 승인 대상 채널이 아니므로 무시: %s", slack_channel_id)
        return {"statusCode": 200, "body": "ignored"}

    slack_message_text = slack_event.get("text", "")
    if "신규 영상 사용 요청" not in slack_message_text:
        log.debug("[A-2] 승인 요청 메시지가 아니므로 무시")
        return {"statusCode": 200, "body": "ignored"}

    slack_message_ts = slack_event.get("ts", "")
    sheets_client, drive_service, log_repo, slack_notifier, email_notifier, supabase_client = _build_deps()

    @task_handler(
        task_id=TASK_ID,
        task_name=TASK_NAME,
        trigger_type=TriggerType.SLACK_WEBHOOK,
        trigger_source=f"Slack #{slack_channel_id}",
        log_repo=log_repo,
        slack_notifier=slack_notifier,
    )
    def _run(*_):
        return a2_run(
            slack_channel_id=slack_channel_id,
            slack_message_ts=slack_message_ts,
            slack_message_text=slack_message_text,
            sheets_client=sheets_client,
            drive_service=drive_service,
            email_notifier=email_notifier,
            slack_notifier=slack_notifier,
            creator_sheet_id=CREATOR_SHEET_ID,
            drive_folder_id=DRIVE_FOLDER_ID,
            sender_email=SENDER_EMAIL,
            admin_api_base_url=ADMIN_API_BASE_URL,
            supabase_client=supabase_client,
        )

    try:
        result = _run(event, context)
        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False),
        }
    except Exception as exc:
        log.error("[A-2] 처리 실패: %s", exc)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}, ensure_ascii=False),
        }


if __name__ == "__main__":
    os.environ.setdefault("CREATOR_SHEET_ID", "1JZ0eLnvMgpjAehpxRfPN2RiG6Pd22EidnnG8tmAvlKQ")
    os.environ.setdefault("DRIVE_FOLDER_ID", "1SEVgIFr8HivMFXBru3C-mfgfTETeLW92")
    os.environ.setdefault("SLACK_BOT_TOKEN", os.environ.get("SLACK_BOT_TOKEN", ""))
    os.environ.setdefault("SLACK_ERROR_CHANNEL", "")
    os.environ.setdefault("SENDER_EMAIL", "hoyoungy2@gmail.com")

    mock_event = {
        "body": json.dumps(
            {
                "type": "event_callback",
                "event": {
                    "type": "message",
                    "channel": os.environ.get("SLACK_APPROVAL_CHANNEL", "C0ATE59CY3E"),
                    "ts": "1714000000.000001",
                    "text": '채널: "정호영" 님의 신규 영상 사용 요청이 있습니다.\n21세기 대군부인',
                },
            },
            ensure_ascii=False,
        )
    }
    print(handler(mock_event, None))
