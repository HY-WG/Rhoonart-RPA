from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


class Settings:
    """Centralized environment settings for the Rhoonart RPA workspace."""

    def __init__(self) -> None:
        self.GOOGLE_CREDENTIALS_FILE = os.environ.get(
            "GOOGLE_CREDENTIALS_FILE",
            "credentials.json",
        )

        self.X_INTERN_TOKEN = os.environ.get("X_INTERN_TOKEN", "")
        self.X_INTERN_SESSION = os.environ.get("X_INTERN_SESSION", "")

        self.SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
        self.SLACK_ERROR_CHANNEL = os.environ.get("SLACK_ERROR_CHANNEL", "#rpa-error")
        self.SLACK_APPROVAL_CHANNEL = os.environ.get("SLACK_APPROVAL_CHANNEL", "")
        self.SLACK_RELIEF_CHANNEL = os.environ.get("SLACK_RELIEF_CHANNEL", "")
        self.ADMIN_SLACK_USER_ID = os.environ.get("ADMIN_SLACK_USER_ID", "")

        self.CONTENT_SHEET_ID = os.environ.get("CONTENT_SHEET_ID", "")
        self.PERFORMANCE_SHEET_ID = os.environ.get(
            "PERFORMANCE_SHEET_ID",
            self.CONTENT_SHEET_ID,
        )
        self.LOG_SHEET_ID = os.environ.get("LOG_SHEET_ID", self.CONTENT_SHEET_ID)
        self.CREATOR_SHEET_ID = os.environ.get("CREATOR_SHEET_ID", "")
        self.DRIVE_FOLDER_ID = os.environ.get("DRIVE_FOLDER_ID", "")
        self.LEAD_SHEET_ID = os.environ.get("LEAD_SHEET_ID", "")
        self.SEED_CHANNEL_SHEET_ID = os.environ.get("SEED_CHANNEL_SHEET_ID", "")
        self.SEED_CHANNEL_GID = os.environ.get("SEED_CHANNEL_GID", "")
        self.COUPON_SHEET_ID = os.environ.get("COUPON_SHEET_ID", "")
        self.COUPON_SHEET_TAB = os.environ.get("COUPON_SHEET_TAB", "\ucfe0\ud3f0\uc694\uccad")
        self.KAKAO_FORM_SHEET_ID = os.environ.get("KAKAO_FORM_SHEET_ID", "")
        self.KAKAO_OUTPUT_SHEET_ID = os.environ.get("KAKAO_OUTPUT_SHEET_ID", "")

        self.TAB_CONTENT = os.environ.get("TAB_CONTENT", "\ucf58\ud150\uce20 \ubaa9\ub85d")
        self.TAB_STATS = os.environ.get("TAB_STATS", "\uc131\uacfc \uad00\ub9ac")
        self.TAB_RIGHTS = os.environ.get("TAB_RIGHTS", "\uc791\ud488 \uad00\ub9ac")
        self.TAB_LOG = os.environ.get("TAB_LOG", "\ub85c\uadf8 \uae30\ub85d")
        self.TAB_LEADS = os.environ.get("TAB_LEADS", "\ub9ac\ub4dc")
        self.TAB_NAVER_FORM = os.environ.get("TAB_NAVER_FORM", "\uc124\ubb38\uc9c0 \uc751\ub2f5 \uc2dc\ud2b81")
        self.KAKAO_FORM_TAB = os.environ.get("KAKAO_FORM_TAB", "\uc124\ubb38\uc9c0 \uc751\ub2f5 \uc2dc\ud2b81")
        self.KAKAO_OUTPUT_TAB = os.environ.get("KAKAO_OUTPUT_TAB", "\ucd5c\uc885 \ub9ac\uc2a4\ud2b8")

        self.NAVER_FORM_ID = os.environ.get("NAVER_FORM_ID", "")
        self.NAVER_EXCEL_SHEET_ID = os.environ.get("NAVER_EXCEL_SHEET_ID", "")
        self.NAVER_MANAGER_EMAIL = os.environ.get("NAVER_MANAGER_EMAIL", "")
        self.NAVER_SLACK_CHANNEL = os.environ.get(
            "NAVER_SLACK_CHANNEL",
            self.SLACK_ERROR_CHANNEL,
        )

        self.YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
        self.C1_GENRES = os.environ.get("C1_GENRES", "\uc608\ub2a5,\ub4dc\ub77c\ub9c8/\uc601\ud654")
        self.C1_MIN_MONTHLY_VIEWS = _as_int(
            os.environ.get("C1_MIN_MONTHLY_VIEWS"),
            20_000_000,
        )
        self.C1_MAX_PAGES = _as_int(os.environ.get("C1_MAX_PAGES"), 5)

        self.SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
        self.SENDER_NAME = os.environ.get("SENDER_NAME", "\ub974\ud638\uc548\uc544\ud2b8")
        self.USE_SES = _as_bool(os.environ.get("USE_SES"), False)
        self.SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.SMTP_PORT = _as_int(os.environ.get("SMTP_PORT"), 587)
        self.SMTP_USER = os.environ.get("SMTP_USER", "")
        self.SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
        self.C2_BATCH_SIZE = _as_int(os.environ.get("C2_BATCH_SIZE"), 50)
        self.C2_MIN_MONTHLY_VIEWS = _as_int(
            os.environ.get("C2_MIN_MONTHLY_VIEWS"),
            0,
        )

        self.LOOKER_URL_WAVVE = os.environ.get("LOOKER_URL_WAVVE", "")
        self.LOOKER_URL_PANSCINEMA = os.environ.get("LOOKER_URL_PANSCINEMA", "")
        self.LOOKER_URL_RIGHTS = os.environ.get("LOOKER_URL_RIGHTS", "")

        self.ADMIN_API_BASE_URL = os.environ.get("ADMIN_API_BASE_URL", "")
        self.ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
        self.LABELIVE_ADMIN_URL = os.environ.get(
            "LABELIVE_ADMIN_URL",
            "https://labelive.io",
        )
        self.NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
        self.NOTION_GUIDELINE_PARENT_PAGE_ID = os.environ.get(
            "NOTION_GUIDELINE_PARENT_PAGE_ID",
            "",
        )

        self.API_BASE_URL = os.environ.get("API_BASE_URL", "")
        self.RELIEF_DB_TYPE = os.environ.get("RELIEF_DB_TYPE", "memory")
        self.RIGHTS_HOLDER_SHEET_ID = os.environ.get("RIGHTS_HOLDER_SHEET_ID", "")
        self.RIGHTS_HOLDER_GID = os.environ.get("RIGHTS_HOLDER_GID", "240557957")

        self.SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
        self.SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
        self.INTEGRATION_DASHBOARD_DB_TYPE = os.environ.get(
            "INTEGRATION_DASHBOARD_DB_TYPE",
            "memory",
        )

        self.AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")

    @property
    def looker_dashboards(self) -> dict[str, str]:
        return {
            "wavve 르호안아트": self.LOOKER_URL_WAVVE,
            "팬시네마x르호안아트": self.LOOKER_URL_PANSCINEMA,
            "영상권리팀르호안아트": self.LOOKER_URL_RIGHTS,
        }


settings = Settings()
