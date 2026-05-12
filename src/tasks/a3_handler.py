"""A-3 task handler — 네이버 클립 월별 온보딩.

post_invoke writes an audit row to naver_new_channel_monthly_report
so the admin UI can track when the monthly onboarding was triggered.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytz

from src.api.dependencies import get_supabase
from src.core.interfaces.task_handler import ITaskHandler, TaskMeta

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


class A3TaskHandler(ITaskHandler):
    @property
    def meta(self) -> TaskMeta:
        return TaskMeta(
            task_id="A-3",
            task_name="네이버 클립 월별 온보딩",
            lambda_module="lambda.a3_naver_clip_monthly_handler",
        )

    def post_invoke(
        self,
        result: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Upsert an audit row into naver_new_channel_monthly_report."""
        try:
            now_kst = datetime.now(KST)
            get_supabase().table("naver_new_channel_monthly_report").upsert(
                {
                    "report_year_month": now_kst.strftime("%Y-%m"),
                    "sent_at": now_kst.isoformat(),
                    "sent_by": "admin",
                    "notes": "보고 메일 발송",
                },
                on_conflict="report_year_month",
            ).execute()
        except Exception as exc:
            logger.warning("naver_new_channel_monthly_report 로그 실패: %s", exc)
        return result
