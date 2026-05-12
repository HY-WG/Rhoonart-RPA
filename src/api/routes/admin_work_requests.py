"""Admin work-request routes — /api/admin/work-requests/*"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from src.api.dependencies import KST, check_auth, get_supabase, invoke_lambda
from src.api.schemas.requests import WorkRequestDecisionRequest

router = APIRouter(tags=["work-requests"])
logger = logging.getLogger(__name__)


@router.get("/api/admin/work-requests")
def list_work_requests(
    status: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Supabase work_requests 조회."""
    sb = get_supabase()
    q = (
        sb.table("work_requests")
        .select("*")
        .order("requested_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if status and status != "all":
        q = q.eq("status", status)
    result = q.execute()
    return {"items": result.data or []}


@router.post("/api/admin/work-requests/{request_id}/approve")
def approve_work_request(
    request_id: str,
    body: WorkRequestDecisionRequest = Body(default_factory=WorkRequestDecisionRequest),
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    """관리자 승인 — A-2 메일 발송 후 status → approved."""
    sb = get_supabase()
    result = sb.table("work_requests").select("*").eq("id", request_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="work request not found")
    item = result.data[0]
    if item.get("status") == "approved":
        return {"status": "approved", "item": item, "message": "이미 승인된 신청입니다."}

    channel_name = str(item.get("channel_name") or "").strip()
    work_title = str(item.get("work_title") or "").strip()
    creator_email = str(item.get("creator_email") or "").strip()
    if not channel_name or not work_title:
        raise HTTPException(status_code=400, detail="channel_name and work_title are required.")

    now = datetime.now(KST).isoformat()
    a2_event = {
        "body": json.dumps(
            {
                "type": "event_callback",
                "source": "admin_hil",
                "override_email": creator_email,
                "event": {
                    "type": "message",
                    "channel": "C_ADMIN_HIL",
                    "ts": item.get("slack_ts") or f"admin-{request_id}",
                    "text": f'채널: "{channel_name}" 님의 신규 영상 사용 요청이 있습니다.\n{work_title}',
                },
            },
            ensure_ascii=False,
        )
    }
    a2_result = invoke_lambda("lambda.a2_work_approval_handler", a2_event)
    update_payload = {
        "status": "approved",
        "processed_at": now,
        "decision_note": body.note.strip() or "관리자 허용",
        "decided_by": body.decided_by,
        "rejection_message": None,
    }
    try:
        updated = sb.table("work_requests").update(update_payload).eq("id", request_id).execute()
    except Exception as exc:
        if not any(key in str(exc) for key in ("decision_note", "decided_by", "rejection_message")):
            raise
        fallback = {"status": "approved", "processed_at": now}
        updated = sb.table("work_requests").update(fallback).eq("id", request_id).execute()
    return {
        "status": "approved",
        "item": (updated.data or [item])[0],
        "a2_result": a2_result,
        "message": "승인 메일 발송을 요청했습니다.",
    }


@router.post("/api/admin/work-requests/{request_id}/reject")
def reject_work_request(
    request_id: str,
    body: WorkRequestDecisionRequest = Body(default_factory=WorkRequestDecisionRequest),
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    """관리자 거절 — 반려 상태와 안내 문구 저장."""
    sb = get_supabase()
    result = sb.table("work_requests").select("*").eq("id", request_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="work request not found")
    item = result.data[0]
    channel_name = str(item.get("channel_name") or "해당").strip()
    work_title = str(item.get("work_title") or "작품").strip()
    rejection_message = (
        f"아쉽게도 {work_title} 참여 심사 결과 {channel_name} 채널이 반려되었습니다. "
        "권리사 측 선정 기준에 따른 결정으로 상세 사유 안내가 어려운 점 양해 부탁드립니다."
    )
    now = datetime.now(KST).isoformat()
    update_payload = {
        "status": "rejected",
        "processed_at": now,
        "decision_note": body.note.strip() or "관리자 거절",
        "decided_by": body.decided_by,
        "rejection_message": rejection_message,
    }
    try:
        updated = sb.table("work_requests").update(update_payload).eq("id", request_id).execute()
    except Exception as exc:
        if not any(key in str(exc) for key in ("decision_note", "decided_by", "rejection_message")):
            raise
        fallback = {"status": "rejected", "processed_at": now}
        updated = sb.table("work_requests").update(fallback).eq("id", request_id).execute()
    return {
        "status": "rejected",
        "item": (updated.data or [item])[0],
        "message": rejection_message,
    }
