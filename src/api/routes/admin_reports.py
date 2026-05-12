"""Admin reports routes — Metabase, Naver report schedules."""
from __future__ import annotations

import logging
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import (
    KST,
    NAVER_REPORT_SCHEDULES_CACHE,
    NAVER_REPORT_SCHEDULES_CACHE_LOCK,
    NAVER_REPORT_SCHEDULES_CACHE_TTL_SECONDS,
    build_naver_supabase_repository,
    check_auth,
)
from src.api.schemas.requests import (
    MetabaseReportSendRequest,
    NaverReportScheduleUpdateRequest,
)
from src.config import settings

router = APIRouter(tags=["reports"])
logger = logging.getLogger(__name__)

LOCAL_METABASE_PORT = "3000"
LOCAL_FRONTEND_PORTS = {"3001"}

_KO_WEEKDAY = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토", 7: "일"}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_metabase_url(url: str) -> str:
    """Fix old local public dashboard URLs saved with the frontend port."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw
    if parsed.path.startswith("/public/dashboard/") and parsed.hostname in {
        "localhost",
        "127.0.0.1",
    }:
        port = str(parsed.port or "")
        if port in LOCAL_FRONTEND_PORTS:
            host = parsed.hostname or "localhost"
            return urlunparse(parsed._replace(netloc=f"{host}:{LOCAL_METABASE_PORT}"))
    return raw


def _split_emails(value: Any) -> list[str]:
    if not value:
        return []
    parts = str(value).replace(";", ",").split(",")
    return [part.strip() for part in parts if "@" in part.strip()]


def _send_metabase_report_email(
    *,
    recipients: list[str],
    rights_holder_name: str,
    dashboard_url: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    sender_email = settings.SENDER_EMAIL or settings.SMTP_USER
    if not sender_email or not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise HTTPException(
            status_code=500,
            detail=(
                "SMTP settings are missing. Set SENDER_EMAIL, SMTP_HOST, "
                "SMTP_USER, and SMTP_PASSWORD in .env."
            ),
        )

    subject = f"[Rhoonart] {rights_holder_name} 네이버 클립 성과보고"
    text_body = (
        f"{rights_holder_name} 담당자님,\n\n"
        "네이버 클립 성과 대시보드 공유드립니다.\n\n"
        f"{dashboard_url}\n\n"
        "위 링크는 Metabase 로그인 없이 열람 가능한 공개 대시보드 링크입니다.\n"
        "감사합니다.\n"
    )
    html_body = f"""
    <p>{rights_holder_name} 담당자님,</p>
    <p>네이버 클립 성과 대시보드 공유드립니다.</p>
    <p><a href="{dashboard_url}">Metabase 대시보드 열기</a></p>
    <p>위 링크는 Metabase 로그인 없이 열람 가능한 공개 대시보드 링크입니다.</p>
    <p>감사합니다.</p>
    """

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = ", ".join(recipients)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    logger.info(
        "metabase report email send start rights_holder=%s recipients=%s smtp_host=%s",
        rights_holder_name,
        recipients,
        settings.SMTP_HOST,
    )
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            "metabase report email send failed rights_holder=%s elapsed_ms=%s",
            rights_holder_name,
            elapsed_ms,
        )
        raise HTTPException(
            status_code=502,
            detail=f"SMTP 발송 실패: {exc} (elapsed_ms={elapsed_ms})",
        ) from exc

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    sent_at = datetime.now(KST).isoformat()
    logger.info(
        "metabase report email send success rights_holder=%s elapsed_ms=%s",
        rights_holder_name,
        elapsed_ms,
    )
    return {
        "status": "sent",
        "rights_holder_name": rights_holder_name,
        "recipients": recipients,
        "dashboard_url": dashboard_url,
        "sent_at": sent_at,
        "elapsed_ms": elapsed_ms,
    }


def _is_schedule_due(schedule: dict[str, Any], now: datetime) -> bool:
    if not schedule.get("enabled"):
        return False
    weekday = now.weekday() + 1
    if weekday not in [int(day) for day in schedule.get("days_of_week") or []]:
        return False
    send_time = str(schedule.get("send_time") or "11:00")[:5]
    try:
        target_time = datetime.strptime(send_time, "%H:%M").time()
    except ValueError:
        target_time = datetime.strptime("11:00", "%H:%M").time()
    if now.time() < target_time:
        return False
    last_sent_at = schedule.get("last_sent_at")
    if last_sent_at:
        try:
            last_sent = datetime.fromisoformat(str(last_sent_at).replace("Z", "+00:00"))
            if last_sent.astimezone(KST).date() == now.date():
                return False
        except ValueError:
            pass
    return True


def run_due_naver_report_schedules_once(*, execution_mode: str = "schedule") -> dict[str, Any]:
    """Check all Naver report schedules and fire any that are due."""
    repo = build_naver_supabase_repository()
    now = datetime.now(KST)
    run_id = f"naver-schedule-{now.strftime('%Y%m%d%H%M%S')}"
    results: list[dict[str, Any]] = []
    schedules = repo.list_report_schedules()
    for schedule in schedules:
        if not _is_schedule_due(schedule, now):
            continue
        rights_holder_name = str(schedule.get("rights_holder_name") or "")
        dashboard_url = _normalize_metabase_url(str(schedule.get("metabase_embed_url") or "").strip())
        recipients = _split_emails(",".join(schedule.get("recipient_emails") or []))
        try:
            if not dashboard_url:
                raise RuntimeError("Metabase public dashboard URL is not configured.")
            if not recipients:
                raise RuntimeError("Recipient email is not configured.")
            sent = _send_metabase_report_email(
                recipients=recipients,
                rights_holder_name=rights_holder_name,
                dashboard_url=dashboard_url,
            )
            repo.mark_report_schedule_sent(
                schedule_id=int(schedule["schedule_id"]),
                sent_at=sent["sent_at"],
            )
            result = {
                "status": "sent",
                "rights_holder_name": rights_holder_name,
                "recipients": recipients,
                "dashboard_url": dashboard_url,
                "sent_at": sent["sent_at"],
                "elapsed_ms": sent.get("elapsed_ms"),
            }
        except Exception as exc:
            result = {
                "status": "failed",
                "rights_holder_name": rights_holder_name,
                "error": str(exc),
            }
            logger.warning("naver report schedule failed for %s: %s", rights_holder_name, exc)
        try:
            repo.create_report_delivery_log(
                {
                    "run_id": run_id,
                    "execution_mode": execution_mode,
                    "send_notifications": True,
                    "status": result["status"],
                    "result_json": result,
                    **result,
                }
            )
        except Exception as log_exc:
            logger.warning("naver report delivery log insert failed: %s", log_exc)
        results.append(result)
    if results:
        with NAVER_REPORT_SCHEDULES_CACHE_LOCK:
            NAVER_REPORT_SCHEDULES_CACHE.clear()
    return {
        "run_id": run_id,
        "checked_at": now.isoformat(),
        "timezone": "Asia/Seoul",
        "checked_schedule_count": len(schedules),
        "due_count": len(results),
        "results": results,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/api/admin/reports/metabase")
def metabase_report_naver() -> dict[str, Any]:
    """Return Naver Clip Metabase dashboard embed URLs per rights holder."""
    rights_holders: list[dict[str, Any]] = []
    any_url_stored = False
    try:
        repo = build_naver_supabase_repository()
        rh_list = repo.list_rights_holders(enabled_only=False)
        seen_names: set[str] = set()
        for rh in rh_list:
            name = rh.get("rights_holder_name", "")
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            embed_url = _normalize_metabase_url(rh.get("metabase_embed_url") or "")
            if embed_url:
                any_url_stored = True
            email = rh.get("email") or rh.get("mail") or ""
            rights_holders.append({
                "id": name.replace(" ", "-").lower(),
                "name": name,
                "embed_url": embed_url,
                "email": email,
                "mail": email,
                "naver_report_enabled": bool(rh.get("naver_report_enabled")),
                "configured": bool(embed_url),
            })
    except Exception:
        pass

    return {
        "title": "네이버 클립 성과 확인",
        "embed_url": "",
        "configured": any_url_stored,
        "env_key": "METABASE_NAVER_CLIP_URL",
        "reports": rights_holders,
    }


@router.post("/api/admin/reports/metabase/send")
def send_metabase_report_naver(request: MetabaseReportSendRequest) -> dict[str, Any]:
    repo = build_naver_supabase_repository()
    rights_holders = repo.list_rights_holders(enabled_only=False, limit=1000)
    target = next(
        (row for row in rights_holders if row.get("rights_holder_name") == request.rights_holder_name),
        None,
    )
    if not target:
        raise HTTPException(status_code=404, detail="Rights holder not found.")

    dashboard_url = _normalize_metabase_url(str(target.get("metabase_embed_url") or "").strip())
    if not dashboard_url:
        raise HTTPException(status_code=400, detail="Metabase public dashboard URL is not configured.")

    recipients = _split_emails(target.get("email") or target.get("mail"))
    if not recipients:
        raise HTTPException(status_code=400, detail="Recipient email is not configured in naver_rights_holders.")

    try:
        sent = _send_metabase_report_email(
            recipients=recipients,
            rights_holder_name=request.rights_holder_name,
            dashboard_url=dashboard_url,
        )
        try:
            schedule = next(
                (
                    item
                    for item in repo.list_report_schedules()
                    if item.get("rights_holder_name") == request.rights_holder_name
                ),
                None,
            )
            if schedule and schedule.get("schedule_id"):
                repo.mark_report_schedule_sent(
                    schedule_id=int(schedule["schedule_id"]),
                    sent_at=sent["sent_at"],
                )
            repo.create_report_delivery_log(
                {
                    "run_id": f"naver-manual-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}",
                    "execution_mode": "manual",
                    "send_notifications": True,
                    "status": "sent",
                    "result_json": sent,
                    **sent,
                }
            )
        except Exception as log_exc:
            logger.warning("manual metabase report status/log update failed: %s", log_exc)
        with NAVER_REPORT_SCHEDULES_CACHE_LOCK:
            NAVER_REPORT_SCHEDULES_CACHE.clear()
        return sent
    except HTTPException as exc:
        try:
            repo.create_report_delivery_log(
                {
                    "run_id": f"naver-manual-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}",
                    "execution_mode": "manual",
                    "send_notifications": True,
                    "status": "failed",
                    "rights_holder_name": request.rights_holder_name,
                    "recipients": recipients,
                    "dashboard_url": dashboard_url,
                    "error": exc.detail,
                }
            )
        except Exception as log_exc:
            logger.warning("manual metabase report failure log insert failed: %s", log_exc)
        raise


@router.get("/api/admin/reports/naver/schedules")
def list_naver_report_schedules() -> dict[str, Any]:
    now = time.monotonic()
    with NAVER_REPORT_SCHEDULES_CACHE_LOCK:
        cached = NAVER_REPORT_SCHEDULES_CACHE.get("payload")
        cached_at = float(NAVER_REPORT_SCHEDULES_CACHE.get("cached_at") or 0)
        if cached and now - cached_at < NAVER_REPORT_SCHEDULES_CACHE_TTL_SECONDS:
            return cached

    repo = build_naver_supabase_repository()
    with ThreadPoolExecutor(max_workers=3) as executor:
        schedules_future = executor.submit(repo.list_report_schedules)
        works_future = executor.submit(repo.list_enabled_report_works)
        logs_future = executor.submit(repo.list_report_delivery_logs, limit=20)
        payload = {
            "schedules": schedules_future.result(),
            "works": works_future.result(),
            "logs": logs_future.result(),
        }

    with NAVER_REPORT_SCHEDULES_CACHE_LOCK:
        NAVER_REPORT_SCHEDULES_CACHE["payload"] = payload
        NAVER_REPORT_SCHEDULES_CACHE["cached_at"] = time.monotonic()
    return payload


@router.patch("/api/admin/reports/naver/schedules/{schedule_id}")
def update_naver_report_schedule(
    schedule_id: int,
    request: NaverReportScheduleUpdateRequest,
) -> dict[str, Any]:
    invalid_days = [day for day in request.days_of_week if day < 1 or day > 7]
    if invalid_days:
        raise HTTPException(status_code=400, detail="days_of_week must be between 1 and 7.")
    try:
        datetime.strptime(request.send_time[:5], "%H:%M")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="send_time must be HH:MM.") from exc

    recipients = [
        email.strip()
        for email in request.recipient_emails
        if "@" in email.strip()
    ]
    repo = build_naver_supabase_repository()
    updated = repo.update_report_schedule(
        schedule_id=schedule_id,
        payload={
            "enabled": request.enabled,
            "days_of_week": request.days_of_week,
            "send_time": request.send_time[:5],
            "timezone": request.timezone or "Asia/Seoul",
            "recipient_emails": recipients,
            "include_work_ids": sorted(set(request.include_work_ids)),
        },
    )
    with NAVER_REPORT_SCHEDULES_CACHE_LOCK:
        NAVER_REPORT_SCHEDULES_CACHE.clear()
    return updated


@router.post("/api/admin/reports/naver/schedules/run-due")
def run_due_naver_report_schedules_route(
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    return run_due_naver_report_schedules_once(execution_mode="manual_run_due")
