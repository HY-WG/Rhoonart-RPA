# -*- coding: utf-8 -*-
"""C-4 Lambda 엔트리포인트 — 수익 100% 쿠폰 신청 처리 알림.

트리거 A: Slack Event API (message.channels) — keyword filter
  → event["source"] == "slack"
  → event["text"] 에 "쿠폰" 또는 "100%" 포함 시 처리

트리거 B: Google Apps Script onEdit → HTTPS POST → API Gateway → Lambda
  → event["source"] == "sheets_completion"
  → 처리 완료 행 감지 → 크리에이터에게 카카오 알림톡 발송 (stub)

환경 변수:
  SLACK_BOT_TOKEN          Slack Bot OAuth Token
  SLACK_ERROR_CHANNEL      에러 알림 채널 ID
  ADMIN_SLACK_USER_ID      담당자 Slack User ID (DM 수신, 예: U01ABCDE)
  COUPON_SHEET_ID          쿠폰 처리 목록 Google Sheets ID
  COUPON_SHEET_TAB         쿠폰 처리 탭명 (기본: "쿠폰신청")
  LABELIVE_ADMIN_URL       레이블리 어드민 URL (기본: https://labelive.io)
  GOOGLE_CREDENTIALS_FILE  서비스 계정 키 파일 (기본: credentials.json)
  KAKAO_API_KEY            카카오 알림톡 API 키 (stub — 미확인)
"""
import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.error_handler import task_handler
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.logger import CoreLogger
from src.handlers.c4_coupon_notification import (
    run_on_slack_message,
    run_on_completion,
    TASK_ID,
    TASK_NAME,
)
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
SLACK_TOKEN        = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH     = os.environ["SLACK_ERROR_CHANNEL"]
ADMIN_SLACK_UID    = os.environ["ADMIN_SLACK_USER_ID"]
COUPON_SHEET_ID    = os.environ["COUPON_SHEET_ID"]
COUPON_SHEET_TAB   = os.environ.get("COUPON_SHEET_TAB", "쿠폰신청")
LABELIVE_ADMIN_URL = os.environ.get("LABELIVE_ADMIN_URL", "https://labelive.io")
CREDS_FILE         = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
# ──────────────────────────────────────────────────────────────────────────────


def _build_deps():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)
    return gc, slack_notifier


def handler(event: dict, context) -> dict:
    """Lambda 핸들러 진입점."""
    source = event.get("source", "slack")

    gc, slack_notifier = _build_deps()

    if source == "sheets_completion":
        # 플로우 B: Sheets 완료 업데이트 → 카카오 알림톡
        creator_name  = event.get("creator_name", "")
        creator_phone = event.get("creator_phone", "")

        @task_handler(
            task_id=TASK_ID,
            task_name=TASK_NAME,
            trigger_type=TriggerType.HTTP,
            trigger_source="GAS onEdit sheets_completion",
            log_repo=None,
            slack_notifier=slack_notifier,
        )
        def _run(*_):
            return run_on_completion(
                creator_name=creator_name,
                creator_phone=creator_phone,
                kakao_notifier=None,  # TODO: KakaoNotifier 연결 (API 키 확인 후)
            )

        return _run(event, context)

    else:
        # 플로우 A: Slack 메시지 키워드 필터
        creator_name  = event.get("creator_name", "")
        message_text  = event.get("text", "")

        @task_handler(
            task_id=TASK_ID,
            task_name=TASK_NAME,
            trigger_type=TriggerType.HTTP,
            trigger_source="Slack Event API",
            log_repo=None,
            slack_notifier=slack_notifier,
        )
        def _run(*_):
            return run_on_slack_message(
                creator_name=creator_name,
                slack_message_text=message_text,
                sheets_client=gc,
                coupon_sheet_id=COUPON_SHEET_ID,
                coupon_sheet_tab=COUPON_SHEET_TAB,
                slack_notifier=slack_notifier,
                admin_slack_user_id=ADMIN_SLACK_UID,
                labelive_admin_url=LABELIVE_ADMIN_URL,
            )

        return _run(event, context)


# 로컬 테스트: python lambda/c4_coupon_notification_handler.py
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # 플로우 A 테스트
    result = handler(
        {
            "source": "slack",
            "creator_name": "테스트 크리에이터",
            "text": "수익 100% 쿠폰 신청합니다",
        },
        None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
