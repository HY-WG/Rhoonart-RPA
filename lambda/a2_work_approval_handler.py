# -*- coding: utf-8 -*-
"""A-2 Lambda 엔트리포인트 — 작품사용신청 승인 자동화.

트리거: Slack Event API (message.channels) → API Gateway → Lambda

Slack 3초 응답 규칙 준수:
  - Slack URL Verification Challenge: 즉시 200 OK + challenge 값 반환
  - 일반 메시지 이벤트:
      현재 구현은 동기 처리 (Drive/Sheet API 호출 ~2초 이내).
      처리 시간이 3초를 초과할 경우 Lambda async invocation 패턴으로 전환 가능.

환경 변수:
  CREATOR_SHEET_ID      크리에이터 이메일 조회 시트 ID
                        (1JZ0eLnvMgpjAehpxRfPN2RiG6Pd22EidnnG8tmAvlKQ)
  DRIVE_FOLDER_ID       작품 파일 Drive 폴더 ID
                        (1SEVgIFr8HivMFXBru3C-mfgfTETeLW92)
  SLACK_BOT_TOKEN       Slack Bot OAuth Token
  SLACK_ERROR_CHANNEL   에러 알림용 Slack 채널 ID
  SLACK_APPROVAL_CHANNEL Slack 작품사용신청 알림 채널 ID (메시지 필터링용)
  SENDER_EMAIL          승인 이메일 발신 주소 (hoyoungy2@gmail.com)
  GOOGLE_CREDENTIALS_FILE  서비스 계정 키 파일 경로 (기본: credentials.json)
  LOG_SHEET_ID          로그 기록 시트 ID (기본: CREATOR_SHEET_ID)
  ADMIN_API_BASE_URL    Admin API 베이스 URL (stub; 공백이면 건너뜀)
  USE_SES               SES 사용 여부 (기본: true)
"""
import json
import os
import sys

import gspread
from src.api.deps import build_google_creds
from googleapiclient.discovery import build

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.error_handler import task_handler
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.repositories.sheet_repository import SheetLogRepository
from src.core.logger import CoreLogger
from src.handlers.a2_work_approval import (
    run as a2_run,
    parse_slack_message,
    TASK_ID, TASK_NAME,
)
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.send",
]

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
CREATOR_SHEET_ID    = os.environ["CREATOR_SHEET_ID"]
DRIVE_FOLDER_ID     = os.environ["DRIVE_FOLDER_ID"]
SLACK_TOKEN         = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH      = os.environ["SLACK_ERROR_CHANNEL"]
SLACK_APPROVAL_CH   = os.environ.get("SLACK_APPROVAL_CHANNEL", "")
SENDER_EMAIL        = os.environ.get("SENDER_EMAIL", "hoyoungy2@gmail.com")
CREDS_FILE          = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
LOG_SHEET_ID        = os.environ.get("LOG_SHEET_ID", CREATOR_SHEET_ID)
ADMIN_API_BASE_URL  = os.environ.get("ADMIN_API_BASE_URL", "")
USE_SES             = os.environ.get("USE_SES", "true").lower() == "true"
TAB_LOG             = os.environ.get("TAB_LOG", "로그")
# ──────────────────────────────────────────────────────────────────────────────


def _build_deps():
    creds = build_google_creds(CREDS_FILE, _SCOPES)

    gc            = gspread.authorize(creds)
    drive_service = build("drive", "v3", credentials=creds)
    log_sh        = gc.open_by_key(LOG_SHEET_ID)
    log_repo      = SheetLogRepository(log_sh.worksheet(TAB_LOG))

    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)
    email_notifier = EmailNotifier(sender_email=SENDER_EMAIL, use_ses=USE_SES)

    return gc, drive_service, log_repo, slack_notifier, email_notifier


def handler(event: dict, context) -> dict:
    """Lambda 핸들러 진입점.

    Slack Event API 페이로드를 수신한다.
    API Gateway는 event["body"]에 JSON 문자열을 전달한다.
    """
    # API Gateway 래핑 해제
    body = event.get("body", event)
    if isinstance(body, str):
        body = json.loads(body)

    # ── Slack URL Verification Challenge ──────────────────────────────────────
    if body.get("type") == "url_verification":
        log.info("[A-2] Slack URL Verification Challenge 수신")
        return {
            "statusCode": 200,
            "body": json.dumps({"challenge": body["challenge"]}),
        }

    # ── 이벤트 콜백 처리 ─────────────────────────────────────────────────────
    slack_event = body.get("event", {})
    event_type  = slack_event.get("type", "")

    # 메시지 이벤트만 처리 (봇 메시지, 서브타입 메시지 제외)
    if event_type != "message" or slack_event.get("subtype"):
        return {"statusCode": 200, "body": "ignored"}

    # 채널 필터 (SLACK_APPROVAL_CHANNEL 지정 시 해당 채널만 처리)
    slack_channel_id = slack_event.get("channel", "")
    if SLACK_APPROVAL_CH and slack_channel_id != SLACK_APPROVAL_CH:
        log.debug("[A-2] 타겟 채널 아님, 스킵: %s", slack_channel_id)
        return {"statusCode": 200, "body": "ignored"}

    slack_message_text = slack_event.get("text", "")
    slack_message_ts   = slack_event.get("ts", "")

    # 신청 메시지 형식 확인 (빠른 필터)
    if "신규 영상 사용 요청" not in slack_message_text:
        log.debug("[A-2] 신청 메시지 아님, 스킵")
        return {"statusCode": 200, "body": "ignored"}

    # ── 의존성 빌드 ──────────────────────────────────────────────────────────
    gc, drive_service, log_repo, slack_notifier, email_notifier = _build_deps()

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
            sheets_client=gc,
            drive_service=drive_service,
            email_notifier=email_notifier,
            slack_notifier=slack_notifier,
            creator_sheet_id=CREATOR_SHEET_ID,
            drive_folder_id=DRIVE_FOLDER_ID,
            sender_email=SENDER_EMAIL,
            admin_api_base_url=ADMIN_API_BASE_URL,
        )

    try:
        result = _run(event, context)
        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False),
        }
    except Exception as e:
        log.error("[A-2] 처리 실패: %s", e)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}, ensure_ascii=False),
        }


# 로컬 테스트: python lambda/a2_work_approval_handler.py
if __name__ == "__main__":
    import os as _os
    _os.environ.setdefault("CREATOR_SHEET_ID",   "1JZ0eLnvMgpjAehpxRfPN2RiG6Pd22EidnnG8tmAvlKQ")
    _os.environ.setdefault("DRIVE_FOLDER_ID",    "1SEVgIFr8HivMFXBru3C-mfgfTETeLW92")
    _os.environ.setdefault("SLACK_BOT_TOKEN",    _os.environ.get("SLACK_BOT_TOKEN", ""))
    _os.environ.setdefault("SLACK_ERROR_CHANNEL","")
    _os.environ.setdefault("SENDER_EMAIL",       "hoyoungy2@gmail.com")

    _mock_event = {
        "body": json.dumps({
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel": "C작품사용신청-알림",
                "ts": "1714000000.000001",
                "text": '채널: "유호영" 의 신규 영상 사용 요청이 있습니다.\n21세기 대군부인',
            }
        })
    }
    print(handler(_mock_event, None))
