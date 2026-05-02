from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.config import settings
from src.core.repositories.supabase_b2_repository import SupabaseNaverRepository
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


class CreatorActionRequest(BaseModel):
    channel_id: str | None = None
    video_id: str | None = None
    platform: str | None = None
    note: str = ""


class LeadDiscoveryRequest(BaseModel):
    video_id: str


class NewWorkRequest(BaseModel):
    title: str = Field(min_length=1)
    rights_holder_name: str = Field(min_length=1)
    registered_by: str = "admin"


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


_MOCK_MY_CHANNELS = [
    {"channel_id": "ch-youtube-luna", "name": "\ub8e8\ub098 \uc20f\ud3fc", "registered_at": "2026-03-22", "platform": "youtube", "status": "\uc2b9\uc778"},
    {"channel_id": "ch-kakao-original", "name": "\uce74\uce74\uc624 \uc624\ub9ac\uc9c0\ub110", "registered_at": "2026-04-02", "platform": "kakao", "status": "\uc2e0\uccad \uac00\ub2a5"},
    {"channel_id": "ch-naver-cliplab", "name": "\ub124\uc774\ubc84 \ud074\ub9bd\ub7a9", "registered_at": "2026-04-16", "platform": "naver", "status": "\uac80\ud1a0\uc911"},
]

_MOCK_CHANNEL_VIDEOS = [
    {
        "video_id": "video-crash-landing",
        "title": "\uc0ac\ub791\uc758 \ubd88\uc2dc\ucc29 \ud558\uc774\ub77c\uc774\ud2b8",
        "description": "tvN 2019-2020 \ubc29\uc601\uc791 \uc0ac\uc6a9 \uc2e0\uccad \ud14c\uc2a4\ud2b8\uc6a9 \uc0d8\ud50c \uc601\uc0c1\uc785\ub2c8\ub2e4.",
        "channel_name": "\ub8e8\ub098 \uc20f\ud3fc",
        "contact_email": "creator@example.com",
        "rights_holder_name": "\uc2a4\ud29c\ub514\uc624\ub4dc\ub798\uace4",
        "platform": "youtube",
        "availability_status": "\uc774\uc6a9 \uac00\ub2a5",
        "thumbnail_emoji": "S",
        "registered_at": "2026-04-12",
        "thumbnail_url": "https://images.unsplash.com/photo-1516280440614-37939bbacd81?auto=format&fit=crop&w=320&q=80",
        "active_channel_count": 8,
    },
    {
        "video_id": "video-king-the-land",
        "title": "\ud0b9\ub354\ub79c\ub4dc \uba85\uc7a5\uba74 \ubaa8\uc74c",
        "description": "JTBC 2023 \ubc29\uc601\uc791 \ucfe0\ud3f0 \uc2e0\uccad \ud14c\uc2a4\ud2b8\uc6a9 \uc0d8\ud50c \uc601\uc0c1\uc785\ub2c8\ub2e4.",
        "channel_name": "\ub124\uc774\ubc84 \ud074\ub9bd\ub7a9",
        "contact_email": "creator@example.com",
        "rights_holder_name": "\uc564\ud53c\uc624\uc5d4\ud130\ud14c\uc778\uba3c\ud2b8",
        "platform": "naver",
        "availability_status": "\uc774\uc6a9 \uac00\ub2a5",
        "thumbnail_emoji": "K",
        "registered_at": "2026-04-18",
        "thumbnail_url": "https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&w=320&q=80",
        "active_channel_count": 4,
    },
    {
        "video_id": "video-moving",
        "title": "\ubb34\ube59 \uce90\ub9ad\ud130 \ub9ac\ubdf0",
        "description": "Disney+ 2023 \ubc29\uc601\uc791 \uad8c\ub9ac \uc18c\uba85 \uc694\uccad \uc5f0\uacb0 \ud14c\uc2a4\ud2b8\uc6a9 \uc0d8\ud50c \uc601\uc0c1\uc785\ub2c8\ub2e4.",
        "channel_name": "\uce74\uce74\uc624 \uc624\ub9ac\uc9c0\ub110",
        "contact_email": "creator@example.com",
        "rights_holder_name": "\uc2a4\ud29c\ub514\uc624\uc564\ub274",
        "platform": "kakao",
        "availability_status": "\uac80\ud1a0 \ud544\uc694",
        "thumbnail_emoji": "M",
        "registered_at": "2026-04-25",
        "thumbnail_url": "https://images.unsplash.com/photo-1505686994434-e3cc5abf1330?auto=format&fit=crop&w=320&q=80",
        "active_channel_count": 11,
    },
]

_MOCK_ADMIN_CHANNELS = [
    {"channel_id": "adm-001", "name": "\ub4dc\ub77c\ub9c8 \ud074\ub9bd \uc5f0\uad6c\uc18c", "platform": "youtube", "owner": "\uae40\ubbfc\uc11c", "registered_at": "2026-01-08", "status": "\uc6b4\uc601\uc911", "video_count": 24},
    {"channel_id": "adm-002", "name": "\uc624\ub298\uc758 \uc20f\ud3fc", "platform": "naver", "owner": "\ubc15\uc900\ud638", "registered_at": "2026-02-14", "status": "\uac80\ud1a0\uc911", "video_count": 7},
    {"channel_id": "adm-003", "name": "\uce74\uce74\uc624 \ud53d", "platform": "kakao", "owner": "\uc774\uc9c0\uc544", "registered_at": "2026-03-03", "status": "\uc6b4\uc601\uc911", "video_count": 16},
    {"channel_id": "adm-004", "name": "\ubb34\ube44 \ud050\ub808\uc774\uc158", "platform": "youtube", "owner": "\ucd5c\ud604\uc6b0", "registered_at": "2026-03-19", "status": "\ubcf4\ub958", "video_count": 3},
    {"channel_id": "adm-005", "name": "\ud074\ub9bd \uc544\uce74\uc774\ube0c", "platform": "naver", "owner": "\uc815\ub2e4\uc740", "registered_at": "2026-04-09", "status": "\uc6b4\uc601\uc911", "video_count": 12},
]

_MOCK_DISCOVERED_LEADS = [
    {"lead_id": "lead-001", "channel_name": "\ub85c\ub9e8\uc2a4 \ud074\ub9bd\ubc15\uc2a4", "platform": "youtube", "subscriber_count": 18400, "contact_email": "romancebox@example.com", "fit_score": 92},
    {"lead_id": "lead-002", "channel_name": "\ub4dc\ub77c\ub9c8 \ud55c\uc785", "platform": "naver", "subscriber_count": 9700, "contact_email": "biteclip@example.com", "fit_score": 87},
    {"lead_id": "lead-003", "channel_name": "K\ucf58\ud150\uce20 \ub9ac\ubdf0\uc5b4", "platform": "kakao", "subscriber_count": 22100, "contact_email": "kcontent@example.com", "fit_score": 84},
]

_METABASE_RIGHTS_HOLDERS = [
    {"id": "wavve", "name": "\uc6e8\uc774\ube0c"},
    {"id": "contents-mining", "name": "\ucee8\ud150\uce20\ub9c8\uc774\ub2dd"},
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
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Rhoonart Integration Dashboard</title>
  <link rel=\"stylesheet\" href=\"./assets/dashboard.css\" />
</head>
<body>
  <div id=\"app\" class=\"app-shell\">
    <noscript>\uc774 \ud398\uc774\uc9c0\ub294 JavaScript\uac00 \ud544\uc694\ud569\ub2c8\ub2e4.</noscript>
  </div>
  <script type=\"module\" src=\"./assets/dashboard.js\"></script>
</body>
</html>
"""


def _build_naver_repository() -> SupabaseNaverRepository:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not configured")
    return SupabaseNaverRepository(
        supabase_url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )


_build_b2_repository = _build_naver_repository


def _build_b2_service() -> B2AnalyticsService:
    return B2AnalyticsService()


def _make_receipt(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": f"{action}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "status": "received",
        "action": action,
        "payload": payload,
        "message": "\uc694\uccad\uc774 \uc811\uc218\ub418\uc5c8\uc2b5\ub2c8\ub2e4.",
    }


def _append_query(url: str, key: str, value: str) -> str:
    if not url:
        return ""
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{key}={quote(value)}"


def build_app(service: IntegrationTaskService | None = None) -> FastAPI:
    app = FastAPI(title="Rhoonart Integration Dashboard", version="0.7.0")
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

    @app.post("/api/integration/tasks/{task_id}/run")
    def start_run(task_id: str, request: RunTaskRequest) -> dict[str, Any]:
        try:
            run = task_service.start_run(task_id, request.payload, execution_mode=request.execution_mode, approved=request.approved)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _run_to_dict(run)

    @app.get("/api/channels/me")
    def list_my_channels() -> dict[str, Any]:
        return {"items": _MOCK_MY_CHANNELS}

    @app.get("/api/channels/me/videos")
    def list_channel_videos() -> dict[str, Any]:
        return {"items": _MOCK_CHANNEL_VIDEOS}

    @app.post("/api/channels/me/creator-applications")
    def create_creator_application(request: CreatorActionRequest) -> dict[str, Any]:
        if request.platform not in {"kakao", "naver"}:
            raise HTTPException(status_code=400, detail="platform must be kakao or naver")
        if not request.channel_id:
            raise HTTPException(status_code=400, detail="channel_id is required")
        return _make_receipt("creator_application", request.model_dump())

    @app.post("/api/channels/me/videos/{video_id}/usage-requests")
    def create_video_usage_request(video_id: str, request: CreatorActionRequest) -> dict[str, Any]:
        if video_id not in {video["video_id"] for video in _MOCK_CHANNEL_VIDEOS}:
            raise HTTPException(status_code=404, detail="video not found")
        return _make_receipt("A-2", {**request.model_dump(), "video_id": video_id})

    @app.post("/api/channels/me/videos/{video_id}/relief-requests")
    def create_relief_request(video_id: str, request: CreatorActionRequest) -> dict[str, Any]:
        if video_id not in {video["video_id"] for video in _MOCK_CHANNEL_VIDEOS}:
            raise HTTPException(status_code=404, detail="video not found")
        return _make_receipt("D-2", {**request.model_dump(), "video_id": video_id})

    @app.get("/api/admin/overview")
    def admin_overview() -> dict[str, Any]:
        return {"pending": [
            {"id": "work-usage", "title": "\uc791\ud488 \uc0ac\uc6a9 \uc2e0\uccad", "metric_label": "\ud604\ud669", "count": 0},
            {"id": "rights-relief", "title": "\uad8c\ub9ac \uc18c\uba85 \uc2e0\uccad", "metric_label": "\ud604\ud669", "count": 2},
            {"id": "naver-report", "title": "\ub124\uc774\ubc84 \uc131\uacfc\ubcf4\uace0 \uc694\uccad", "metric_label": "\uc2e0\uaddc", "count": 1},
        ]}

    @app.get("/api/admin/channels")
    def admin_channels() -> dict[str, Any]:
        return {"items": _MOCK_ADMIN_CHANNELS}

    @app.get("/api/admin/videos")
    def admin_videos() -> dict[str, Any]:
        return {"items": _MOCK_CHANNEL_VIDEOS}

    @app.post("/api/admin/videos")
    def register_video(request: NewWorkRequest) -> dict[str, Any]:
        return _make_receipt("C-3", request.model_dump())

    @app.post("/api/admin/lead-discovery")
    def run_lead_discovery(request: LeadDiscoveryRequest) -> dict[str, Any]:
        video = next((item for item in _MOCK_CHANNEL_VIDEOS if item["video_id"] == request.video_id), None)
        if video is None:
            raise HTTPException(status_code=404, detail="video not found")
        if video["active_channel_count"] < 5:
            raise HTTPException(status_code=400, detail="lead discovery requires at least 5 active channels")
        return {"run_id": f"C-1-{request.video_id}", "status": "completed", "video": video, "leads": _MOCK_DISCOVERED_LEADS}

    @app.get("/api/admin/lead-discovery/{run_id}")
    def get_lead_discovery(run_id: str) -> dict[str, Any]:
        video = _MOCK_CHANNEL_VIDEOS[0]
        if run_id.startswith("C-1-video-moving"):
            video = _MOCK_CHANNEL_VIDEOS[2]
        return {"run_id": run_id, "status": "completed", "video": video, "leads": _MOCK_DISCOVERED_LEADS}

    @app.get("/api/admin/reports/metabase")
    def metabase_report() -> dict[str, Any]:
        url = settings.METABASE_NAVER_CLIP_URL
        configured = bool(url)
        return {
            "title": "\ub124\uc774\ubc84 \ud074\ub9bd \uc131\uacfc \ud655\uc778",
            "embed_url": url,
            "configured": configured,
            "env_key": "METABASE_NAVER_CLIP_URL",
            "reports": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "embed_url": _append_query(url, "rights_holder", item["name"]),
                    "configured": configured,
                }
                for item in _METABASE_RIGHTS_HOLDERS
            ],
        }

    @app.get("/api/naver/analytics/options")
    @app.get("/api/b2/analytics/options")
    def get_b2_options() -> dict[str, Any]:
        repo = _build_naver_repository()
        service = _build_b2_service()
        rows = repo.list_all_clip_reports()
        return service.filter_options(rows)

    @app.get("/api/naver/analytics")
    @app.get("/api/b2/analytics")
    def get_b2_analytics(checked_from: str | None = None, checked_to: str | None = None, uploaded_from: str | None = None, uploaded_to: str | None = None, channel_name: str | None = None, clip_title: str | None = None, work_title: str | None = None, rights_holder_name: str | None = None, platform: str | None = None, group_by: str = "clip", limit: int = 100) -> dict[str, Any]:
        repo = _build_naver_repository()
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
        rows = repo.list_clip_reports_filtered(checked_from=checked_from, checked_to=checked_to, uploaded_from=uploaded_from, uploaded_to=uploaded_to, channel_name=channel_name, clip_title=clip_title, work_title=work_title, rights_holder_name=rights_holder_name, platform=platform, limit=min(limit, 1000))
        filtered = service.filter_rows(rows, filters)
        return {"filters": {"checked_from": checked_from, "checked_to": checked_to, "uploaded_from": uploaded_from, "uploaded_to": uploaded_to, "channel_name": channel_name, "clip_title": clip_title, "work_title": work_title, "rights_holder_name": rights_holder_name, "platform": platform, "group_by": group_by, "limit": min(limit, 1000)}, "summary": service.summarize(filtered), "groups": service.group_rows(filtered, group_by=group_by), "rows": filtered}

    @app.post("/api/naver/looker-studio/generate-send")
    @app.post("/api/b2/looker-studio/generate-send")
    def generate_b2_looker(request: B2AnalyticsRequest) -> dict[str, Any]:
        if not request.rights_holder_name:
            raise HTTPException(status_code=400, detail="rights_holder_name is required")
        repo = _build_naver_repository()
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
        rows = repo.list_clip_reports_filtered(checked_from=request.checked_from, checked_to=request.checked_to, uploaded_from=request.uploaded_from, uploaded_to=request.uploaded_to, channel_name=request.channel_name, clip_title=request.clip_title, work_title=request.work_title, rights_holder_name=request.rights_holder_name, platform=request.platform, limit=1000)
        filtered = service.filter_rows(rows, filters)
        rights_holders = repo.list_rights_holders(enabled_only=False)
        target = next((row for row in rights_holders if row.get("rights_holder_name") == request.rights_holder_name), None)
        summary = service.summarize(filtered)
        grouped = service.group_rows(filtered, group_by=request.group_by)
        payload = {"run_id": f"looker-{request.rights_holder_name}-{summary['clip_count']}", "status": "stub_only", "rights_holder_name": request.rights_holder_name, "recipient_email": target.get("email") if target else None, "existing_looker_studio_url": target.get("looker_studio_url") if target else None, "report_title": f"{request.rights_holder_name} \ub124\uc774\ubc84 \ud074\ub9bd \uc131\uacfc \ubcf4\uace0", "summary": summary, "top_groups": grouped[:10], "sample_rows": filtered[:10]}
        log_row = repo.create_looker_delivery_stub(payload)
        return {"stub": payload, "log_row": log_row}

    return app


app = build_app()
