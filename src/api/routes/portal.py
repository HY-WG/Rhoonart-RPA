"""Portal API routes — /api/channels/me/*

These endpoints serve the partner-facing portal (portal_users / portal_channels / portal_videos).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, File, Form, Header, HTTPException, UploadFile

from src.api.dependencies import KST, get_supabase, build_naver_clip_repository
from src.api.schemas.requests import PortalActionRequest
from src.backoffice.dependencies import get_relief_request_service
from src.config import settings
from src.api.storage import safe_storage_name, upload_storage_file

router = APIRouter(tags=["portal"])

NAVER_REVENUE_BUCKET = "naver-revenue-settlements"

_PORTAL_CHANNEL_STATUS_LABEL: dict[str, str] = {
    "pending": "검토중",
    "approved": "승인",
    "blocked": "차단",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_portal_receipt(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": f"{action}-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}",
        "status": "received",
        "action": action,
        "payload": payload,
        "message": "요청이 접수되었습니다.",
    }


def _get_portal_user(user_email: str) -> dict[str, Any]:
    """Look up the portal user by email (X-Portal-User header value)."""
    if not user_email:
        raise HTTPException(status_code=401, detail="X-Portal-User 헤더가 필요합니다.")
    try:
        result = (
            get_supabase()
            .table("portal_users")
            .select("id, email, name")
            .eq("email", user_email.strip())
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=401,
                detail=f"등록되지 않은 포털 사용자입니다: {user_email}",
            )
        return result.data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"portal_users 조회 실패: {exc}") from exc


def _get_portal_channel_for_user(
    user_id: str,
    channel_name: str | None = None,
) -> dict[str, Any]:
    """Return the first approved channel owned by *user_id*.

    If *channel_name* is given, filter to that specific channel.
    """
    try:
        q = (
            get_supabase()
            .table("portal_channels")
            .select("id, channel_name, platform, status")
            .eq("owner_id", user_id)
            .eq("status", "approved")
        )
        if channel_name:
            q = q.eq("channel_name", channel_name.strip())
        result = q.order("created_at", desc=False).limit(1).execute()
        channels = result.data or []
        if not channels:
            raise HTTPException(
                status_code=404,
                detail="승인된 채널이 없습니다. 채널 등록 후 이용해 주세요.",
            )
        return channels[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"portal_channels 조회 실패: {exc}") from exc


def _insert_copyright_claim(
    *,
    sb,
    work_id: int,
    channel_name: str,
    work_title: str,
    right_holder_id: int | str | None,
) -> dict[str, Any]:
    now = datetime.now(KST)
    due = (now + timedelta(days=7)).date().isoformat()
    payload: dict[str, Any] = {
        "channel_id": None,
        "channel_name": channel_name,
        "work_id": work_id,
        "work_title": work_title,
        "right_holder_id": right_holder_id,
        "due": due,
        "requested_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "completed": False,
        "completed_at": None,
    }
    try:
        result = sb.table("copyright_claims").insert(payload).execute()
        return (result.data or [payload])[0]
    except Exception as exc:
        missing_completed = "completed" in str(exc) and (
            "column" in str(exc).lower() or "schema cache" in str(exc).lower()
        )
        if not missing_completed:
            import logging
            logging.getLogger(__name__).warning("copyright_claims insert failed: %s", exc)
            raise HTTPException(
                status_code=500, detail=f"copyright_claims 저장 실패: {exc}"
            ) from exc
        fallback_payload = {
            key: value
            for key, value in payload.items()
            if key not in {"completed", "completed_at"}
        }
        result = sb.table("copyright_claims").insert(fallback_payload).execute()
        saved = (result.data or [fallback_payload])[0]
        saved["completed"] = False
        saved["completed_at"] = None
        import logging
        logging.getLogger(__name__).warning(
            "copyright_claims.completed column is missing. "
            "Apply migrations/017_copyright_claims_completed.sql."
        )
        return saved


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/api/channels/me")
def portal_list_my_channels(
    x_portal_user: str = Header(default=""),
) -> dict[str, Any]:
    """Return channels owned by the current portal user."""
    user = _get_portal_user(x_portal_user)
    try:
        result = (
            get_supabase()
            .table("portal_channels")
            .select("id, channel_name, platform, status, created_at, channel_url")
            .eq("owner_id", user["id"])
            .order("created_at", desc=False)
            .limit(100)
            .execute()
        )
        items = []
        for row in result.data or []:
            items.append({
                "channel_id": row["id"],
                "name": row.get("channel_name", ""),
                "registered_at": (row.get("created_at") or "")[:10],
                "platform": row.get("platform", "youtube"),
                "status": _PORTAL_CHANNEL_STATUS_LABEL.get(
                    row.get("status", ""), row.get("status", "대기")
                ),
            })
        return {"items": items}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"portal_channels 조회 실패: {exc}") from exc


@router.get("/api/channels/me/videos")
def portal_list_channel_videos() -> dict[str, Any]:
    """Return works list from Supabase (video_id = 'work-{id}')."""
    try:
        result = (
            get_supabase()
            .table("works")
            .select("id, work_title, platform, created_at, rights_holders(rights_holder_name)")
            .eq("active_flag", "Active")
            .order("created_at", desc=False)
            .limit(100)
            .execute()
        )
        items = []
        for row in result.data or []:
            work_title = row.get("work_title", "")
            rh = row.get("rights_holders") or {}
            rights_holder_name = rh.get("rights_holder_name", "") if isinstance(rh, dict) else ""
            items.append({
                "video_id": f"work-{row['id']}",
                "title": work_title,
                "description": "",
                "channel_name": "",
                "contact_email": "",
                "rights_holder_name": rights_holder_name,
                "platform": row.get("platform") or "youtube",
                "availability_status": "이용 가능",
                "thumbnail_emoji": (work_title[0] if work_title else "?"),
                "registered_at": (row.get("created_at") or "")[:10],
                "thumbnail_url": (
                    "https://images.unsplash.com/photo-1516280440614-37939bbacd81"
                    "?auto=format&fit=crop&w=320&q=80"
                ),
                "active_channel_count": 0,
            })
        return {"items": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"works 조회 실패: {exc}") from exc


@router.post("/api/channels/me/naver-revenue-settlements")
async def portal_create_naver_revenue_settlement(
    name: str = Form(...),
    channel_name: str = Form(...),
    revenue_month: str = Form(...),
    monthly_revenue: str = Form(...),
    screenshot: UploadFile | None = File(None),
    x_portal_user: str = Header(default=""),
) -> dict[str, Any]:
    _get_portal_user(x_portal_user)
    now_dt = datetime.now(KST)
    storage_path = None
    file_name = None
    content_type = None
    file_size = None
    if screenshot and screenshot.filename:
        content = await screenshot.read()
        if not content:
            raise HTTPException(
                status_code=400, detail="수익금 화면 캡쳐 이미지 파일이 비어 있습니다."
            )
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="수익금 화면 캡쳐 이미지는 20MB 이하만 업로드할 수 있습니다.",
            )
        file_name = screenshot.filename
        content_type = screenshot.content_type or "application/octet-stream"
        file_size = len(content)
        storage_path = (
            f"{now_dt.strftime('%Y/%m')}/"
            f"{uuid.uuid4()}_{safe_storage_name(file_name)}"
        )
        upload_storage_file(NAVER_REVENUE_BUCKET, storage_path, content, content_type)
    try:
        amount = float(str(monthly_revenue).replace(",", "").strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="당월 수익금은 숫자로 입력해주세요.") from exc
    payload = {
        "portal_user_email": x_portal_user.strip(),
        "name": name.strip(),
        "channel_name": channel_name.strip(),
        "revenue_month": revenue_month.strip(),
        "monthly_revenue": amount,
        "screenshot_file_path": storage_path,
        "screenshot_file_name": file_name,
        "screenshot_content_type": content_type,
        "screenshot_file_size": file_size,
        "updated_at": now_dt.isoformat(),
    }
    payload["settlement_key"] = ":".join([
        payload["portal_user_email"] or "anonymous",
        payload["name"] or "unknown-name",
        payload["channel_name"] or "unknown-channel",
        payload["revenue_month"] or "unknown-month",
    ])
    try:
        result = (
            get_supabase()
            .table("naver_revenue_settlements")
            .upsert(payload, on_conflict="settlement_key")
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"naver_revenue_settlements 저장 실패: {exc}. "
                "migrations/020_revenue_lead_work_registration.sql 적용 여부를 확인하세요."
            ),
        ) from exc
    return {"status": "saved", "item": (result.data or [payload])[0]}


@router.post("/api/channels/me/creator-applications")
def portal_create_creator_application(body: PortalActionRequest = Body(...)) -> dict[str, Any]:
    if body.platform not in {"kakao", "naver"}:
        raise HTTPException(status_code=400, detail="platform must be kakao or naver")
    if not body.channel_id:
        raise HTTPException(status_code=400, detail="channel_id is required")
    return _make_portal_receipt("creator_application", body.model_dump())


@router.post("/api/channels/me/videos/{video_id}/usage-requests")
def portal_create_video_usage_request(
    video_id: str,
    body: PortalActionRequest = Body(...),
    x_portal_user: str = Header(default=""),
) -> dict[str, Any]:
    user = _get_portal_user(x_portal_user)
    channel = _get_portal_channel_for_user(user["id"], channel_name=body.channel_name or None)

    actual_work_id = video_id.removeprefix("work-")
    try:
        work_res = (
            get_supabase()
            .table("works")
            .select("id, work_title, platform")
            .eq("id", int(actual_work_id))
            .single()
            .execute()
        )
        work = work_res.data
    except Exception:
        work = None
    if not work:
        raise HTTPException(
            status_code=404, detail=f"works 에서 작품을 찾을 수 없습니다: {actual_work_id}"
        )

    now = datetime.now(KST)
    channel_name = channel["channel_name"]
    work_title = (body.work_title or work.get("work_title", "")).strip()
    user_email = user["email"]
    slack_ts = f"portal-{user_email}-{video_id}-{now.strftime('%Y%m%d%H%M%S')}"

    try:
        get_supabase().table("portal_videos").upsert(
            {
                "channel_id": channel["id"],
                "work_id": int(actual_work_id),
                "request_status": "pending",
                "requested_at": now.isoformat(),
            },
            on_conflict="channel_id,work_id",
        ).execute()
    except Exception:
        pass  # portal_videos 저장 실패는 비치명적

    row: dict[str, Any] = {
        "work_title": work_title,
        "channel_name": channel_name,
        "creator_email": user_email,
        "status": "pending",
        "requested_at": now.isoformat(),
        "slack_ts": slack_ts,
        "decision_note": "관리자 승인 대기",
    }
    try:
        db_result = get_supabase().table("work_requests").insert(row).execute()
        saved_row = (db_result.data or [row])[0]
    except Exception as exc:
        if "decision_note" not in str(exc):
            saved_row = row
        else:
            fallback_row = {key: value for key, value in row.items() if key != "decision_note"}
            db_result = get_supabase().table("work_requests").insert(fallback_row).execute()
            saved_row = (db_result.data or [fallback_row])[0]

    return {
        **_make_portal_receipt("A-2", {**body.model_dump(), "video_id": video_id}),
        "work_request": saved_row,
        "message": "A-2 영상권한 신청이 접수되었습니다. 관리자 승인 후 메일이 발송됩니다.",
    }


@router.get("/api/channels/me/usage-requests")
def portal_list_my_usage_requests(
    limit: int = 100,
    x_portal_user: str = Header(default=""),
) -> dict[str, Any]:
    """List work_requests for the current portal user."""
    user = _get_portal_user(x_portal_user)
    result = (
        get_supabase()
        .table("work_requests")
        .select("*")
        .eq("creator_email", user["email"])
        .order("requested_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"items": result.data or []}


@router.post("/api/channels/me/videos/{video_id}/relief-requests")
def portal_create_relief_request(
    video_id: str,
    body: PortalActionRequest = Body(...),
    x_portal_user: str = Header(default=""),
) -> dict[str, Any]:
    user = _get_portal_user(x_portal_user)
    channel = _get_portal_channel_for_user(user["id"], channel_name=body.channel_name or None)

    actual_work_id = video_id.removeprefix("work-")
    sb = get_supabase()
    try:
        work_res = (
            sb.table("works")
            .select("id, work_title, platform, rights_holder_id")
            .eq("id", int(actual_work_id))
            .single()
            .execute()
        )
        work = work_res.data
    except Exception:
        work = None
    if not work:
        raise HTTPException(
            status_code=404, detail=f"works 에서 작품을 찾을 수 없습니다: {actual_work_id}"
        )

    channel_name = channel["channel_name"]
    work_title = (body.work_title or work.get("work_title", "")).strip()
    requester_email = user["email"]
    rights_holder_name = (body.rights_holder_name or "").strip()
    work_rights_holder_id = work.get("rights_holder_id")

    claim = _insert_copyright_claim(
        sb=sb,
        work_id=int(actual_work_id),
        channel_name=channel_name,
        work_title=work_title,
        right_holder_id=work_rights_holder_id,
    )

    request = get_relief_request_service().create_request(
        requester_channel_name=channel_name,
        requester_email=requester_email,
        requester_notes=body.note or f"portal video_id={video_id}",
        submitted_via="portal",
        work_items=[
            {
                "work_id": video_id,
                "work_title": work_title,
                "rights_holder_name": rights_holder_name,
                "channel_folder_name": channel_name,
            }
        ],
    )
    return {
        **_make_portal_receipt("D-2", {**body.model_dump(), "video_id": video_id}),
        "copyright_claim": claim,
        "relief_request": {
            "request_id": request.request_id,
            "requester_channel_name": request.requester_channel_name,
            "requester_email": request.requester_email,
            "status": request.status.value,
            "submitted_via": request.submitted_via,
            "created_at": request.created_at.isoformat() if request.created_at else None,
        },
        "message": "D-2 권리 소명 신청이 relief request로 접수되었습니다.",
    }
