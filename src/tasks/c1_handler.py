"""C-1 task handler — 리드 발굴 자동화."""
from __future__ import annotations

from src.core.interfaces.task_handler import ITaskHandler, TaskMeta


class C1TaskHandler(ITaskHandler):
    @property
    def meta(self) -> TaskMeta:
        return TaskMeta(
            task_id="C-1",
            task_name="리드 발굴 자동화",
            lambda_module="lambda.c1_lead_filter_handler",
        )
