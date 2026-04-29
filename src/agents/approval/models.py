"""Approval Queue 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """에이전트가 Pause 시 생성하는 승인 요청."""
    trace_id: str
    task_id: str
    summary: str                      # 인간이 읽을 수 있는 작업 설명
    risk_level: str
    preview: dict[str, Any]           # 실행 예정 파라미터 미리보기
    checkpoint: dict[str, Any]        # Resume에 필요한 에이전트 상태 전체
    approval_id: str = field(default_factory=lambda: f"apv-{uuid4().hex[:12]}")


@dataclass
class ApprovalRecord:
    """저장소에 보관되는 승인 레코드."""
    approval_id: str
    trace_id: str
    task_id: str
    status: ApprovalStatus
    summary: str
    risk_level: str
    preview: dict[str, Any]
    checkpoint: dict[str, Any]
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decided_by: str = ""
    decision_note: str = ""
    # 실행 결과 (EXECUTED 상태로 전이된 후 저장)
    execution_result: dict[str, Any] | None = None

    @classmethod
    def from_request(cls, req: ApprovalRequest) -> "ApprovalRecord":
        return cls(
            approval_id=req.approval_id,
            trace_id=req.trace_id,
            task_id=req.task_id,
            status=ApprovalStatus.PENDING,
            summary=req.summary,
            risk_level=req.risk_level,
            preview=req.preview,
            checkpoint=req.checkpoint,
        )
