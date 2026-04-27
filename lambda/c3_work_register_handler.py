# -*- coding: utf-8 -*-
"""C-3 Lambda 엔트리포인트 — 신규 작품 등록.

트리거: HTTP Request (관리자 웹 또는 수동 호출)

환경 변수:
  ADMIN_API_BASE_URL              레이블리 어드민 API 베이스 URL
                                  미설정 시 StubAdminAPIClient 자동 사용
  ADMIN_API_TOKEN                 Admin API 인증 토큰 (Bearer)
  X_INTERN_SESSION                Supabase Edge Function 세션 ID (선택)
  NOTION_API_KEY                  Notion Integration 토큰 (가이드라인 노션 페이지 생성용)
  NOTION_GUIDELINE_PARENT_PAGE_ID 가이드라인 페이지를 생성할 부모 Notion 페이지 ID
  SLACK_BOT_TOKEN                 Slack Bot OAuth Token
  SLACK_ERROR_CHANNEL             에러 알림 채널 ID

event 구조 예시:
{
  "work_title":           "신병",
  "rights_holder_name":   "웨이브",
  "release_year":         2022,
  "description":          "작품 소개",
  "director":             "감독명",
  "cast":                 "배우1, 배우2",
  "genre":                "드라마",
  "video_type":           "드라마",
  "country":              "한국",
  "platforms":            ["웨이브"],
  "platform_video_url":   "https://...",
  "trailer_url":          "https://...",
  "source_download_url":  "https://...",

  // 가이드라인 (선택 — 없으면 STEP 2 건너뜀)
  "guideline": {
    "source_provided_date":   "2026-05-01",
    "upload_available_date":  "2026-05-10",
    "usage_notes":            "주의사항 내용",
    "format_guide":           "#신병 #드라마클립 문구 포함 필수",
    "other_platforms":        "네이버 클립 가능 / 카카오 숏폼 불가",
    "logo_subtitle_provided": true,
    "review_required":        false
  },

  "dry_run": false
}
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.core.clients.admin_api_client import build_admin_client
from src.core.error_handler import task_handler
from src.core.logger import CoreLogger
from src.core.notifiers.slack_notifier import SlackNotifier
from src.handlers.c3_work_register import run as c3_run, TASK_ID, TASK_NAME
from src.models.log_entry import TriggerType
from src.models.work import Work
from src.models.work_guideline import WorkGuideline

log = CoreLogger(__name__)

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
_ADMIN_API_BASE_URL  = os.environ.get("ADMIN_API_BASE_URL", "")
_ADMIN_API_TOKEN     = os.environ.get("ADMIN_API_TOKEN", "")
_X_INTERN_SESSION    = os.environ.get("X_INTERN_SESSION", "")
_NOTION_TOKEN        = os.environ.get("NOTION_API_KEY", "")
_NOTION_PARENT_PAGE  = os.environ.get("NOTION_GUIDELINE_PARENT_PAGE_ID", "")
_SLACK_TOKEN         = os.environ.get("SLACK_BOT_TOKEN", "")
_SLACK_ERROR_CH      = os.environ.get("SLACK_ERROR_CHANNEL", "#rpa-error")


def _parse_guideline(raw: dict | None) -> WorkGuideline | None:
    """event['guideline'] dict -> WorkGuideline 변환."""
    if not raw:
        return None
    try:
        return WorkGuideline(**raw)
    except Exception as e:
        log.warning("[C-3] guideline 파싱 실패 (건너뜀): %s", e)
        return None


def handler(event: dict, context=None) -> dict:
    """Lambda / HTTP 핸들러 진입점."""
    # JSON body 처리 (API Gateway 래핑)
    if isinstance(event.get("body"), str):
        try:
            body = json.loads(event["body"])
            event = {**event, **body}
        except json.JSONDecodeError:
            pass

    work = Work(
        work_title=event.get("work_title", ""),
        rights_holder_name=event.get("rights_holder_name", ""),
        release_year=event.get("release_year"),
        description=event.get("description", ""),
        director=event.get("director", ""),
        cast=event.get("cast", ""),
        genre=event.get("genre", ""),
        video_type=event.get("video_type", ""),
        country=event.get("country", ""),
        platforms=event.get("platforms", []),
        platform_video_url=event.get("platform_video_url", ""),
        trailer_url=event.get("trailer_url", ""),
        source_download_url=event.get("source_download_url", ""),
    )

    guideline = _parse_guideline(event.get("guideline"))
    dry_run   = bool(event.get("dry_run", False))

    admin_client = build_admin_client(
        base_url=_ADMIN_API_BASE_URL,
        token=_ADMIN_API_TOKEN,
        session=_X_INTERN_SESSION,
    )

    slack_notifier = (
        SlackNotifier(token=_SLACK_TOKEN, error_channel=_SLACK_ERROR_CH)
        if _SLACK_TOKEN else None
    )

    log.info("[C-3] 핸들러 시작: '%s' (dry_run=%s)", work.work_title, dry_run)

    @task_handler(
        task_id=TASK_ID,
        task_name=TASK_NAME,
        trigger_type=TriggerType.HTTP,
        trigger_source="admin web / manual",
        log_repo=None,
        slack_notifier=slack_notifier,
    )
    def _run(*_):
        return c3_run(
            work=work,
            guideline=guideline,
            admin_client=admin_client,
            notion_token=_NOTION_TOKEN,
            notion_parent_page_id=_NOTION_PARENT_PAGE,
            dry_run=dry_run,
        )

    return _run(event, context)


if __name__ == "__main__":
    # 로컬 테스트: python lambda/c3_work_register_handler.py
    result = handler(
        {
            "work_title": "신병",
            "rights_holder_name": "웨이브",
            "release_year": 2022,
            "genre": "드라마",
            "country": "한국",
            "guideline": {
                "upload_available_date": "2026-05-10",
                "usage_notes": "작품 소스 제공 후 2주 이내 업로드 완료",
                "format_guide": "#신병 #웨이브 #드라마클립 문구를 제목에 포함해주세요.",
                "other_platforms": "네이버 클립 가능 / 카카오 숏폼 불가",
                "logo_subtitle_provided": True,
                "review_required": False,
            },
            "dry_run": True,
        },
        None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
