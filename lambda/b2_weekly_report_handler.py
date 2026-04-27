# -*- coding: utf-8 -*-
"""B-2 Lambda 엔트리포인트 — 주간 성과 보고 자동화.

트리거: HTTP Request (API Gateway POST) — 웹 대시보드 연동 예정
  (구 트리거: EventBridge Cron 매주 월요일 10시 KST → 이관 완료)

event["source"] 로 트리거 종류 구분:
  "http"   → API Gateway HTTP 요청
  "cron"   → EventBridge 폴백 (필요 시 유지)
  기본값   → "http"

Looker Studio 대시보드 (권리사별 3개):
  LOOKER_URL_WAVVE       웨이브×루나르트 대시보드 URL
  LOOKER_URL_PANSCINEMA  판씨네마×루나르트 대시보드 URL
  LOOKER_URL_RIGHTS      영상권리사×루나르트 대시보드 URL
  → 각 권리사 이름은 콘텐츠 관리 시트 '작품 관리' 탭의 '이름' 열과 매칭

환경 변수:
  CONTENT_SHEET_ID        콘텐츠 관리 시트 ID
                          (1e-rRWmjL29U53OG1ZPYKSaqKlbSq46K6AsQ356nlM0w)
  PERFORMANCE_SHEET_ID    성과 데이터 시트 ID (기본: CONTENT_SHEET_ID)
  LOG_SHEET_ID            로그 기록 시트 ID (기본: CONTENT_SHEET_ID)
  GOOGLE_CREDENTIALS_FILE 서비스 계정 키 파일 (기본: credentials.json)
  SLACK_BOT_TOKEN         Slack Bot OAuth Token
  SLACK_ERROR_CHANNEL     에러 알림 채널 ID
  SENDER_EMAIL            발신 이메일 주소
  LOOKER_URL_WAVVE        웨이브×루나르트 Looker 대시보드 URL
  LOOKER_URL_PANSCINEMA   판씨네마×루나르트 Looker 대시보드 URL
  LOOKER_URL_RIGHTS       영상권리사×루나르트 Looker 대시보드 URL
  USE_SES                 AWS SES 사용 여부 (기본: true)
"""
import json
import os
import sys

import gspread
from src.api.deps import build_google_creds

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.error_handler import task_handler
from src.core.notifiers.email_notifier import EmailNotifier
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.repositories.sheet_repository import SheetPerformanceRepository, SheetLogRepository
from src.core.logger import CoreLogger
from src.handlers.b2_weekly_report import run as b2_run, TASK_ID, TASK_NAME
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
CONTENT_SHEET_ID     = os.environ["CONTENT_SHEET_ID"]
PERFORMANCE_SHEET_ID = os.environ.get("PERFORMANCE_SHEET_ID", CONTENT_SHEET_ID)
LOG_SHEET_ID         = os.environ.get("LOG_SHEET_ID", CONTENT_SHEET_ID)
CREDS_FILE           = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SLACK_TOKEN          = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH       = os.environ["SLACK_ERROR_CHANNEL"]
SENDER_EMAIL         = os.environ["SENDER_EMAIL"]
USE_SES              = os.environ.get("USE_SES", "true").lower() == "true"

# 권리사별 Looker Studio 대시보드 URL (환경 변수로 관리)
LOOKER_DASHBOARDS: dict[str, str] = {
    "웨이브x루나르트":    os.environ.get("LOOKER_URL_WAVVE", ""),
    "판씨네마x루나르트":  os.environ.get("LOOKER_URL_PANSCINEMA", ""),
    "영상권리사x루나르트": os.environ.get("LOOKER_URL_RIGHTS", ""),
}

# 콘텐츠 관리 시트 탭명
TAB_CONTENT = os.environ.get("TAB_CONTENT", "콘텐츠 목록")    # gid=161689321
TAB_STATS   = os.environ.get("TAB_STATS",   "성과 데이터")
TAB_RIGHTS  = os.environ.get("TAB_RIGHTS",  "작품 관리")       # gid=567622906
TAB_LOG     = os.environ.get("TAB_LOG",     "로그")
# ──────────────────────────────────────────────────────────────────────────────


def _build_deps():
    creds = build_google_creds(CREDS_FILE, _SCOPES)
    gc = gspread.authorize(creds)

    content_sh = gc.open_by_key(CONTENT_SHEET_ID)
    perf_sh    = gc.open_by_key(PERFORMANCE_SHEET_ID)
    log_sh     = gc.open_by_key(LOG_SHEET_ID)

    perf_repo = SheetPerformanceRepository(
        content_ws=content_sh.worksheet(TAB_CONTENT),
        stats_ws=perf_sh.worksheet(TAB_STATS),
        rights_ws=content_sh.worksheet(TAB_RIGHTS),
        looker_dashboards=LOOKER_DASHBOARDS,
    )
    log_repo = SheetLogRepository(log_sh.worksheet(TAB_LOG))

    email_notifier = EmailNotifier(sender_email=SENDER_EMAIL, use_ses=USE_SES)
    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)

    return perf_repo, log_repo, email_notifier, slack_notifier


def handler(event: dict, context) -> dict:
    """Lambda 핸들러 진입점.

    HTTP Request:  event에 API Gateway 페이로드 포함
    Cron 폴백:     event["source"] == "cron"
    """
    # API Gateway body 언래핑
    if "body" in event and isinstance(event["body"], str):
        try:
            body = json.loads(event["body"])
            event = {**event, **body}
        except json.JSONDecodeError:
            pass

    source       = event.get("source", "http")
    trigger_type = TriggerType.CRON if source == "cron" else TriggerType.HTTP
    trigger_src  = f"EventBridge weekly cron" if source == "cron" else "HTTP Request"

    perf_repo, log_repo, email_notifier, slack_notifier = _build_deps()

    @task_handler(
        task_id=TASK_ID,
        task_name=TASK_NAME,
        trigger_type=trigger_type,
        trigger_source=trigger_src,
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
        )

    result = _run(event, context)
    return {
        "statusCode": 200,
        "body": json.dumps(result, ensure_ascii=False),
    }


# 로컬 테스트: python lambda/b2_weekly_report_handler.py
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    result = handler({"source": "manual"}, None)
    print(result)
