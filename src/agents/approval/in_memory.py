"""InMemory Approval Repository — 테스트 및 개발용."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from threading import Lock

from .models import ApprovalRecord, ApprovalStatus
from .repository import IApprovalRepository


class InMemoryApprovalRepository(IApprovalRepository):
    def __init__(self) -> None:
        self._records: dict[str, ApprovalRecord] = {}
        self._lock = Lock()

    def save(self, record: ApprovalRecord) -> None:
        with self._lock:
            self._records[record.approval_id] = copy.deepcopy(record)

    def get(self, approval_id: str) -> ApprovalRecord | None:
        with self._lock:
            rec = self._records.get(approval_id)
            return copy.deepcopy(rec) if rec else None

    def update_status(
        self,
        approval_id: str,
        status: ApprovalStatus,
        *,
        decided_by: str = "",
        decision_note: str = "",
    ) -> None:
        with self._lock:
            rec = self._records.get(approval_id)
            if rec is None:
                raise KeyError(f"approval not found: {approval_id}")
            rec.status = status
            rec.decided_at = datetime.now(timezone.utc)
            rec.decided_by = decided_by
            rec.decision_note = decision_note

    def save_execution_result(self, approval_id: str, result: dict) -> None:
        with self._lock:
            rec = self._records.get(approval_id)
            if rec is None:
                raise KeyError(f"approval not found: {approval_id}")
            rec.execution_result = result
            rec.status = ApprovalStatus.EXECUTED

    def list_pending(self) -> list[ApprovalRecord]:
        with self._lock:
            return [
                copy.deepcopy(r)
                for r in self._records.values()
                if r.status == ApprovalStatus.PENDING
            ]
