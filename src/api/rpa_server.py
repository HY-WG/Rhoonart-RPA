from __future__ import annotations

import importlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import gspread
import pytz
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.agents.approval.in_memory import InMemoryApprovalRepository
from src.agents.approval.queue import ApprovalQueue
from src.api.approval_router import build_approval_router
from src.api.deps import ALL_SCOPES, build_google_creds
from src.backoffice.app import build_app as build_relief_app
from src.backoffice.dependencies import get_relief_request_service
from src.config import settings
from src.core.repositories.sheet_repository import SheetNaverClipApplicantRepository
from src.core.repositories.supabase_b2_repository import SupabaseNaverRepository
from src.dashboard.app import build_app as build_dashboard_app
from src.dashboard.runner import build_integration_task_service
from src.handlers.a2_work_approval import parse_manual_request
from src.models import NaverClipApplicant, RepresentativeChannelPlatform
from src.services import B2AnalyticsFilters, B2AnalyticsService
from src.services.b2_test_report_service import B2TestReportService

KST = pytz.timezone("Asia/Seoul")
ADMIN_B2_STATIC_DIR = Path(__file__).resolve().parents[1] / "admin_b2" / "static"


class GenericTriggerRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class A3ApplicantCreateRequest(BaseModel):
    name: str
    phone_number: str
    naver_id: str
    naver_clip_profile_name: str
    naver_clip_profile_id: str
    representative_channel_name: str
    representative_channel_platform: RepresentativeChannelPlatform
    channel_url: str


class A3ApplicantResponse(BaseModel):
    applicant_id: str
    name: str
    phone_number: str
    naver_id: str
    naver_clip_profile_name: str
    naver_clip_profile_id: str
    representative_channel_name: str
    representative_channel_platform: RepresentativeChannelPlatform
    channel_url: str
    submitted_at: datetime


class A2ManualRequestStub(BaseModel):
    channel_name: str
    work_title: str


class B2AdminRunRequest(BaseModel):
    send_notifications: bool = False
    source: str = "admin_page"


class B2SupabaseCollectRequest(BaseModel):
    triggered_by: str = Field(default="manual", pattern="^(manual|schedule|api)$")
    max_clips_per_identifier: int = Field(default=2000, ge=1, le=5000)


class B2AnalyticsQuery(BaseModel):
    checked_from: str | None = None
    checked_to: str | None = None
    uploaded_from: str | None = None
    uploaded_to: str | None = None
    channel_name: str | None = None
    clip_title: str | None = None
    work_title: str | None = None
    rights_holder_name: str | None = None
    platform: str | None = None
    group_by: str = "clip"
    limit: int = 100


TASK_HANDLERS: dict[str, str] = {
    "A-2": "lambda.a2_work_approval_handler",
    "A-3": "lambda.a3_naver_clip_monthly_handler",
    "B-2": "lambda.b2_weekly_report_handler",
    "C-1": "lambda.c1_lead_filter_handler",
    "C-2": "lambda.c2_cold_email_handler",
    "C-3": "lambda.c3_work_register_handler",
    "C-4": "lambda.c4_coupon_notification_handler",
    "D-3": "lambda.d3_kakao_creator_onboarding_handler",
}


def _check_auth(x_rpa_token: str | None = Header(default=None)) -> None:
    if not settings.X_INTERN_TOKEN:
        return
    if x_rpa_token != settings.X_INTERN_TOKEN:
        raise HTTPException(status_code=401, detail="invalid X-RPA-Token")


def _invoke_lambda(module_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    module = importlib.import_module(module_name)
    return module.handler(payload, None)


def build_naver_clip_repository() -> SheetNaverClipApplicantRepository:
    if not settings.NAVER_APPLICANT_SHEET_ID:
        raise RuntimeError("NAVER_APPLICANT_SHEET_ID is not configured")
    creds = build_google_creds(settings.GOOGLE_CREDENTIALS_FILE, ALL_SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(settings.NAVER_APPLICANT_SHEET_ID)
    worksheet = sheet.worksheet(settings.NAVER_APPLICANT_TAB)
    return SheetNaverClipApplicantRepository(worksheet)


def build_naver_supabase_repository() -> SupabaseNaverRepository:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not configured")
    return SupabaseNaverRepository(
        supabase_url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )


build_b2_supabase_repository = build_naver_supabase_repository


def build_b2_analytics_service() -> B2AnalyticsService:
    return B2AnalyticsService()


def _applicant_to_response(applicant: NaverClipApplicant) -> A3ApplicantResponse:
    return A3ApplicantResponse(
        applicant_id=applicant.applicant_id,
        name=applicant.name,
        phone_number=applicant.phone_number,
        naver_id=applicant.naver_id,
        naver_clip_profile_name=applicant.naver_clip_profile_name,
        naver_clip_profile_id=applicant.naver_clip_profile_id,
        representative_channel_name=applicant.representative_channel_name,
        representative_channel_platform=applicant.representative_channel_platform,
        channel_url=applicant.channel_url,
        submitted_at=applicant.submitted_at,
    )


def build_app() -> FastAPI:
    app = FastAPI(
        title="Rhoonart RPA Control Server",
        version="0.2.0",
        description=(
            "Unified local control server for legacy trigger endpoints, "
            "integration dashboard, and the D-2 relief-request backoffice."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    dashboard_service = build_integration_task_service()
    dashboard_app = build_dashboard_app(service=dashboard_service)
    relief_app = build_relief_app(service=get_relief_request_service())

    # Approval Queue (InMemory — Supabase 전환 시 SupabaseApprovalRepository로 교체)
    _approval_repo = InMemoryApprovalRepository()
    _notifier = type("_Stub", (), {"send": lambda self, **kw: None})()
    _approval_queue = ApprovalQueue(repo=_approval_repo, notifier=_notifier)
    approval_router = build_approval_router(_approval_queue)
    app.include_router(approval_router)

    app.mount("/dashboard", dashboard_app)
    app.mount("/relief", relief_app)
    if ADMIN_B2_STATIC_DIR.exists():
        app.mount(
            "/admin-assets/b2",
            StaticFiles(directory=ADMIN_B2_STATIC_DIR),
            name="b2-admin-assets",
        )

    @app.get("/", response_class=HTMLResponse)
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

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "time": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "dashboard_repository": settings.INTEGRATION_DASHBOARD_DB_TYPE,
            "auth_required": bool(settings.X_INTERN_TOKEN),
        }

    @app.post("/api/a2/manual-request-stub")
    def a2_manual_request_stub(
        request: A2ManualRequestStub,
        _: None = Depends(_check_auth),
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

    @app.get("/admin/b2", response_class=HTMLResponse)
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

    @app.get("/api/admin/naver/content-catalog")
    @app.get("/api/admin/b2/content-catalog")
    def list_b2_content_catalog(_: None = Depends(_check_auth)) -> list[dict[str, Any]]:
        repo = build_naver_supabase_repository()
        return repo.list_content_catalog()

    @app.get("/api/admin/naver/rights-holders")
    @app.get("/api/admin/b2/rights-holders")
    def list_b2_rights_holders(
        enabled_only: bool = True,
        _: None = Depends(_check_auth),
    ) -> list[dict[str, Any]]:
        repo = build_naver_supabase_repository()
        return repo.list_rights_holders(enabled_only=enabled_only)

    @app.get("/api/admin/naver/clip-reports")
    @app.get("/api/admin/b2/clip-reports")
    def list_b2_clip_reports(
        limit: int = 100,
        work_title: str | None = None,
        _: None = Depends(_check_auth),
    ) -> list[dict[str, Any]]:
        repo = build_naver_supabase_repository()
        return repo.list_clip_reports(limit=limit, work_title=work_title)

    @app.get("/api/admin/naver/analytics/options")
    @app.get("/api/admin/b2/analytics/options")
    def get_b2_analytics_options(_: None = Depends(_check_auth)) -> dict[str, Any]:
        repo = build_naver_supabase_repository()
        service = build_b2_analytics_service()
        rows = repo.list_all_clip_reports()
        return service.filter_options(rows)

    @app.get("/api/admin/naver/analytics")
    @app.get("/api/admin/b2/analytics")
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
        _: None = Depends(_check_auth),
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

    @app.post("/api/admin/naver/looker-studio/generate-send")
    @app.post("/api/admin/b2/looker-studio/generate-send")
    def create_b2_looker_delivery_stub(
        request: B2AnalyticsQuery,
        _: None = Depends(_check_auth),
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

    @app.post("/api/admin/naver/run-report-stub")
    @app.post("/api/admin/b2/run-report-stub")
    def run_b2_report_stub(
        request: B2AdminRunRequest,
        _: None = Depends(_check_auth),
    ) -> dict[str, Any]:
        return _invoke_lambda(
            "lambda.b2_weekly_report_handler",
            {"source": request.source, "send_notifications": request.send_notifications},
        )

    @app.post("/api/admin/naver/supabase/collect")
    @app.post("/api/admin/b2/supabase/collect")
    def collect_b2_supabase_reports(
        request: B2SupabaseCollectRequest,
        _: None = Depends(_check_auth),
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

    @app.get("/a3/apply", response_class=HTMLResponse)
    def a3_apply_page() -> str:
        platform_options = "".join(
            f'<option value="{option.value}">{option.value}</option>'
            for option in RepresentativeChannelPlatform
        )
        return f"""
        <!doctype html>
        <html lang="ko">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>A-3 지원 신청</title>
          <style>
            body {{ font-family: "Segoe UI", "Apple SD Gothic Neo", sans-serif; background: #f6f1ea; margin: 0; color: #18222d; }}
            .shell {{ max-width: 920px; margin: 0 auto; padding: 32px 20px 48px; }}
            .card {{ background: #fffdf8; border: 1px solid #ddcfbc; border-radius: 24px; padding: 28px; box-shadow: 0 16px 40px rgba(24,34,45,.08); }}
            h1 {{ margin-top: 0; font-size: 32px; }}
            p {{ color: #64717d; line-height: 1.6; }}
            .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            label {{ display: grid; gap: 8px; font-weight: 600; }}
            label.full {{ grid-column: 1 / -1; }}
            input, select {{ border: 1px solid #d7c8b5; border-radius: 14px; padding: 12px 14px; font: inherit; background: white; }}
            button {{ border: 0; border-radius: 999px; background: #1b6b73; color: white; padding: 14px 20px; font-weight: 700; cursor: pointer; }}
            pre {{ background: #17212b; color: #dce8f3; padding: 16px; border-radius: 16px; overflow: auto; min-height: 120px; }}
            @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} }}
          </style>
        </head>
        <body>
          <div class="shell">
            <div class="card">
              <h1>A-3 지원 신청</h1>
              <p>홈페이지에서 받은 신청은 A-3 월간 집계와 메일 발송 대상으로 저장됩니다.</p>
              <form id="a3-form" class="grid">
                <label><span>이름</span><input name="name" required /></label>
                <label><span>전화번호</span><input name="phone_number" required /></label>
                <label><span>네이버 ID</span><input name="naver_id" required /></label>
                <label><span>네이버 클립 프로필명</span><input name="naver_clip_profile_name" required /></label>
                <label><span>네이버 클립 프로필 ID</span><input name="naver_clip_profile_id" required /></label>
                <label><span>대표 채널명</span><input name="representative_channel_name" required /></label>
                <label><span>대표 채널의 활동 플랫폼</span><select name="representative_channel_platform" required>{platform_options}</select></label>
                <label class="full"><span>채널 URL</span><input name="channel_url" type="url" required /></label>
                <div class="full"><button type="submit">신청 저장</button></div>
              </form>
              <pre id="result">아직 제출되지 않았습니다.</pre>
            </div>
          </div>
          <script>
            const form = document.getElementById('a3-form');
            const result = document.getElementById('result');
            form.addEventListener('submit', async (event) => {{
              event.preventDefault();
              const payload = Object.fromEntries(new FormData(form).entries());
              const response = await fetch('/api/a3/applicants', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload),
              }});
              const data = await response.json();
              result.textContent = JSON.stringify(data, null, 2);
            }});
          </script>
        </body>
        </html>
        """

    @app.get("/api/a3/applicants", response_model=list[A3ApplicantResponse])
    def list_a3_applicants(_: None = Depends(_check_auth)) -> list[A3ApplicantResponse]:
        repo = build_naver_clip_repository()
        return [_applicant_to_response(applicant) for applicant in repo.list_applicants()]

    @app.post("/api/a3/applicants", response_model=A3ApplicantResponse)
    def create_a3_applicant(payload: A3ApplicantCreateRequest) -> A3ApplicantResponse:
        repo = build_naver_clip_repository()
        applicant = NaverClipApplicant.create(
            name=payload.name,
            phone_number=payload.phone_number,
            naver_id=payload.naver_id,
            naver_clip_profile_name=payload.naver_clip_profile_name,
            naver_clip_profile_id=payload.naver_clip_profile_id,
            representative_channel_name=payload.representative_channel_name,
            representative_channel_platform=payload.representative_channel_platform,
            channel_url=payload.channel_url,
        )
        saved = repo.create_applicant(applicant)
        return _applicant_to_response(saved)

    @app.post("/api/tasks/{task_id}/trigger")
    def trigger_task(
        task_id: str,
        request: GenericTriggerRequest,
        _: None = Depends(_check_auth),
    ) -> dict[str, Any]:
        module_name = TASK_HANDLERS.get(task_id.upper())
        if not module_name:
            raise HTTPException(status_code=404, detail=f"unknown task: {task_id}")
        return _invoke_lambda(module_name, request.payload)

    @app.post("/api/a2/trigger")
    def trigger_a2(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        payload = dict(request.payload)
        event = {
            "body": json.dumps(
                {
                    "type": "event_callback",
                    "event": {
                        "type": "message",
                        "channel": payload.get("slack_channel_id", "C_HTTP_TRIGGER"),
                        "ts": payload.get("slack_message_ts", "manual-0001"),
                        "text": (
                            f'\ucc44\ub110: "{payload.get("channel_name", "Test Channel")}" '
                            f'\uc2e0\uaddc \uc601\uc0c1 \uc0ac\uc6a9 \uc694\uccad\uc774 \uc788\uc2b5\ub2c8\ub2e4.\n'
                            f'{payload.get("work_title", "Test Work")}'
                        ),
                    },
                },
                ensure_ascii=False,
            )
        }
        return _invoke_lambda("lambda.a2_work_approval_handler", event)

    @app.post("/api/a3/trigger")
    def trigger_a3(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.a3_naver_clip_monthly_handler", request.payload)

    @app.post("/api/b2/trigger")
    def trigger_b2(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.b2_weekly_report_handler", request.payload)

    @app.post("/api/c1/trigger")
    def trigger_c1(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.c1_lead_filter_handler", request.payload)

    @app.post("/api/c2/trigger")
    def trigger_c2(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.c2_cold_email_handler", request.payload)

    @app.post("/api/c3/trigger")
    def trigger_c3(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.c3_work_register_handler", request.payload)

    @app.post("/api/c4/trigger")
    def trigger_c4(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.c4_coupon_notification_handler", request.payload)

    @app.post("/api/d3/trigger")
    def trigger_d3(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.d3_kakao_creator_onboarding_handler", request.payload)

    return app


app = build_app()


if __name__ == "__main__":
    uvicorn.run("src.api.rpa_server:app", host="127.0.0.1", port=8000, reload=False)
