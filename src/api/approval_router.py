"""Approval API Router — 에이전트 승인/거절 엔드포인트.

엔드포인트:
  GET  /api/approvals/pending          — 대기 중 승인 목록
  GET  /api/approvals/{approval_id}    — 단건 조회
  POST /api/approvals/{approval_id}/approve  — 승인 + 에이전트 재개
  POST /api/approvals/{approval_id}/reject   — 거절

ApprovalQueue는 의존성 주입으로 전달받는다.
서버 시작 시 rpa_server.py 에서 build_approval_router(queue) 호출.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.agents.approval.queue import ApprovalQueue


# ── 요청 스키마 ───────────────────────────────────────────────────────────

class ApproveRequest(BaseModel):
    decided_by: str = "admin"
    note: str = ""


class RejectRequest(BaseModel):
    decided_by: str = "admin"
    note: str = ""


# ── 라우터 팩토리 ─────────────────────────────────────────────────────────

def build_approval_router(queue: ApprovalQueue) -> APIRouter:
    """ApprovalQueue를 주입받아 FastAPI APIRouter 반환."""
    router = APIRouter(prefix="/api/approvals", tags=["approvals"])

    @router.get("/pending")
    def list_pending() -> list[dict[str, Any]]:
        """대기 중인 승인 요청 목록 반환."""
        records = queue.list_pending()
        return [
            {
                "approval_id": r.approval_id,
                "task_id": r.task_id,
                "trace_id": r.trace_id,
                "summary": r.summary,
                "risk_level": r.risk_level,
                "preview": r.preview,
                "requested_at": r.requested_at.isoformat(),
            }
            for r in records
        ]

    @router.get("/{approval_id}")
    def get_approval(approval_id: str) -> dict[str, Any]:
        """단건 승인 레코드 조회."""
        record = queue.get(approval_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"승인 요청 없음: {approval_id}")
        return {
            "approval_id": record.approval_id,
            "task_id": record.task_id,
            "trace_id": record.trace_id,
            "status": record.status.value,
            "summary": record.summary,
            "risk_level": record.risk_level,
            "preview": record.preview,
            "requested_at": record.requested_at.isoformat(),
            "decided_at": record.decided_at.isoformat() if record.decided_at else None,
            "decided_by": record.decided_by,
            "decision_note": record.decision_note,
            "execution_result": record.execution_result,
        }

    @router.post("/{approval_id}/approve")
    def approve(approval_id: str, body: ApproveRequest) -> dict[str, Any]:
        """승인 처리 후 에이전트 재개. 실행 결과 반환."""
        try:
            result = queue.approve(
                approval_id,
                decided_by=body.decided_by,
                note=body.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"에이전트 재개 실패: {exc}"
            ) from exc
        return {"approval_id": approval_id, "execution_result": result}

    @router.post("/{approval_id}/reject")
    def reject(approval_id: str, body: RejectRequest) -> dict[str, Any]:
        """승인 거절 처리."""
        try:
            queue.reject(
                approval_id,
                decided_by=body.decided_by,
                note=body.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"approval_id": approval_id, "status": "rejected"}

    return router
