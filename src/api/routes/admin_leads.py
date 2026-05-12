"""Admin lead management routes — /api/admin/leads/*"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from googleapiclient.discovery import build

from src.api.dependencies import (
    KST,
    LEAD_SUBSCRIBER_METRICS,
    LEAD_SUBSCRIBER_METRICS_LOCK,
    check_auth,
    get_supabase,
)
from src.api.schemas.requests import LeadBlockRequest, LeadPromoteRequest, LeadSendEmailRequest
from src.config import settings
from src.core.notifiers.email_notifier import EmailNotifier

router = APIRouter(tags=["leads"])
logger = logging.getLogger(__name__)


def _lead_discovery_summary_message(result: dict[str, Any]) -> str:
    discovered = int(result.get("discovered") or 0)
    upserted = int(result.get("upserted") or 0)
    tier_a = int(result.get("tier_a") or 0)
    tier_b = int(result.get("tier_b") or 0)
    tier_bp = int(result.get("tier_b_potential") or 0)
    tier_c = int(result.get("tier_c") or 0)

    if upserted > 0:
        return (
            f"신규 리드 채널 {upserted}개가 검토대기 목록에 반영되었습니다. "
            f"등급별로 A {tier_a}개, B {tier_b}개, B? {tier_bp}개입니다."
        )
    if discovered <= 0:
        return (
            "신규 리드 채널이 발굴되지 않았습니다. YouTube 검색 결과에서 시드 채널과 "
            "차단리스트를 제외한 뒤 남는 후보가 없었거나, 드라마·영화 클립 채널로 "
            "판별되는 후보가 없었습니다."
        )
    if tier_c >= discovered:
        return (
            f"신규 리드 채널이 발굴되지 않았습니다. 후보 채널 {discovered}개를 찾았지만 "
            "모두 기준 미달(C등급)로 분류되어 검토대기 목록에는 추가하지 않았습니다."
        )
    return (
        f"신규 리드 채널이 발굴되지 않았습니다. 후보 채널 {discovered}개 중 "
        f"A/B/B? 기준을 통과한 채널이 없었습니다. 기준 미달(C등급)은 {tier_c}개입니다."
    )


_COLD_EMAIL_HTML = """\
<html>
<body style="font-family:sans-serif;color:#333;line-height:1.6;max-width:600px;">
<p>안녕하세요, <strong>{channel_name}</strong> 채널 담당자님.</p>
<p>저는 <strong>루나트</strong>에서 크리에이터 파트너십을 담당하고 있습니다.<br>
귀 채널의 콘텐츠를 인상 깊게 살펴보았으며, 함께 성장할 수 있는 기회를 제안드리고자 연락드렸습니다.</p>
<h3 style="color:#1a73e8;">제안 내용</h3>
<p>루나트는 유튜브 채널의 수익화 및 성장을 지원하는 MCN으로,<br>
콘텐츠 기획·배포·저작권 관리·광고 수익화 등 다양한 분야에서 파트너 채널을 지원하고 있습니다.</p>
<p>관심이 있으시다면 이 메일로 회신 주세요. 담당자가 빠르게 연락드리겠습니다.</p>
<p>감사합니다.<br><strong>루나트</strong> 파트너십 팀 드림</p>
</body>
</html>"""


@router.get("/api/admin/leads")
def list_leads(
    review_status: str = "pending",
    grade: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Supabase lead_channels 조회. review_status 별 필터링."""
    sb = get_supabase()
    q = (
        sb.table("lead_channels")
        .select("*")
        .order("monthly_views", desc=True)
        .range(offset, offset + limit - 1)
    )
    if review_status != "all":
        q = q.eq("review_status", review_status)
    if grade:
        q = q.eq("grade", grade)
    result = q.execute()
    items = result.data or []
    with LEAD_SUBSCRIBER_METRICS_LOCK:
        for row in items:
            channel_id = str(row.get("channel_id") or "")
            if channel_id in LEAD_SUBSCRIBER_METRICS:
                row.update(LEAD_SUBSCRIBER_METRICS[channel_id])
    total = sb.table("lead_channels").select("channel_id", count="exact").execute()
    return {"items": items, "total": getattr(total, "count", 0)}


@router.post("/api/admin/leads/refresh-subscribers")
def refresh_lead_subscribers(_: None = Depends(check_auth)) -> dict[str, Any]:
    """YouTube API로 리드 채널 구독자 수를 갱신한다."""
    if not settings.YOUTUBE_API_KEY:
        raise HTTPException(status_code=500, detail="YOUTUBE_API_KEY is not configured.")
    sb = get_supabase()
    result = (
        sb.table("lead_channels")
        .select("channel_id,subscriber_count")
        .eq("platform", "youtube")
        .limit(50)
        .execute()
    )
    leads = [row for row in (result.data or []) if row.get("channel_id")]
    if not leads:
        return {
            "status": "completed",
            "total": 0,
            "updated": 0,
            "percent": 100,
            "last_run_at": datetime.now(KST).isoformat(),
        }

    youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY, cache_discovery=False)
    now = datetime.now(KST).isoformat()
    updated = 0
    failed: list[str] = []
    metrics: list[dict[str, Any]] = []
    for start in range(0, len(leads), 50):
        batch = leads[start : start + 50]
        ids = [str(row["channel_id"]) for row in batch if not str(row["channel_id"]).startswith("@")]
        if not ids:
            continue
        response = (
            youtube.channels()
            .list(part="statistics", id=",".join(ids), maxResults=len(ids))
            .execute()
        )
        stats_by_id = {
            item["id"]: int(item.get("statistics", {}).get("subscriberCount") or 0)
            for item in response.get("items", [])
        }
        for row in batch:
            channel_id = str(row.get("channel_id") or "")
            if channel_id not in stats_by_id:
                failed.append(channel_id)
                continue
            previous = row.get("subscriber_count_current") or row.get("subscriber_count") or 0
            current = stats_by_id[channel_id]
            payload = {
                "subscriber_count": current,
                "subscriber_count_previous": int(previous or 0),
                "subscriber_count_current": current,
                "subscriber_delta": current - int(previous or 0),
                "subscriber_refreshed_at": now,
            }
            metrics.append({"channel_id": channel_id, **payload})
            try:
                sb.table("lead_channels").update(payload).eq("channel_id", channel_id).execute()
            except Exception as exc:
                if not any(key in str(exc) for key in (
                    "subscriber_count_previous", "subscriber_count_current",
                    "subscriber_delta", "subscriber_refreshed_at",
                )):
                    raise
                sb.table("lead_channels").update(
                    {"subscriber_count": current}
                ).eq("channel_id", channel_id).execute()
                with LEAD_SUBSCRIBER_METRICS_LOCK:
                    LEAD_SUBSCRIBER_METRICS[channel_id] = payload
            updated += 1
    return {
        "status": "completed",
        "total": len(leads),
        "updated": updated,
        "failed": failed[:20],
        "metrics": metrics,
        "percent": 100,
        "last_run_at": now,
    }


@router.get("/api/admin/leads/summary")
def lead_summary(_: None = Depends(check_auth)) -> dict[str, Any]:
    sb = get_supabase()
    result = sb.table("lead_channels").select("*").limit(1000).execute()
    rows = result.data or []
    total = len(rows)
    latest = max(
        [str(row.get("subscriber_refreshed_at") or row.get("discovered_at") or "") for row in rows],
        default="",
    )
    try:
        latest_run = (
            sb.table("lead_discovery_runs")
            .select("*")
            .order("finished_at", desc=True)
            .limit(1)
            .execute()
        )
        latest_run_row = (latest_run.data or [{}])[0]
        latest_run_result = latest_run_row.get("result_json") or {}
    except Exception:
        latest_run = (
            sb.table("automation_runs")
            .select("result,finished_at,started_at")
            .eq("task_id", "C-1")
            .order("finished_at", desc=True)
            .limit(1)
            .execute()
        )
        latest_run_row = (latest_run.data or [{}])[0]
        latest_run_result = latest_run_row.get("result") or {}
    discovered_count = int(latest_run_result.get("discovered") or 0)
    upserted_count = int(latest_run_result.get("upserted") or 0)
    excluded_count = int(latest_run_result.get("tier_c") or 0)
    drama_titles = latest_run_result.get("drama_titles") or []
    detail_log = latest_run_result.get("detail_log") or latest_run_row.get("detail_log") or []
    return {
        "total": total,
        "promoted": sum(1 for row in rows if row.get("review_status") == "promoted"),
        "blocked": sum(1 for row in rows if row.get("review_status") == "blocked"),
        "pending": sum(1 for row in rows if row.get("review_status") == "pending"),
        "last_run_at": latest,
        "last_discovery_run_at": latest_run_row.get("finished_at") or latest_run_row.get("started_at") or "",
        "discovered_count": discovered_count,
        "new_lead_count": upserted_count,
        "excluded_count": excluded_count,
        "discovery_message": _lead_discovery_summary_message(latest_run_result),
        "drama_titles": drama_titles if isinstance(drama_titles, list) else [],
        "detail_log": detail_log if isinstance(detail_log, list) else [],
        "progress_percent": 100 if total else 0,
    }


@router.post("/api/admin/leads/bulk-send-email")
def bulk_send_lead_email(
    body: LeadSendEmailRequest = Body(default_factory=LeadSendEmailRequest),
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    """검토 대기 상태의 이메일 보유 리드 전체에 콜드메일 일괄 발송."""
    sb = get_supabase()
    now = datetime.now(KST).isoformat()

    result = (
        sb.table("lead_channels")
        .select("channel_id,channel_name,email,email_status")
        .eq("review_status", "pending")
        .neq("email_status", "sent")
        .not_.is_("email", "null")
        .execute()
    )
    targets = [r for r in (result.data or []) if r.get("email")]

    sender_email = os.environ.get("SENDER_EMAIL", "hoyoungy2@gmail.com")
    use_ses = os.environ.get("USE_SES", "true").lower() == "true"
    notifier = EmailNotifier(sender_email=sender_email, use_ses=use_ses)

    sent, skipped, failed = [], [], []
    for lead in targets:
        cid = lead["channel_id"]
        cname = lead.get("channel_name", "채널")
        cemail = lead["email"]
        try:
            if not body.dry_run:
                subject = f"[루나트] {cname} 채널 제휴 제안드립니다"
                html_body = _COLD_EMAIL_HTML.format(channel_name=cname)
                success = notifier.send(recipient=cemail, message=html_body, subject=subject, html=True)
                if success:
                    sb.table("lead_channels").update({"email_status": "sent"}).eq("channel_id", cid).execute()
                    sent.append(cid)
                else:
                    sb.table("lead_channels").update({"email_status": "bounced"}).eq("channel_id", cid).execute()
                    failed.append(cid)
            else:
                sent.append(cid)
        except Exception as exc:
            logger.warning("bulk send failed for %s: %s", cid, exc)
            failed.append(cid)

    return {
        "status": "completed" if not body.dry_run else "dry_run",
        "total": len(targets),
        "sent": len(sent),
        "failed": len(failed),
        "skipped": len(skipped),
        "dry_run": body.dry_run,
    }


@router.post("/api/admin/leads/{channel_id}/promote")
def promote_lead_to_seed(
    channel_id: str,
    body: LeadPromoteRequest = Body(default_factory=LeadPromoteRequest),
) -> dict[str, Any]:
    """리드 채널을 seed_channel로 승격 + review_status='promoted' 업데이트."""
    sb = get_supabase()
    now = datetime.now(KST).isoformat()

    lead_res = sb.table("lead_channels").select("*").eq("channel_id", channel_id).single().execute()
    lead = lead_res.data
    if not lead:
        raise HTTPException(status_code=404, detail=f"lead not found: {channel_id}")
    if lead.get("review_status") == "blocked":
        raise HTTPException(status_code=409, detail="이미 차단된 채널입니다.")

    seed_payload = {
        "channel_url": lead["channel_url"],
        "channel_name": lead.get("channel_name"),
        "channel_title": lead.get("channel_name"),
        "channel_id": channel_id,
        "platform": lead.get("platform", "youtube"),
        "active": True,
        "status": "active",
        "promoted_from_lead_id": channel_id,
        "promoted_by": body.promoted_by,
        "promoted_at": now,
        "updated_at": now,
    }
    existing_seed = (
        sb.table("seed_channel")
        .select("id")
        .eq("channel_url", lead["channel_url"])
        .limit(1)
        .execute()
    )
    if existing_seed.data:
        sb.table("seed_channel").update(seed_payload).eq("id", existing_seed.data[0]["id"]).execute()
    else:
        sb.table("seed_channel").insert(seed_payload).execute()

    sb.table("lead_channels").update(
        {"review_status": "promoted", "reviewed_at": now, "reviewed_by": body.promoted_by}
    ).eq("channel_id", channel_id).execute()

    return {
        "status": "promoted",
        "channel_id": channel_id,
        "channel_name": lead.get("channel_name"),
        "channel_url": lead.get("channel_url"),
        "promoted_by": body.promoted_by,
        "promoted_at": now,
    }


@router.post("/api/admin/leads/{channel_id}/block")
def block_lead(
    channel_id: str,
    body: LeadBlockRequest = Body(default_factory=LeadBlockRequest),
) -> dict[str, Any]:
    """리드 채널을 차단 + channel_blocklist 등록."""
    sb = get_supabase()
    now = datetime.now(KST).isoformat()

    lead_res = sb.table("lead_channels").select("*").eq("channel_id", channel_id).single().execute()
    lead = lead_res.data
    if not lead:
        raise HTTPException(status_code=404, detail=f"lead not found: {channel_id}")

    sb.table("channel_blocklist").upsert(
        {
            "channel_id": channel_id,
            "channel_name": lead.get("channel_name"),
            "channel_url": lead.get("channel_url"),
            "platform": lead.get("platform", "youtube"),
            "reason": body.reason,
            "blocked_at": now,
            "blocked_by": body.blocked_by,
        },
        on_conflict="channel_id",
    ).execute()

    sb.table("lead_channels").update(
        {
            "review_status": "blocked",
            "reviewed_at": now,
            "reviewed_by": body.blocked_by,
            "block_reason": body.reason,
        }
    ).eq("channel_id", channel_id).execute()

    try:
        from src.core.crawlers._blocklist import block_channels as _block_json
        _block_json(
            [{"channel_id": channel_id, "name": lead.get("channel_name", "")}],
            reason=body.reason,
        )
    except Exception:
        pass

    return {
        "status": "blocked",
        "channel_id": channel_id,
        "channel_name": lead.get("channel_name"),
        "reason": body.reason,
        "blocked_by": body.blocked_by,
        "blocked_at": now,
    }


@router.delete("/api/admin/leads/{channel_id}/block")
def unblock_lead(channel_id: str) -> dict[str, Any]:
    """차단 해제 — channel_blocklist 삭제 + review_status → pending."""
    sb = get_supabase()
    sb.table("channel_blocklist").delete().eq("channel_id", channel_id).execute()
    sb.table("lead_channels").update(
        {"review_status": "pending", "reviewed_at": None, "block_reason": None}
    ).eq("channel_id", channel_id).execute()

    try:
        from src.core.crawlers._blocklist import unblock_channels as _unblock_json
        _unblock_json([channel_id])
    except Exception:
        pass

    return {"status": "unblocked", "channel_id": channel_id}


@router.post("/api/admin/leads/{channel_id}/send-email")
def send_lead_email(
    channel_id: str,
    body: LeadSendEmailRequest = Body(default_factory=LeadSendEmailRequest),
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    """단일 리드 채널에 콜드메일 발송."""
    sb = get_supabase()
    now = datetime.now(KST).isoformat()

    result = sb.table("lead_channels").select("*").eq("channel_id", channel_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Lead not found: {channel_id}")
    lead = result.data[0]

    if not lead.get("email"):
        raise HTTPException(status_code=400, detail="이메일 주소가 없는 채널입니다.")

    if body.dry_run:
        return {
            "status": "dry_run",
            "channel_id": channel_id,
            "channel_name": lead.get("channel_name"),
            "email": lead.get("email"),
            "dry_run": True,
            "sent_at": None,
        }

    channel_name = lead.get("channel_name", "채널")
    recipient_email = lead["email"]
    subject = f"[루나트] {channel_name} 채널 제휴 제안드립니다"
    html_body = _COLD_EMAIL_HTML.format(channel_name=channel_name)

    sender_email = os.environ.get("SENDER_EMAIL", "hoyoungy2@gmail.com")
    use_ses = os.environ.get("USE_SES", "true").lower() == "true"
    notifier = EmailNotifier(sender_email=sender_email, use_ses=use_ses)
    success = notifier.send(recipient=recipient_email, message=html_body, subject=subject, html=True)

    if success:
        sb.table("lead_channels").update({"email_status": "sent"}).eq("channel_id", channel_id).execute()
    else:
        sb.table("lead_channels").update({"email_status": "bounced"}).eq("channel_id", channel_id).execute()
        raise HTTPException(status_code=500, detail=f"이메일 발송 실패: {recipient_email}")

    return {
        "status": "sent",
        "channel_id": channel_id,
        "channel_name": channel_name,
        "email": recipient_email,
        "dry_run": False,
        "sent_at": now,
    }
