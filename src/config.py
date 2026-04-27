# -*- coding: utf-8 -*-
"""루나트 RPA — 환경 변수 중앙화 설정 모듈.

모든 환경 변수는 이 파일에서 단일 관리합니다.
핸들러/서버 코드에서는 ``from src.config import settings`` 후 속성으로 접근합니다.

사용 예::

    from src.config import settings

    token = settings.SLACK_BOT_TOKEN
    sheet_id = settings.CONTENT_SHEET_ID

중요: Sheet ID 계열 속성은 기본값이 빈 문자열("")입니다.
      반드시 .env 에 실제 값을 입력해야 합니다.
"""
from __future__ import annotations

import os


class Settings:
    """환경 변수를 속성으로 노출하는 설정 클래스.

    임포트 시점에 os.environ 을 1회 읽습니다. 테스트 등에서 env를 변경한 뒤
    재로드가 필요하면 ``settings.__init__()`` 을 재호출하거나 모듈을 다시 임포트하세요.
    """

    def __init__(self) -> None:
        # ── Google 인증 ──────────────────────────────────────────────────────
        self.GOOGLE_CREDENTIALS_FILE: str = os.environ.get(
            "GOOGLE_CREDENTIALS_FILE", "credentials.json"
        )

        # ── RPA 서버 인증 ────────────────────────────────────────────────────
        self.X_INTERN_TOKEN: str   = os.environ.get("X_INTERN_TOKEN", "")
        self.X_INTERN_SESSION: str = os.environ.get("X_INTERN_SESSION", "")

        # ── Slack ────────────────────────────────────────────────────────────
        self.SLACK_BOT_TOKEN: str      = os.environ.get("SLACK_BOT_TOKEN", "")
        self.SLACK_ERROR_CHANNEL: str  = os.environ.get("SLACK_ERROR_CHANNEL", "#rpa-error")

        # ── 공통 시트 ────────────────────────────────────────────────────────
        # 기본값을 하드코딩하지 않음 → .env 에 반드시 입력
        self.CONTENT_SHEET_ID: str     = os.environ.get("CONTENT_SHEET_ID", "")
        self.PERFORMANCE_SHEET_ID: str = os.environ.get(
            "PERFORMANCE_SHEET_ID",
            os.environ.get("CONTENT_SHEET_ID", ""),
        )
        self.LOG_SHEET_ID: str         = os.environ.get(
            "LOG_SHEET_ID",
            os.environ.get("CONTENT_SHEET_ID", ""),
        )

        # ── 시트 탭명 ────────────────────────────────────────────────────────
        self.TAB_CONTENT: str = os.environ.get("TAB_CONTENT", "콘텐츠 목록")
        self.TAB_STATS: str   = os.environ.get("TAB_STATS",   "성과 관리")
        self.TAB_RIGHTS: str  = os.environ.get("TAB_RIGHTS",  "작품 관리")
        self.TAB_LOG: str     = os.environ.get("TAB_LOG",     "로그 기록")

        # ── A-2: 작품사용신청 승인 ───────────────────────────────────────────
        # Sheet ID — .env 의 CREATOR_SHEET_ID 에 반드시 입력
        self.CREATOR_SHEET_ID: str       = os.environ.get("CREATOR_SHEET_ID", "")
        self.DRIVE_FOLDER_ID: str        = os.environ.get("DRIVE_FOLDER_ID", "")
        self.SLACK_APPROVAL_CHANNEL: str = os.environ.get("SLACK_APPROVAL_CHANNEL", "")

        # ── A-3: 네이버 클립 월별 ────────────────────────────────────────────
        self.NAVER_FORM_ID: str          = os.environ.get("NAVER_FORM_ID", "")
        self.NAVER_EXCEL_SHEET_ID: str   = os.environ.get("NAVER_EXCEL_SHEET_ID", "")
        self.TAB_NAVER_FORM: str         = os.environ.get("TAB_NAVER_FORM", "설문지 응답 시트1")
        self.NAVER_MANAGER_EMAIL: str    = os.environ.get("NAVER_MANAGER_EMAIL", "")
        self.NAVER_SLACK_CHANNEL: str    = os.environ.get(
            "NAVER_SLACK_CHANNEL",
            os.environ.get("SLACK_ERROR_CHANNEL", "#rpa-error"),
        )

        # ── B-2: 주간 성과 보고 ──────────────────────────────────────────────
        self.LOOKER_URL_WAVVE: str      = os.environ.get("LOOKER_URL_WAVVE", "")
        self.LOOKER_URL_PANSCINEMA: str = os.environ.get("LOOKER_URL_PANSCINEMA", "")
        self.LOOKER_URL_RIGHTS: str     = os.environ.get("LOOKER_URL_RIGHTS", "")

        # ── C-1: 리드 발굴 ───────────────────────────────────────────────────
        self.YOUTUBE_API_KEY: str   = os.environ.get("YOUTUBE_API_KEY", "")
        self.SEED_CHANNEL_SHEET_ID: str = os.environ.get("SEED_CHANNEL_SHEET_ID", "")
        self.SEED_CHANNEL_GID: str      = os.environ.get("SEED_CHANNEL_GID", "")
        self.LEAD_SHEET_ID: str         = os.environ.get("LEAD_SHEET_ID", "")
        self.TAB_LEADS: str             = os.environ.get("TAB_LEADS", "리드")
        self.C1_GENRES: str             = os.environ.get("C1_GENRES", "예능,드라마·영화")
        self.C1_MIN_MONTHLY_VIEWS: int  = int(os.environ.get("C1_MIN_MONTHLY_VIEWS", "20000000"))
        self.C1_MAX_PAGES: int          = int(os.environ.get("C1_MAX_PAGES", "5"))

        # ── C-2: 콜드메일 ────────────────────────────────────────────────────
        self.SENDER_EMAIL: str          = os.environ.get("SENDER_EMAIL", "")
        self.SENDER_NAME: str           = os.environ.get("SENDER_NAME", "루나트")
        self.USE_SES: bool              = os.environ.get("USE_SES", "false").lower() == "true"
        self.SMTP_HOST: str             = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.SMTP_PORT: int             = int(os.environ.get("SMTP_PORT", "587"))
        self.SMTP_USER: str             = os.environ.get("SMTP_USER", "")
        self.SMTP_PASSWORD: str         = os.environ.get("SMTP_PASSWORD", "")
        self.C2_BATCH_SIZE: int         = int(os.environ.get("C2_BATCH_SIZE", "50"))
        self.C2_MIN_MONTHLY_VIEWS: int  = int(os.environ.get("C2_MIN_MONTHLY_VIEWS", "0"))

        # ── C-3: 신규 작품 등록 ──────────────────────────────────────────────
        self.ADMIN_API_BASE_URL: str    = os.environ.get("ADMIN_API_BASE_URL", "")
        self.ADMIN_API_TOKEN: str       = os.environ.get("ADMIN_API_TOKEN", "")
        self.NOTION_API_KEY: str        = os.environ.get("NOTION_API_KEY", "")
        self.NOTION_GUIDELINE_PARENT_PAGE_ID: str = os.environ.get(
            "NOTION_GUIDELINE_PARENT_PAGE_ID", ""
        )

        # ── D-2: 정산 요청 ───────────────────────────────────────────────────
        self.API_BASE_URL: str = os.environ.get("API_BASE_URL", "")

        # ── D-3: 카카오 크리에이터 온보딩 ────────────────────────────────────
        self.KAKAO_FORM_SHEET_ID: str  = os.environ.get("KAKAO_FORM_SHEET_ID", "")
        self.KAKAO_OUTPUT_SHEET_ID: str = os.environ.get("KAKAO_OUTPUT_SHEET_ID", "")
        self.KAKAO_FORM_TAB: str       = os.environ.get("KAKAO_FORM_TAB",   "설문지 응답 시트1")
        self.KAKAO_OUTPUT_TAB: str     = os.environ.get("KAKAO_OUTPUT_TAB", "최종 리스트")

        # ── AWS ──────────────────────────────────────────────────────────────
        self.AWS_REGION: str = os.environ.get("AWS_REGION", "ap-northeast-2")

    # ── 편의 프로퍼티 ─────────────────────────────────────────────────────────

    @property
    def looker_dashboards(self) -> dict[str, str]:
        """B-2 Looker Studio 대시보드 URL 맵."""
        return {
            "웨이브x루나르트":     self.LOOKER_URL_WAVVE,
            "판씨네마x루나르트":   self.LOOKER_URL_PANSCINEMA,
            "영상권리사x루나르트": self.LOOKER_URL_RIGHTS,
        }


# 모듈 수준 싱글턴
settings = Settings()
