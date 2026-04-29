"""Input Gateway 모델.

TaskEnvelope — 에이전트에 전달되는 표준 작업 봉투
TriggerType  — 트리거 출처 (slack / http / cron / manual)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class TriggerType(str, Enum):
    SLACK = "slack"
    HTTP = "http"
    EMAIL = "email"
    CRON = "cron"
    MANUAL = "manual"


@dataclass
class TaskEnvelope:
    """에이전트 입력 표준 봉투.

    Attributes
    ----------
    task_id:
        업무 식별자 (A-2, B-2, C-1 …)
    instruction:
        에이전트에 전달할 자연어 지시문
    context:
        파서가 추출한 구조화된 파라미터 (task_id별로 다름)
    trigger_type:
        호출 출처
    trigger_source:
        채널 ID, cron 이름 등 세부 출처 식별자
    dry_run:
        True면 실제 변경 없이 시뮬레이션
    envelope_id:
        자동 생성 UUID
    created_at:
        생성 시각
    """
    task_id: str
    instruction: str
    context: dict[str, Any] = field(default_factory=dict)
    trigger_type: TriggerType = TriggerType.MANUAL
    trigger_source: str = ""
    dry_run: bool = False
    envelope_id: str = field(
        default_factory=lambda: f"env-{uuid4().hex[:12]}"
    )
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "task_id": self.task_id,
            "instruction": self.instruction,
            "context": self.context,
            "trigger_type": self.trigger_type.value,
            "trigger_source": self.trigger_source,
            "dry_run": self.dry_run,
            "created_at": self.created_at.isoformat(),
        }
