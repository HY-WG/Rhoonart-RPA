# -*- coding: utf-8 -*-
"""C-2 Lambda 엔트리포인트 — 콜드메일 발송.

트리거: 수동 호출 또는 EventBridge Cron (담당자 설정)

event 페이로드 예시:
  {}                                           — 기본값으로 실행
  {"batch_size": 30, "genre": "예능"}          — 장르 필터 + 배치 크기 지정
  {"genre": "드라마·영화", "min_monthly_views": 10000000}

지원 event 파라미터:
  batch_size (int, 기본 50)       : 1회 최대 발송 수
  genre (str, 기본 전체)          : "예능" | "드라마·영화" | "기타"
  min_monthly_views (int, 기본 0) : 최소 월간 조회수 필터
  platform (str, 기본 전체)       : "youtube"

의존성 주입:
  - SheetLeadRepository : 리드 조회 + 상태 업데이트
  - SheetLogRepository  : 로그 기록
  - EmailNotifier       : 콜드메일 발송 (SES / SMTP)
  - SlackNotifier       : 에러 알림
"""
import os
import sys

import gspread
from src.api.deps import build_google_creds

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.error_handler import task_handler
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.repositories.sheet_repository import SheetLeadRepository, SheetLogRepository
from src.core.logger import CoreLogger
from src.handlers.c2_cold_email import run as c2_run, TASK_ID, TASK_NAME
from src.models.lead import Genre
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
LEAD_SHEET_ID  = os.environ["LEAD_SHEET_ID"]
LOG_SHEET_ID   = os.environ.get("LOG_SHEET_ID", LEAD_SHEET_ID)
CREDS_FILE     = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")

SLACK_TOKEN    = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH = os.environ["SLACK_ERROR_CHANNEL"]

SENDER_EMAIL   = os.environ["SENDER_EMAIL"]
SENDER_NAME    = os.environ.get("SENDER_NAME", "루나트")
USE_SES        = os.environ.get("USE_SES", "true").lower() == "true"

TAB_LEADS = os.environ.get("TAB_LEADS", "리드")
TAB_LOG   = os.environ.get("TAB_LOG", "로그")

DEFAULT_BATCH_SIZE = int(os.environ.get("C2_BATCH_SIZE", "50"))
DEFAULT_MIN_VIEWS  = int(os.environ.get("C2_MIN_MONTHLY_VIEWS", "0"))
# ──────────────────────────────────────────────────────────────────────────────

_GENRE_MAP = {
    "예능":        Genre.ENTERTAINMENT,
    "드라마·영화": Genre.DRAMA_MOVIE,
    "기타":        Genre.OTHER,
}


def _build_deps():
    creds = build_google_creds(CREDS_FILE, _SCOPES)
    gc = gspread.authorize(creds)

    lead_sh = gc.open_by_key(LEAD_SHEET_ID)
    log_sh  = gc.open_by_key(LOG_SHEET_ID)

    lead_repo = SheetLeadRepository(lead_sh.worksheet(TAB_LEADS))
    log_repo  = SheetLogRepository(log_sh.worksheet(TAB_LOG))

    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)
    email_notifier = EmailNotifier(sender_email=SENDER_EMAIL, use_ses=USE_SES)

    return lead_repo, log_repo, slack_notifier, email_notifier


def handler(event: dict, context) -> dict:
    batch_size   = int(event.get("batch_size", DEFAULT_BATCH_SIZE))
    min_views    = int(event.get("min_monthly_views", DEFAULT_MIN_VIEWS))
    raw_genre    = event.get("genre")
    raw_platform = event.get("platform")
    dry_run      = str(event.get("dry_run", "true")).lower() == "true"

    genre    = _GENRE_MAP.get(raw_genre) if raw_genre else None
    platform = raw_platform if raw_platform else None

    if raw_genre and genre is None:
        raise ValueError(f"알 수 없는 genre 값: {raw_genre!r}. 예능 / 드라마·영화 / 기타 중 하나.")

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


# 로컬 테스트: python lambda/c2_cold_email_handler.py
# 장르 지정:   python lambda/c2_cold_email_handler.py 예능 20
if __name__ == "__main__":
    import sys as _sys
    _genre  = _sys.argv[1] if len(_sys.argv) > 1 else None
    _batch  = int(_sys.argv[2]) if len(_sys.argv) > 2 else DEFAULT_BATCH_SIZE
    _payload = {"batch_size": _batch}
    if _genre:
        _payload["genre"] = _genre
    result = handler(_payload, None)
    print(result)
