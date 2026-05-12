"""D-3 task handler — 카카오 오리지널 크리에이터 월초 점검."""
from __future__ import annotations

from src.core.interfaces.task_handler import ITaskHandler, TaskMeta


class D3TaskHandler(ITaskHandler):
    @property
    def meta(self) -> TaskMeta:
        return TaskMeta(
            task_id="D-3",
            task_name="카카오 오리지널 크리에이터 월초 점검",
            lambda_module="lambda.d3_kakao_creator_onboarding_handler",
        )
