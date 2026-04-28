"""Approval Queue Service.

에이전트가 고위험 작업을 만나면:
1. create()로 ApprovalRecord 저장 + Slack 알림 발송
2. 에이전트는 checkpoint를 담은 dict 반환 후 즉시 종료 (메모리 유지 안 함)

승인자가 approve/reject 하면:
3. approve() 호출 → checkpoint 로드 → 에이전트 재개
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import ApprovalRecord, ApprovalRequest, ApprovalStatus
from .repository import IApprovalRepository

if TYPE_CHECKING:
    from ..tools.registry import ToolRegistry


class ApprovalQueue:
    def __init__(
        self,
        repo: IApprovalRepository,
        notifier: Any,            # INotifier (slack_notifier 등)
        tool_registry: "ToolRegistry | None" = None,
    ) -> None:
        self._repo = repo
        self._notifier = notifier
        self._tools = tool_registry   # resume 시 도구 실행에 사용

    # ── 생성 ─────────────────────────────────────
    def create(self, request: ApprovalRequest) -> str:
        """승인 요청 저장 + Slack 알림. approval_id 반환."""
        record = ApprovalRecord.from_request(request)
        self._repo.save(record)
        self._send_notification(record)
        return record.approval_id

    # ── 승인 ─────────────────────────────────────
    def approve(
        self,
        approval_id: str,
        decided_by: str,
        note: str = "",
    ) -> dict[str, Any]:
        """승인 처리 후 체크포인트에서 에이전트 재개. 실행 결과 반환."""
        record = self._repo.get(approval_id)
        if record is None:
            raise ValueError(f"승인 요청을 찾을 수 없습니다: {approval_id}")
        if record.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"이미 처리된 승인 요청입니다. (status={record.status.value})"
            )

        self._repo.update_status(
            approval_id,
            ApprovalStatus.APPROVED,
            decided_by=decided_by,
            decision_note=note,
        )

        # 체크포인트에서 에이전트 재개
        result = self._resume_from_checkpoint(record.checkpoint)

        self._repo.save_execution_result(approval_id, result)
        return result

    # ── 거절 ─────────────────────────────────────
    def reject(
        self,
        approval_id: str,
        decided_by: str,
        note: str = "",
    ) -> None:
        """승인 거절 처리."""
        record = self._repo.get(approval_id)
        if record is None:
            raise ValueError(f"승인 요청을 찾을 수 없습니다: {approval_id}")
        if record.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"이미 처리된 승인 요청입니다. (status={record.status.value})"
            )
        self._repo.update_status(
            approval_id,
            ApprovalStatus.REJECTED,
            decided_by=decided_by,
            decision_note=note,
        )

    # ── 조회 ─────────────────────────────────────
    def get(self, approval_id: str) -> ApprovalRecord | None:
        return self._repo.get(approval_id)

    def list_pending(self) -> list[ApprovalRecord]:
        return self._repo.list_pending()

    # ── 내부 ─────────────────────────────────────
    def _resume_from_checkpoint(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """체크포인트에서 에이전트를 재구성하여 Act 단계부터 재개."""
        # 지연 임포트로 순환 참조 방지
        from ..repository import InMemoryAgentTraceRepository
        from ..runtime.agent import RhoArtAgent
        from ..runtime.models import AgentTrace, Thought

        trace = AgentTrace(
            trace_id=checkpoint["trace_id"],
            task_id=checkpoint["envelope"]["task_id"],
            envelope_id=checkpoint["envelope"]["envelope_id"],
            steps=list(checkpoint.get("trace_steps", [])),
        )
        thought = Thought(**checkpoint["pending_thought"])

        agent = RhoArtAgent(
            tool_registry=self._tools,
            approval_queue=self,
            trace_repo=InMemoryAgentTraceRepository(),
        )
        return agent.resume_from_checkpoint(thought, trace)

    def _send_notification(self, record: ApprovalRecord) -> None:
        """Slack 승인 알림 발송."""
        import json

        preview_str = json.dumps(record.preview, ensure_ascii=False, indent=2)
        message = (
            f"*[승인 요청]* `{record.task_id}` — {record.summary}\n"
            f"위험도: `{record.risk_level}` | ID: `{record.approval_id}`\n"
            f"```{preview_str}```\n"
            f"승인: `POST /api/approvals/{record.approval_id}/approve`"
        )
        try:
            self._notifier.send(recipient="#rpa-approvals", message=message)
        except Exception:
            pass  # 알림 실패가 승인 요청 생성을 막지 않도록
