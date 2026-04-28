from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .models import ExecutionMode, IntegrationRun, IntegrationTaskSpec
from .runner import IntegrationTaskService, build_integration_task_service

STATIC_DIR = Path(__file__).with_name("static")


class RunTaskRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    approved: bool = False


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
        "description": "tvN 2019–2020 방영작. 작품사용신청 승인 테스트용 샘플 영상입니다.",
        "channel_name": "호영 채널",
        "contact_email": "hoyoungy2@gmail.com",
        "rights_holder_name": "스튜디오드래곤",
        "platform": "유튜브",
        "availability_status": "이용 가능",
        "thumbnail_emoji": "🎭",
    },
    {
        "video_id": "video-king-the-land",
        "title": "킹더랜드",
        "description": "JTBC 2023 방영작. 쿠폰 신청 테스트에 사용하는 샘플 영상입니다.",
        "channel_name": "호영 채널",
        "contact_email": "hoyoungy2@gmail.com",
        "rights_holder_name": "판씨네마",
        "platform": "네이버 클립",
        "availability_status": "이용 가능",
        "thumbnail_emoji": "👑",
    },
    {
        "video_id": "video-moving",
        "title": "무빙",
        "description": "Disney+ 2023 방영작. 저작권 소명 신청 연결 테스트용 샘플 영상입니다.",
        "channel_name": "호영 채널",
        "contact_email": "hoyoungy2@gmail.com",
        "rights_holder_name": "웨이브",
        "platform": "카카오숏폼",
        "availability_status": "이용 가능",
        "thumbnail_emoji": "🦸",
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


def build_app(service: IntegrationTaskService | None = None) -> FastAPI:
    app = FastAPI(title="Rhoonart 통합 테스트 대시보드", version="0.5.0")
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
        """내 채널 이용 가능 영상 목록 (mock)."""
        return _MOCK_CHANNEL_VIDEOS

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
