# -*- coding: utf-8 -*-
"""A-3 Lambda 엔트리포인트 — 네이버 클립 월별 채널 인입 자동화.

트리거: EventBridge Cron × 2
  - cron(0 1 L * ? *)  — 매월 말일 10시 KST  (mode=confirm)
  - cron(0 1 1 * ? *)  — 매월  1일 10시 KST  (mode=send)

event 페이로드 예시:
  {"mode": "confirm"}   또는   {"mode": "send"}

의존성 주입:
  - SheetFormResponseRepository : 구글폼 응답 조회 (INaverClipRepository)
  - SheetLogRepository           : 로그 기록
  - SlackNotifier                : Slack 확인 요청 + 에러 알림
  - EmailNotifier                : 엑셀 첨부 메일 발송
"""
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.error_handler import task_handler
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.repositories.sheet_repository import SheetFormResponseRepository, SheetLogRepository
from src.core.logger import CoreLogger
from src.handlers.a3_naver_clip_monthly import run as a3_run, RunMode, TASK_ID, TASK_NAME
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
NAVER_FORM_SHEET_ID = os.environ["NAVER_FORM_ID"]
LOG_SHEET_ID        = os.environ.get("LOG_SHEET_ID", NAVER_FORM_SHEET_ID)
CREDS_FILE          = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")

SLACK_TOKEN         = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH      = os.environ["SLACK_ERROR_CHANNEL"]
SLACK_CONFIRM_CH    = os.environ.get("NAVER_SLACK_CHANNEL", SLACK_ERROR_CH)

NAVER_MANAGER_EMAIL = os.environ["NAVER_MANAGER_EMAIL"]
SENDER_EMAIL        = os.environ["SENDER_EMAIL"]
USE_SES             = os.environ.get("USE_SES", "true").lower() == "true"

TAB_FORM = os.environ.get("TAB_NAVER_FORM", "설문지 응답 시트1")
TAB_LOG  = os.environ.get("TAB_LOG", "로그")

# 구글폼 응답 시트 컬럼명 오버라이드
FORM_COL_MAP = {k: os.environ[k] for k in [
    "NAVER_COL_TIMESTAMP", "NAVER_COL_CHANNEL_NAME", "NAVER_COL_CHANNEL_URL",
    "NAVER_COL_MANAGER_NAME", "NAVER_COL_MANAGER_EMAIL", "NAVER_COL_GENRE",
] if k in os.environ}
_COL_MAP_KEYS = {
    "NAVER_COL_TIMESTAMP":     "COL_TIMESTAMP",
    "NAVER_COL_CHANNEL_NAME":  "COL_CHANNEL_NAME",
    "NAVER_COL_CHANNEL_URL":   "COL_CHANNEL_URL",
    "NAVER_COL_MANAGER_NAME":  "COL_MANAGER_NAME",
    "NAVER_COL_MANAGER_EMAIL": "COL_MANAGER_EMAIL",
    "NAVER_COL_GENRE":         "COL_GENRE",
}
REPO_COL_MAP = {_COL_MAP_KEYS[k]: v for k, v in FORM_COL_MAP.items()}
# ──────────────────────────────────────────────────────────────────────────────


def _build_deps():
    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=_SCOPES)
    gc = gspread.authorize(creds)

    form_sh = gc.open_by_key(NAVER_FORM_SHEET_ID)
    log_sh  = gc.open_by_key(LOG_SHEET_ID)

    form_repo = SheetFormResponseRepository(
        form_sh.worksheet(TAB_FORM),
        col_map=REPO_COL_MAP or None,
    )
    log_repo  = SheetLogRepository(log_sh.worksheet(TAB_LOG))

    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)
    email_notifier = EmailNotifier(sender_email=SENDER_EMAIL, use_ses=USE_SES)

    return form_repo, log_repo, slack_notifier, email_notifier


def handler(event: dict, context) -> dict:
    raw_mode = event.get("mode", "send")
    try:
        mode = RunMode(raw_mode)
    except ValueError:
        raise ValueError(f"알 수 없는 mode 값: {raw_mode!r}. 'confirm' 또는 'send' 중 하나여야 합니다.")

    form_repo, log_repo, slack_notifier, email_notifier = _build_deps()

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
            form_repo=form_repo,
            log_repo=log_repo,
            slack_notifier=slack_notifier,
            email_notifier=email_notifier,
            mode=mode,
            manager_email=NAVER_MANAGER_EMAIL,
            slack_channel=SLACK_CONFIRM_CH,
        )

    return _run(event, context)


# 로컬 테스트: python lambda/a3_naver_clip_monthly_handler.py confirm
if __name__ == "__main__":
    import sys as _sys
    _mode = _sys.argv[1] if len(_sys.argv) > 1 else "send"
    result = handler({"mode": _mode}, None)
    print(result)
