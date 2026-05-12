"""B-2 task handler — 네이버 클립 성과보고 (주간)."""
from __future__ import annotations

from src.core.interfaces.task_handler import ITaskHandler, TaskMeta


class B2TaskHandler(ITaskHandler):
    @property
    def meta(self) -> TaskMeta:
        return TaskMeta(
            task_id="B-2",
            task_name="네이버 클립 성과보고",
            lambda_module="lambda.b2_weekly_report_handler",
        )
