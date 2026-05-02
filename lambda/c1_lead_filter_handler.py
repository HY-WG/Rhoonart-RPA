# -*- coding: utf-8 -*-
"""C-1 Lambda 엔트리포인트 — 리드 발굴 (YouTube Shorts 채널 탐색기).

트리거 1: EventBridge Cron — cron(0 1 1 * ? *) (매월 1일 10시 KST)
트리거 2: work_threshold — 신규 작품 등록 후 7일(2주) 이내 작품사용신청이 5개 이하일 시 자동 호출
          event 구조: {"source": "work_threshold", "work_title": "작품명", "work_id": "..."}


탐색 구조:
  Layer A — 채널명 키워드 직접 검색 (type=channel)
    비용: 100유닛 × 7개 키워드 = 700유닛 (고정)

  Layer B — 드라마·영화 제목 기반 Shorts 영상 검색
    비용: 100유닛 × 2 × 제목수 (기본 10개 → 2,000유닛)

  합계: ~2,700유닛 / 월 (일일 한도 10,000유닛 이내)

환경 변수:
  YOUTUBE_API_KEY         YouTube Data API v3 키
  SEED_CHANNEL_SHEET_ID   시드 채널 URL 시트 ID
                          (18HY8-FdG_nAe-gOP7WNKiu5k7xMQliW9oxvKTcLC8Is)
  SEED_CHANNEL_GID        시드 채널 탭 GID (기본: 1224056617)
  LEAD_SHEET_ID           리드 저장 시트 ID
  LOG_SHEET_ID            로그 기록 시트 ID (기본: LEAD_SHEET_ID)
  GOOGLE_CREDENTIALS_FILE 서비스 계정 키 파일 (기본: credentials.json)
  SLACK_BOT_TOKEN         Slack Bot OAuth Token
  SLACK_ERROR_CHANNEL     에러 알림 채널 ID
  C1_MAX_CHANNELS         최대 탐색 채널 수 (기본: 200)
"""
import os
import sys

import gspread
from src.api.deps import build_google_creds

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.error_handler import task_handler
from src.core.notifiers.slack_notifier import SlackNotifier
from src.core.repositories.sheet_repository import SheetLeadRepository, SheetLogRepository
from src.core.repositories.supabase_repository import (
    SupabaseLeadRepository,
    SupabaseLogRepository,
    SupabaseSeedChannelRepository,
)
from src.core.logger import CoreLogger
from src.handlers.c1_lead_filter import run as c1_run, run_for_work as c1_run_for_work, TASK_ID, TASK_NAME
from src.models.log_entry import TriggerType

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
YOUTUBE_API_KEY       = os.environ["YOUTUBE_API_KEY"]
C_LEAD_REPOSITORY_TYPE = os.environ.get("C_LEAD_REPOSITORY_TYPE", "supabase").lower()
SEED_SHEET_ID         = os.environ.get("SEED_CHANNEL_SHEET_ID", "")
SEED_SHEET_GID        = os.environ.get("SEED_CHANNEL_GID", "1224056617")
LEAD_SHEET_ID         = os.environ.get("LEAD_SHEET_ID", "")
LOG_SHEET_ID          = os.environ.get("LOG_SHEET_ID", LEAD_SHEET_ID)
CREDS_FILE            = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
SLACK_TOKEN           = os.environ["SLACK_BOT_TOKEN"]
SLACK_ERROR_CH        = os.environ["SLACK_ERROR_CHANNEL"]
MAX_CHANNELS          = int(os.environ.get("C1_MAX_CHANNELS", "200"))

TAB_LEADS = os.environ.get("TAB_LEADS", "리드")
TAB_LOG   = os.environ.get("TAB_LOG", "로그")
# ──────────────────────────────────────────────────────────────────────────────


def _build_deps():
    if C_LEAD_REPOSITORY_TYPE == "supabase":
        from supabase import create_client  # type: ignore

        supabase_url = os.environ["SUPABASE_URL"]
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
        client = create_client(supabase_url, supabase_key)
        lead_repo = SupabaseLeadRepository(client)
        log_repo = SupabaseLogRepository(client)
        seed_repo = SupabaseSeedChannelRepository(client)
        slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)
        return lead_repo, log_repo, slack_notifier, seed_repo

    creds = build_google_creds(CREDS_FILE, _SCOPES)
    gc = gspread.authorize(creds)

    lead_sh = gc.open_by_key(LEAD_SHEET_ID)
    log_sh  = gc.open_by_key(LOG_SHEET_ID)

    lead_repo = SheetLeadRepository(lead_sh.worksheet(TAB_LEADS))
    log_repo  = SheetLogRepository(log_sh.worksheet(TAB_LOG))
    slack_notifier = SlackNotifier(token=SLACK_TOKEN, error_channel=SLACK_ERROR_CH)

    return lead_repo, log_repo, slack_notifier, None


def handler(event: dict, context) -> dict:
    """Lambda 핸들러 진입점.

    event["source"] 에 따라 트리거 종류를 구분합니다.
      - "work_threshold": 특정 작품의 채널 부족 → 리드발굴 + Slack 알림
        필수 필드: event["work_title"] (str)
        선택 필드: event["lead_sheet_url"] (str, Slack 링크용)
      - 그 외 (기본, cron): 월간 전체 탐색
    """
    lead_repo, log_repo, slack_notifier, seed_repo = _build_deps()
    source = event.get("source", "cron")
    seed_urls = seed_repo.list_seed_channel_urls() if seed_repo else None

    if source == "work_threshold":
        work_title = event.get("work_title", "알 수 없는 작품")
        lead_sheet_url = event.get("lead_sheet_url", "")

        @task_handler(
            task_id=TASK_ID,
            task_name=TASK_NAME,
            trigger_type=TriggerType.HTTP,
            trigger_source=f"work_threshold:{work_title}",
            log_repo=log_repo,
            slack_notifier=slack_notifier,
        )
        def _run_threshold(*_):
            return c1_run_for_work(
                work_title=work_title,
                lead_repo=lead_repo,
                log_repo=log_repo,
                slack_notifier=slack_notifier,
                api_key=YOUTUBE_API_KEY,
                seed_sheet_id=SEED_SHEET_ID,
                lead_sheet_url=lead_sheet_url,
                seed_sheet_gid=SEED_SHEET_GID,
                max_channels=MAX_CHANNELS,
                seed_urls=seed_urls,
            )

        return _run_threshold(event, context)

    # 기본: 월간 전체 탐색 (cron 또는 수동)
    @task_handler(
        task_id=TASK_ID,
        task_name=TASK_NAME,
        trigger_type=TriggerType.CRON,
        trigger_source="EventBridge monthly cron",
        log_repo=log_repo,
        slack_notifier=slack_notifier,
    )
    def _run(*_):
        return c1_run(
            lead_repo=lead_repo,
            log_repo=log_repo,
            slack_notifier=slack_notifier,
            api_key=YOUTUBE_API_KEY,
            seed_sheet_id=SEED_SHEET_ID,
            seed_sheet_gid=SEED_SHEET_GID,
            max_channels=MAX_CHANNELS,
            seed_urls=seed_urls,
        )

    return _run(event, context)


# 로컬 테스트: python lambda/c1_lead_filter_handler.py
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    result = handler({}, None)
    print(result)
