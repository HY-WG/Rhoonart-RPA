"""C-2 task handler — 콜드메일 발송."""
from __future__ import annotations

from src.core.interfaces.task_handler import ITaskHandler, TaskMeta


class C2TaskHandler(ITaskHandler):
    @property
    def meta(self) -> TaskMeta:
        return TaskMeta(
            task_id="C-2",
            task_name="콜드메일 발송",
            lambda_module="lambda.c2_cold_email_handler",
        )
