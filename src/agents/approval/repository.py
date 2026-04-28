"""Approval Repository 인터페이스."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ApprovalRecord, ApprovalStatus


class IApprovalRepository(ABC):
    @abstractmethod
    def save(self, record: ApprovalRecord) -> None: ...

    @abstractmethod
    def get(self, approval_id: str) -> ApprovalRecord | None: ...

    @abstractmethod
    def update_status(
        self,
        approval_id: str,
        status: ApprovalStatus,
        *,
        decided_by: str = "",
        decision_note: str = "",
    ) -> None: ...

    @abstractmethod
    def save_execution_result(
        self, approval_id: str, result: dict
    ) -> None: ...

    @abstractmethod
    def list_pending(self) -> list[ApprovalRecord]: ...
