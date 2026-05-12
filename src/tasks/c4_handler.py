"""C-4 task handler — 수익 100% 쿠폰 신청 처리 알림."""
from __future__ import annotations

from src.core.interfaces.task_handler import ITaskHandler, TaskMeta


class C4TaskHandler(ITaskHandler):
    @property
    def meta(self) -> TaskMeta:
        return TaskMeta(
            task_id="C-4",
            task_name="쿠폰 신청 처리 알림",
            lambda_module="lambda.c4_coupon_notification_handler",
        )
