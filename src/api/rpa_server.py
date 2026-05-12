"""Rhoonart RPA Control Server — lean orchestrator.

All route logic lives in src/api/routes/*.py.
This module wires the FastAPI application together:
  - CORS middleware
  - sub-app mounts (dashboard, relief backoffice, admin-assets)
  - approval queue
  - Naver report background scheduler
  - include_router for every domain router
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytz
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.agents.approval.in_memory import InMemoryApprovalRepository
from src.agents.approval.queue import ApprovalQueue
from src.api.approval_router import build_approval_router
from src.api.dependencies import (
    NAVER_REPORT_SCHEDULER_LOCK,
    NAVER_REPORT_SCHEDULER_STOP,
)
from src.api.routes.admin_copyright import router as copyright_router
from src.api.routes.admin_leads import router as leads_router
from src.api.routes.admin_naver import router as naver_router
from src.api.routes.admin_overview import router as overview_router
from src.api.routes.admin_reports import router as reports_router
from src.api.routes.admin_work_requests import router as work_requests_router
from src.api.routes.admin_works import router as works_router
from src.api.routes.applications import router as applications_router
from src.api.routes.portal import router as portal_router
from src.backoffice.app import build_app as build_relief_app
from src.backoffice.dependencies import get_relief_request_service
from src.dashboard.app import build_app as build_dashboard_app
from src.dashboard.runner import build_integration_task_service

KST = pytz.timezone("Asia/Seoul")
logger = logging.getLogger(__name__)

ADMIN_B2_STATIC_DIR = Path(__file__).resolve().parents[1] / "admin_b2" / "static"

# Scheduler thread reference (module-level so the thread outlives build_app)
_scheduler_thread: threading.Thread | None = None


def _start_naver_report_scheduler() -> None:
    """Launch the background thread that fires due Naver report schedules."""
    global _scheduler_thread
    enabled = os.environ.get("NAVER_REPORT_SCHEDULER_ENABLED", "true").lower() not in {"0", "false", "no"}
    if not enabled:
        logger.info("naver report scheduler disabled by NAVER_REPORT_SCHEDULER_ENABLED")
        return
    with NAVER_REPORT_SCHEDULER_LOCK:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        try:
            interval = max(30, int(os.environ.get("NAVER_REPORT_SCHEDULER_INTERVAL_SECONDS", "60")))
        except ValueError:
            interval = 60

        def _worker() -> None:
            # Import lazily to avoid circular imports at module load time
            from src.api.routes.admin_reports import run_due_naver_report_schedules_once  # noqa: PLC0415
            logger.info("naver report scheduler started interval_seconds=%s timezone=Asia/Seoul", interval)
            while not NAVER_REPORT_SCHEDULER_STOP.wait(interval):
                try:
                    result = run_due_naver_report_schedules_once(execution_mode="scheduler")
                    if result["due_count"]:
                        logger.info("naver report scheduler sent due reports: %s", result)
                except Exception as exc:
                    logger.exception("naver report scheduler tick failed: %s", exc)

        NAVER_REPORT_SCHEDULER_STOP.clear()
        _scheduler_thread = threading.Thread(
            target=_worker,
            name="naver-report-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()


def build_app() -> FastAPI:
    app = FastAPI(
        title="Rhoonart RPA Control Server",
        version="0.3.0",
        description=(
            "Unified local control server for legacy trigger endpoints, "
            "integration dashboard, and the D-2 relief-request backoffice."
        ),
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Sub-applications ──────────────────────────────────────────────────────
    dashboard_app = build_dashboard_app(service=build_integration_task_service())
    relief_app = build_relief_app(service=get_relief_request_service())
    app.mount("/dashboard", dashboard_app)
    app.mount("/relief", relief_app)
    if ADMIN_B2_STATIC_DIR.exists():
        app.mount(
            "/admin-assets/b2",
            StaticFiles(directory=ADMIN_B2_STATIC_DIR),
            name="b2-admin-assets",
        )

    # ── Approval queue (InMemory — swap to SupabaseApprovalRepository when ready) ─
    _approval_repo = InMemoryApprovalRepository()
    _notifier = type("_Stub", (), {"send": lambda self, **kw: None})()
    _approval_queue = ApprovalQueue(repo=_approval_repo, notifier=_notifier)
    app.include_router(build_approval_router(_approval_queue))

    # ── Domain routers ────────────────────────────────────────────────────────
    app.include_router(overview_router)
    app.include_router(portal_router)
    app.include_router(applications_router)
    app.include_router(reports_router)
    app.include_router(naver_router)
    app.include_router(work_requests_router)
    app.include_router(works_router)
    app.include_router(copyright_router)
    app.include_router(leads_router)

    # ── Background scheduler ──────────────────────────────────────────────────
    @app.on_event("startup")
    def _startup_naver_report_scheduler() -> None:
        _start_naver_report_scheduler()

    return app


app = build_app()


if __name__ == "__main__":
    uvicorn.run("src.api.rpa_server:app", host="127.0.0.1", port=8000, reload=False)
