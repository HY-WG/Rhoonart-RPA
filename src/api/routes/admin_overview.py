"""Admin overview and misc routes — /, /health, /api/admin/overview."""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import HTMLResponse, StreamingResponse

from src.api.dependencies import (
    KST,
    NAVER_REPORT_SCHEDULES_CACHE,
    NAVER_REPORT_SCHEDULES_CACHE_LOCK,
    build_naver_supabase_repository,
    check_auth,
    get_supabase,
)
from src.api.schemas.requests import A2ManualRequestStub
from src.backoffice.dependencies import get_relief_request_service
from src.handlers.a2_work_approval import parse_manual_request

router = APIRouter(tags=["overview"])

_KO_WEEKDAY = {1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토", 7: "일"}


def _format_schedule_str(days_of_week: list[Any], send_time: str) -> str:
    day_labels = [_KO_WEEKDAY.get(int(d), str(d)) for d in sorted(int(d) for d in days_of_week)]
    try:
        h, m = map(int, send_time[:5].split(":"))
        ampm = "오전" if h < 12 else "오후"
        hh = h if h <= 12 else h - 12
        time_label = f"{ampm} {hh}시" + (f" {m}분" if m else "")
    except Exception:
        time_label = send_time
    return " ".join(day_labels) + " " + time_label


def _next_weekday_5th(year: int, month: int) -> datetime:
    from datetime import timedelta
    d = datetime(year, month, 5)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Rhoonart RPA Control Server</title>
      <style>
        body { font-family: "Segoe UI", "Apple SD Gothic Neo", sans-serif; margin: 40px; color: #17212b; background: #f7f4ee; }
        .card { max-width: 880px; background: white; border: 1px solid #ddd2c2; border-radius: 16px; padding: 24px; box-shadow: 0 10px 24px rgba(23,33,43,.08); }
        h1 { margin-top: 0; }
        ul { line-height: 1.8; }
        a { color: #1b6b73; text-decoration: none; font-weight: 600; }
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Rhoonart RPA Control Server</h1>
        <p>This server combines the dashboard, legacy trigger APIs, and the D-2 backoffice in one place.</p>
        <ul>
          <li><a href="/a3/apply">A-3 Homepage Intake Form</a></li>
          <li><a href="/d3/apply">D-3 Kakao Creator Intake Form</a></li>
          <li><a href="/dashboard/">Integration Test Dashboard</a></li>
          <li><a href="/admin/b2">B-2 Analytics Admin</a></li>
          <li><a href="/api/approvals/pending">승인 대기 목록 (Approvals)</a></li>
          <li><a href="/docs">Control Server API Docs</a></li>
          <li><a href="/relief/docs">D-2 Backoffice API Docs</a></li>
        </ul>
      </div>
    </body>
    </html>
    """


@router.get("/health")
def health() -> dict[str, Any]:
    from src.config import settings
    return {
        "status": "ok",
        "time": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "dashboard_repository": settings.INTEGRATION_DASHBOARD_DB_TYPE,
        "auth_required": bool(settings.X_INTERN_TOKEN),
        "version": "2026-05-07-fix",
    }


@router.get("/api/admin/overview")
def admin_overview(_: None = Depends(check_auth)) -> dict[str, Any]:
    """어드민 홈 카드용 요약 지표."""
    sb = get_supabase()

    def _count(table: str, column: str | None = None, value: str | bool | None = None) -> int:
        try:
            query = sb.table(table).select("id", count="exact")
            if column is not None:
                query = query.eq(column, value)
            result = query.execute()
            return int(getattr(result, "count", 0) or 0)
        except Exception:
            return 0

    work_pending = _count("work_requests", "status", "pending")
    work_total = _count("work_requests")
    leads_total = _count("lead_channels")
    relief_total = 0
    try:
        relief_total = len(get_relief_request_service().list_requests())
    except Exception:
        relief_total = 0

    schedules = []
    try:
        repo = build_naver_supabase_repository()
        schedules = repo.list_report_schedules()
    except Exception:
        pass
    active_schedules = [row for row in schedules if row.get("enabled")]

    now = datetime.now(KST)
    rh_card_items: dict[str, dict[str, Any]] = {}
    for sched in schedules:
        if not sched.get("enabled"):
            continue
        name = str(sched.get("rights_holder_name") or "").strip()
        if not name:
            continue
        days = sched.get("days_of_week") or []
        send_time = str(sched.get("send_time") or "11:00")[:5]
        schedule_str = _format_schedule_str(days, send_time) if days else ""
        last_sent_at = sched.get("last_sent_at")
        status_label = "보고 대기중"
        if last_sent_at:
            try:
                sent_dt = datetime.fromisoformat(str(last_sent_at).replace("Z", "+00:00"))
                sent_kst = sent_dt.astimezone(KST)
                if sent_kst.year == now.year and sent_kst.month == now.month:
                    status_label = "보고 완료"
            except Exception:
                pass
        rh_card_items[name] = {"name": name, "schedule": schedule_str, "status": status_label}
    rights_holders_list = list(rh_card_items.values())

    current_5th = _next_weekday_5th(now.year, now.month)
    next_year = now.year + (1 if now.month == 12 else 0)
    next_month = 1 if now.month == 12 else now.month + 1
    next_5th = _next_weekday_5th(next_year, next_month)

    def _fmt_report_date(d: datetime) -> str:
        return f"{d.month}월 {d.day}일 ({_KO_WEEKDAY[d.weekday() + 1]})"

    current_month_key = now.strftime("%Y-%m")
    current_month_sent = False
    try:
        sent_result = (
            sb.table("naver_new_channel_monthly_report")
            .select("id")
            .eq("report_year_month", current_month_key)
            .limit(1)
            .execute()
        )
        current_month_sent = bool(sent_result.data)
    except Exception:
        pass

    report_dates = {
        "current": _fmt_report_date(current_5th),
        "current_sent": current_month_sent,
        "next": _fmt_report_date(next_5th),
        "next_sent": False,
    }

    leads_needed = leads_total
    try:
        works_result = sb.table("works").select("id", count="exact").eq("active_flag", "Active").execute()
        leads_needed = int(getattr(works_result, "count", 0) or 0)
    except Exception:
        pass

    return {
        "pending": [
            {
                "id": "work-application",
                "title": "작품 사용 신청 현황",
                "metric_label": "승인 대기",
                "count": work_pending,
                "href": "/admin/work-application",
                "status": f"전체 {work_total}건",
            },
            {
                "id": "rights-relief",
                "title": "소명 신청 권리사",
                "metric_label": "접수 건",
                "count": relief_total,
                "href": "/partner/relief",
                "status": "권리사 확인 필요",
            },
            {
                "id": "naver-youtube-report",
                "title": "네이버 클립 & 유튜브 통합 성과 보고",
                "metric_label": "활성 권리사",
                "count": len(rights_holders_list),
                "href": "/admin/reports/naver-clip",
                "status": f"정기 일정 {len(active_schedules)}개",
                "rights_holders": rights_holders_list,
            },
            {
                "id": "naver-revenue",
                "title": "네이버 클립 크리에이터 프로그램 등록 보고",
                "metric_label": "당월 보고일",
                "count": 0,
                "href": "/admin/naver-monthly",
                "status": None,
                "report_dates": report_dates,
            },
            {
                "id": "lead-summary",
                "title": "리드 발굴 요약",
                "metric_label": "리드 발굴 필요 영상",
                "count": leads_needed,
                "href": "/admin/lead-discovery",
                "status": "개 · 채널 확보 필요 작품 기준",
            },
        ]
    }


@router.post("/api/a2/manual-request-stub")
def a2_manual_request_stub(
    request: A2ManualRequestStub,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    channel_name, work_title = parse_manual_request(
        request.channel_name,
        request.work_title,
    )
    proposed_endpoint = "/work-approvals/request"
    return {
        "status": "stub_only",
        "channel_name": channel_name,
        "work_title": work_title,
        "manuals_api_base_url": "https://aajtilnicgqywpmuuxtr.supabase.co/functions/v1/manuals-api",
        "proposed_endpoint": proposed_endpoint,
        "proposed_url": f"https://aajtilnicgqywpmuuxtr.supabase.co/functions/v1/manuals-api{proposed_endpoint}",
        "next_step": "개발팀에서 실제 endpoint 및 채널 보유 작품 조회 명세 제공 후 연결",
    }


@router.get("/admin/b2", response_class=HTMLResponse)
def b2_admin_page() -> str:
    return """
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>B-2 네이버 클립 성과 어드민</title>
      <link rel="stylesheet" href="/admin-assets/b2/b2_admin.css" />
    </head>
    <body>
      <div id="app"></div>
      <script type="module" src="/admin-assets/b2/b2_admin.js"></script>
    </body>
    </html>
    """
