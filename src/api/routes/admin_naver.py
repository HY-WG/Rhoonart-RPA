"""Admin Naver/B2 routes — content catalog, analytics, collect jobs."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import (
    KST,
    build_b2_analytics_service,
    build_naver_supabase_repository,
    check_auth,
    get_naver_collect_job,
    invoke_lambda,
    set_naver_collect_job,
)
from src.api.schemas.requests import (
    B2AdminRunRequest,
    B2AnalyticsQuery,
    B2SupabaseCollectRequest,
    NaverWorkCreateRequest,
    NaverWorkReportEnabledUpdateRequest,
)
from src.services import B2AnalyticsFilters
from src.services.b2_test_report_service import B2TestReportService

router = APIRouter(tags=["naver"])
logger = logging.getLogger(__name__)


# ── Background collect job runner ────────────────────────────────────────────

def _run_naver_collect_job(job_id: str, request: B2SupabaseCollectRequest) -> None:
    set_naver_collect_job(
        job_id,
        status="running",
        phase="starting",
        message="오늘자 크롤링을 시작하는 중입니다.",
        percent=0,
        completed=0,
        total=0,
        row_count=0,
    )
    try:
        repo = build_naver_supabase_repository()
        service = B2TestReportService(
            repository=repo,
            max_clips_per_identifier=request.max_clips_per_identifier,
        )

        def _progress(update: dict[str, Any]) -> None:
            set_naver_collect_job(job_id, **update)

        rows = service.collect_enabled_reports(
            triggered_by=request.triggered_by,
            progress_callback=_progress,
        )
        summary = build_b2_analytics_service().summarize(rows)
        set_naver_collect_job(
            job_id,
            status="completed",
            phase="completed",
            message=f"오늘자 크롤링이 완료되었습니다. 저장된 영상 수: {len(rows)}",
            percent=100,
            row_count=len(rows),
            summary=summary,
            finished_at=datetime.now(KST).isoformat(),
        )
    except Exception as exc:
        set_naver_collect_job(
            job_id,
            status="failed",
            phase="failed",
            message=f"오늘자 크롤링 실패: {exc}",
            percent=100,
            error_message=str(exc),
            finished_at=datetime.now(KST).isoformat(),
        )


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/api/admin/naver/content-catalog")
@router.get("/api/admin/b2/content-catalog")
def list_b2_content_catalog(_: None = Depends(check_auth)) -> list[dict[str, Any]]:
    return build_naver_supabase_repository().list_content_catalog()


@router.post("/api/admin/naver/content-catalog")
@router.post("/api/admin/b2/content-catalog")
def create_b2_content_catalog_item(
    request: NaverWorkCreateRequest,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    return build_naver_supabase_repository().upsert_content_catalog_item(
        content_name=request.content_name.strip(),
        identifier=request.identifier.strip(),
        rights_holder_name=request.rights_holder_name.strip(),
        status=request.status.strip() or "Active",
        naver_report_enabled=request.naver_report_enabled,
    )


@router.patch("/api/admin/naver/content-catalog/{work_id}/report-enabled")
@router.patch("/api/admin/b2/content-catalog/{work_id}/report-enabled")
def update_b2_content_report_enabled(
    work_id: int,
    request: NaverWorkReportEnabledUpdateRequest,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    return build_naver_supabase_repository().update_work_report_enabled(
        work_id=work_id,
        naver_report_enabled=request.naver_report_enabled,
    )


@router.get("/api/admin/naver/rights-holders")
@router.get("/api/admin/b2/rights-holders")
def list_b2_rights_holders(
    enabled_only: bool = True,
    _: None = Depends(check_auth),
) -> list[dict[str, Any]]:
    return build_naver_supabase_repository().list_rights_holders(enabled_only=enabled_only)


@router.get("/api/admin/naver/clip-reports")
@router.get("/api/admin/b2/clip-reports")
def list_b2_clip_reports(
    limit: int = 100,
    work_title: str | None = None,
    _: None = Depends(check_auth),
) -> list[dict[str, Any]]:
    return build_naver_supabase_repository().list_clip_reports(limit=limit, work_title=work_title)


@router.get("/api/admin/naver/analytics/options")
@router.get("/api/admin/b2/analytics/options")
def get_b2_analytics_options(_: None = Depends(check_auth)) -> dict[str, Any]:
    repo = build_naver_supabase_repository()
    service = build_b2_analytics_service()
    rows = repo.list_all_clip_reports()
    return service.filter_options(rows)


@router.get("/api/admin/naver/analytics")
@router.get("/api/admin/b2/analytics")
def get_b2_analytics(
    checked_from: str | None = None,
    checked_to: str | None = None,
    uploaded_from: str | None = None,
    uploaded_to: str | None = None,
    channel_name: str | None = None,
    clip_title: str | None = None,
    work_title: str | None = None,
    rights_holder_name: str | None = None,
    platform: str | None = None,
    group_by: str = "clip",
    limit: int = 100,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    repo = build_naver_supabase_repository()
    service = build_b2_analytics_service()
    filters = B2AnalyticsFilters(
        checked_from=datetime.fromisoformat(checked_from).date() if checked_from else None,
        checked_to=datetime.fromisoformat(checked_to).date() if checked_to else None,
        uploaded_from=datetime.fromisoformat(uploaded_from).date() if uploaded_from else None,
        uploaded_to=datetime.fromisoformat(uploaded_to).date() if uploaded_to else None,
        channel_name=channel_name or None,
        clip_title=clip_title or None,
        work_title=work_title or None,
        rights_holder_name=rights_holder_name or None,
        platform=platform or None,
    )
    rows = repo.list_clip_reports_filtered(
        checked_from=checked_from,
        checked_to=checked_to,
        uploaded_from=uploaded_from,
        uploaded_to=uploaded_to,
        channel_name=channel_name,
        clip_title=clip_title,
        work_title=work_title,
        rights_holder_name=rights_holder_name,
        platform=platform,
        limit=min(limit, 1000),
    )
    filtered = service.filter_rows(rows, filters)
    return {
        "filters": {
            "checked_from": checked_from,
            "checked_to": checked_to,
            "uploaded_from": uploaded_from,
            "uploaded_to": uploaded_to,
            "channel_name": channel_name,
            "clip_title": clip_title,
            "work_title": work_title,
            "rights_holder_name": rights_holder_name,
            "platform": platform,
            "group_by": group_by,
            "limit": min(limit, 1000),
        },
        "summary": service.summarize(filtered),
        "groups": service.group_rows(filtered, group_by=group_by),
        "rows": filtered,
    }


@router.post("/api/admin/naver/looker-studio/generate-send")
@router.post("/api/admin/b2/looker-studio/generate-send")
def create_b2_looker_delivery_stub(
    request: B2AnalyticsQuery,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    if not request.rights_holder_name:
        raise HTTPException(status_code=400, detail="rights_holder_name is required")
    repo = build_naver_supabase_repository()
    service = build_b2_analytics_service()
    filters = B2AnalyticsFilters(
        checked_from=datetime.fromisoformat(request.checked_from).date() if request.checked_from else None,
        checked_to=datetime.fromisoformat(request.checked_to).date() if request.checked_to else None,
        uploaded_from=datetime.fromisoformat(request.uploaded_from).date() if request.uploaded_from else None,
        uploaded_to=datetime.fromisoformat(request.uploaded_to).date() if request.uploaded_to else None,
        channel_name=request.channel_name or None,
        clip_title=request.clip_title or None,
        work_title=request.work_title or None,
        rights_holder_name=request.rights_holder_name or None,
        platform=request.platform or None,
    )
    rows = repo.list_clip_reports_filtered(
        checked_from=request.checked_from,
        checked_to=request.checked_to,
        uploaded_from=request.uploaded_from,
        uploaded_to=request.uploaded_to,
        channel_name=request.channel_name,
        clip_title=request.clip_title,
        work_title=request.work_title,
        rights_holder_name=request.rights_holder_name,
        platform=request.platform,
        limit=1000,
    )
    filtered = service.filter_rows(rows, filters)
    rights_holders = repo.list_rights_holders(enabled_only=False)
    target = next(
        (row for row in rights_holders if row.get("rights_holder_name") == request.rights_holder_name),
        None,
    )
    payload = {
        "run_id": f"looker-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}",
        "status": "stub_only",
        "rights_holder_name": request.rights_holder_name,
        "recipient_email": target.get("email") if target else None,
        "existing_looker_studio_url": target.get("looker_studio_url") if target else None,
        "summary": service.summarize(filtered),
        "group_preview": service.group_rows(filtered, group_by=request.group_by)[:10],
        "filters": request.model_dump(),
        "next_step": "실제 Looker Studio 생성 API와 메일 발송 API 명세를 받으면 이 payload로 자동화 연결",
    }
    log_row = repo.create_looker_delivery_stub(payload)
    return {"stub": payload, "log_row": log_row}


@router.post("/api/admin/naver/run-report-stub")
@router.post("/api/admin/b2/run-report-stub")
def run_b2_report_stub(
    request: B2AdminRunRequest,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    return invoke_lambda(
        "lambda.b2_weekly_report_handler",
        {"source": request.source, "send_notifications": request.send_notifications},
    )


@router.post("/api/admin/naver/supabase/collect")
@router.post("/api/admin/b2/supabase/collect")
def collect_b2_supabase_reports(
    request: B2SupabaseCollectRequest,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    repo = build_naver_supabase_repository()
    service = B2TestReportService(
        repository=repo,
        max_clips_per_identifier=request.max_clips_per_identifier,
    )
    rows = service.collect_enabled_reports(triggered_by=request.triggered_by)
    summary = build_b2_analytics_service().summarize(rows)
    return {
        "status": "success",
        "triggered_by": request.triggered_by,
        "max_clips_per_identifier": request.max_clips_per_identifier,
        "row_count": len(rows),
        "summary": summary,
    }


@router.post("/api/admin/naver/supabase/collect-jobs")
@router.post("/api/admin/b2/supabase/collect-jobs")
def start_b2_supabase_collect_job(
    request: B2SupabaseCollectRequest,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    now = datetime.now(KST).isoformat()
    set_naver_collect_job(
        job_id,
        status="queued",
        phase="queued",
        message="오늘자 크롤링 작업이 대기열에 등록되었습니다.",
        percent=0,
        completed=0,
        total=0,
        row_count=0,
        triggered_by=request.triggered_by,
        max_clips_per_identifier=request.max_clips_per_identifier,
        created_at=now,
    )
    thread = threading.Thread(
        target=_run_naver_collect_job,
        args=(job_id, request),
        daemon=True,
    )
    thread.start()
    return get_naver_collect_job(job_id) or {"job_id": job_id, "status": "queued"}


@router.get("/api/admin/naver/supabase/collect-jobs/latest")
@router.get("/api/admin/b2/supabase/collect-jobs/latest")
def get_latest_b2_supabase_collect_job(_: None = Depends(check_auth)) -> dict[str, Any]:
    repo = build_naver_supabase_repository()
    latest = repo.latest_daily_report_run()
    if not latest:
        return {
            "job_id": "latest",
            "status": "empty",
            "phase": "empty",
            "message": "아직 크롤링 실행 기록이 없습니다.",
            "percent": 0,
            "completed": 0,
            "total": 0,
            "row_count": 0,
        }
    status = str(latest.get("status") or "")
    finished_at = str(latest.get("finished_at") or "")
    checked_at = str(latest.get("checked_at") or "")
    return {
        "job_id": str(latest.get("run_id") or "latest"),
        "run_id": latest.get("run_id"),
        "status": "completed" if status == "success" else status,
        "phase": "completed" if status == "success" else status,
        "message": (
            f"마지막 크롤링 기록입니다. 저장된 영상 수: {latest.get('row_count') or 0}"
            if status == "success"
            else str(latest.get("error_message") or "마지막 크롤링 기록입니다.")
        ),
        "percent": 100,
        "completed": int(latest.get("row_count") or 0),
        "total": int(latest.get("row_count") or 0),
        "row_count": int(latest.get("row_count") or 0),
        "triggered_by": latest.get("triggered_by"),
        "created_at": checked_at,
        "updated_at": finished_at or checked_at,
        "finished_at": finished_at or checked_at,
        "error_message": latest.get("error_message"),
    }


@router.get("/api/admin/naver/supabase/collect-jobs/{job_id}")
@router.get("/api/admin/b2/supabase/collect-jobs/{job_id}")
def get_b2_supabase_collect_job(
    job_id: str,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    job = get_naver_collect_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="collect job not found")
    return job
