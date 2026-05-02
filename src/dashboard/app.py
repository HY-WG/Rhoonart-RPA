from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import settings
from src.core.repositories.supabase_b2_repository import SupabaseB2Repository
from src.services import B2AnalyticsFilters, B2AnalyticsService

from .models import ExecutionMode, IntegrationRun, IntegrationTaskSpec
from .runner import IntegrationTaskService, build_integration_task_service

STATIC_DIR = Path(__file__).with_name("static")


class RunTaskRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    approved: bool = False


class B2AnalyticsRequest(BaseModel):
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


def _run_to_dict(run: IntegrationRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "task_id": run.task_id,
        "title": run.title,
        "payload": run.payload,
        "status": run.status.value,
        "execution_mode": run.execution_mode.value,
        "requires_approval": run.requires_approval,
        "approved": run.approved,
        "started_at": run.started_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "result": run.result,
        "error": run.error,
        "logs": run.logs,
    }


_MOCK_CHANNEL_VIDEOS = [
    {
        "video_id": "video-crash-landing",
        "title": "사랑의 불시착",
        "description": "tvN 2019-2020 방영작. 작품사용신청 승인 테스트용 샘플 영상입니다.",
        "channel_name": "호영 채널",
        "contact_email": "hoyoungy2@gmail.com",
        "rights_holder_name": "스튜디오드래곤",
        "platform": "유튜브",
        "availability_status": "이용 가능",
        "thumbnail_emoji": "🎬",
    },
    {
        "video_id": "video-king-the-land",
        "title": "킹더랜드",
        "description": "JTBC 2023 방영작. 쿠폰 신청 테스트에 사용하는 샘플 영상입니다.",
        "channel_name": "호영 채널",
        "contact_email": "hoyoungy2@gmail.com",
        "rights_holder_name": "에이스토리",
        "platform": "네이버 클립",
        "availability_status": "이용 가능",
        "thumbnail_emoji": "🎟️",
    },
    {
        "video_id": "video-moving",
        "title": "무빙",
        "description": "Disney+ 2023 방영작. 저작권 소명 신청 연결 테스트용 샘플 영상입니다.",
        "channel_name": "호영 채널",
        "contact_email": "hoyoungy2@gmail.com",
        "rights_holder_name": "웨이브",
        "platform": "카카오 숏폼",
        "availability_status": "이용 가능",
        "thumbnail_emoji": "📝",
    },
]


def _task_to_dict(task: IntegrationTaskSpec) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "default_payload": task.default_payload,
        "targets": task.targets,
        "trigger_mode": task.trigger_mode,
        "requires_approval": task.requires_approval,
        "supports_dry_run": task.supports_dry_run,
        "real_run_warning": task.real_run_warning,
        "sheet_links": task.sheet_links,
        "tab_group": task.tab_group,
    }


def _render_dashboard_shell() -> str:
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Rhoonart 통합 테스트 대시보드</title>
  <link rel="stylesheet" href="./assets/dashboard.css" />
</head>
<body>
  <div id="app" class="app-shell">
    <noscript>이 페이지는 JavaScript가 필요합니다.</noscript>
  </div>
  <script type="module" src="./assets/dashboard.js"></script>
</body>
</html>
"""


def _build_b2_repository() -> SupabaseB2Repository:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not configured")
    return SupabaseB2Repository(
        supabase_url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )


def _build_b2_service() -> B2AnalyticsService:
    return B2AnalyticsService()


def build_app(service: IntegrationTaskService | None = None) -> FastAPI:
    app = FastAPI(title="Rhoonart 통합 테스트 대시보드", version="0.6.0")
    task_service = service or build_integration_task_service()

    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="dashboard-assets")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard_page() -> str:
        return _render_dashboard_shell()

    @app.get("/api/integration/tasks")
    def list_tasks() -> list[dict[str, Any]]:
        return [_task_to_dict(task) for task in task_service.list_task_specs()]

    @app.get("/api/integration/resources")
    def resource_summary() -> dict[str, Any]:
        return task_service.environment_summary()

    @app.get("/api/integration/runs")
    def list_runs() -> list[dict[str, Any]]:
        return [_run_to_dict(run) for run in task_service.list_runs()]

    @app.get("/api/integration/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = task_service.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return _run_to_dict(run)

    @app.get("/api/channels/me/videos")
    def list_channel_videos() -> list[dict[str, Any]]:
        return _MOCK_CHANNEL_VIDEOS

    @app.get("/api/b2/analytics/options")
    def get_b2_options() -> dict[str, Any]:
        repo = _build_b2_repository()
        service = _build_b2_service()
        rows = repo.list_all_clip_reports()
        return service.filter_options(rows)

    @app.get("/api/b2/analytics")
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
    ) -> dict[str, Any]:
        repo = _build_b2_repository()
        service = _build_b2_service()
        filters = B2AnalyticsFilters(
            checked_from=date.fromisoformat(checked_from) if checked_from else None,
            checked_to=date.fromisoformat(checked_to) if checked_to else None,
            uploaded_from=date.fromisoformat(uploaded_from) if uploaded_from else None,
            uploaded_to=date.fromisoformat(uploaded_to) if uploaded_to else None,
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

    @app.post("/api/b2/looker-studio/generate-send")
    def generate_b2_looker(request: B2AnalyticsRequest) -> dict[str, Any]:
        if not request.rights_holder_name:
            raise HTTPException(status_code=400, detail="rights_holder_name is required")
        repo = _build_b2_repository()
        service = _build_b2_service()
        filters = B2AnalyticsFilters(
            checked_from=date.fromisoformat(request.checked_from) if request.checked_from else None,
            checked_to=date.fromisoformat(request.checked_to) if request.checked_to else None,
            uploaded_from=date.fromisoformat(request.uploaded_from) if request.uploaded_from else None,
            uploaded_to=date.fromisoformat(request.uploaded_to) if request.uploaded_to else None,
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
        summary = service.summarize(filtered)
        grouped = service.group_rows(filtered, group_by=request.group_by)
        payload = {
            "run_id": f"looker-{request.rights_holder_name}-{summary['clip_count']}",
            "status": "stub_only",
            "rights_holder_name": request.rights_holder_name,
            "recipient_email": target.get("email") if target else None,
            "existing_looker_studio_url": target.get("looker_studio_url") if target else None,
            "report_title": f"{request.rights_holder_name} 네이버 클립 성과보고",
            "dataset_scope": {
                "checked_from": request.checked_from,
                "checked_to": request.checked_to,
                "uploaded_from": request.uploaded_from,
                "uploaded_to": request.uploaded_to,
                "platform": request.platform,
            },
            "summary": summary,
            "work_titles": sorted({row.get("work_title") for row in filtered if row.get("work_title")}),
            "channel_names": sorted({row.get("channel_name") for row in filtered if row.get("channel_name")})[:20],
            "top_groups": grouped[:10],
            "sample_rows": filtered[:10],
            "delivery": {
                "send_to": target.get("email") if target else None,
                "send_via": "email_stub",
                "subject": f"[자동화 초안] {request.rights_holder_name} 네이버 클립 성과 Looker Studio",
            },
            "next_step": "실제 Looker Studio 생성/공유/메일 발송 API 명세 수령 후 자동화 연결",
        }
        log_row = repo.create_looker_delivery_stub(payload)
        return {"stub": payload, "log_row": log_row}

    @app.post("/api/integration/tasks/{task_id}/run")
    def start_run(task_id: str, request: RunTaskRequest) -> dict[str, Any]:
        try:
            run = task_service.start_run(
                task_id,
                request.payload,
                execution_mode=request.execution_mode,
                approved=request.approved,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _run_to_dict(run)

    return app


app = build_app()
