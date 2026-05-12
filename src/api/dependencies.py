"""Shared dependencies and factory functions for RPA Control Server routes.

This module centralises all dependency injection helpers that were previously
scattered inside the ``build_app()`` closure in ``rpa_server.py``.
"""
from __future__ import annotations

import importlib
import logging
import threading
from datetime import datetime
from typing import Any

import gspread
import pytz
from fastapi import Header, HTTPException

from src.core.clients.google_auth_client import ALL_SCOPES, build_google_creds
from src.config import settings
from src.core.repositories.sheet_repository import SheetNaverClipApplicantRepository
from src.core.repositories.supabase_naver_repository import SupabaseNaverRepository
from src.services import B2AnalyticsService

KST = pytz.timezone("Asia/Seoul")
logger = logging.getLogger(__name__)

# ── Module-level shared state ────────────────────────────────────────────────
NAVER_COLLECT_JOBS: dict[str, dict[str, Any]] = {}
NAVER_COLLECT_JOBS_LOCK = threading.Lock()

NAVER_REPORT_SCHEDULES_CACHE: dict[str, Any] = {}
NAVER_REPORT_SCHEDULES_CACHE_LOCK = threading.Lock()
NAVER_REPORT_SCHEDULES_CACHE_TTL_SECONDS = 60

NAVER_REPORT_SCHEDULER_THREAD: threading.Thread | None = None
NAVER_REPORT_SCHEDULER_STOP = threading.Event()
NAVER_REPORT_SCHEDULER_LOCK = threading.Lock()

LEAD_SUBSCRIBER_METRICS: dict[str, dict[str, Any]] = {}
LEAD_SUBSCRIBER_METRICS_LOCK = threading.Lock()

WORK_SEARCH_EXTERNAL_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
WORK_SEARCH_EXTERNAL_CACHE_TTL_SECONDS = 60 * 60 * 24

# Task dispatch is handled entirely by src.tasks.registry.TASK_REGISTRY.
# TASK_HANDLERS (the old string-keyed dict) has been removed.


# ── Auth dependency ──────────────────────────────────────────────────────────
def check_auth(x_rpa_token: str | None = Header(default=None)) -> None:
    """FastAPI dependency: validates X-RPA-Token header."""
    if not settings.X_INTERN_TOKEN:
        return
    if x_rpa_token != settings.X_INTERN_TOKEN:
        raise HTTPException(status_code=401, detail="invalid X-RPA-Token")


# ── Supabase client ──────────────────────────────────────────────────────────
def get_supabase():
    """Return a Supabase service-role client. Imported lazily to avoid startup cost."""
    from supabase import create_client  # type: ignore
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


# ── Lambda invocation ────────────────────────────────────────────────────────
def invoke_lambda(module_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dynamically import a lambda handler module and invoke its handler function."""
    module = importlib.import_module(module_name)
    return module.handler(payload, None)


# ── Naver collect job helpers ────────────────────────────────────────────────
def set_naver_collect_job(job_id: str, **updates: Any) -> dict[str, Any]:
    with NAVER_COLLECT_JOBS_LOCK:
        current = NAVER_COLLECT_JOBS.get(job_id, {})
        next_job = {
            **current,
            **updates,
            "job_id": job_id,
            "updated_at": datetime.now(KST).isoformat(),
        }
        NAVER_COLLECT_JOBS[job_id] = next_job
        return dict(next_job)


def get_naver_collect_job(job_id: str) -> dict[str, Any] | None:
    with NAVER_COLLECT_JOBS_LOCK:
        job = NAVER_COLLECT_JOBS.get(job_id)
        return dict(job) if job else None


# ── Repository / service factories ──────────────────────────────────────────
def build_naver_clip_repository() -> SheetNaverClipApplicantRepository:
    spreadsheet_id = (
        settings.NAVER_INBOUND_REPORT_SHEET_ID
        or settings.NAVER_APPLICANT_SHEET_ID
        or settings.NAVER_FORM_ID
    )
    if not spreadsheet_id:
        raise RuntimeError(
            "NAVER_INBOUND_REPORT_SHEET_ID or NAVER_APPLICANT_SHEET_ID is not configured"
        )
    creds = build_google_creds(settings.GOOGLE_CREDENTIALS_FILE, ALL_SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id)
    preferred_tabs = ["Sheet1", settings.NAVER_APPLICANT_TAB]
    try:
        worksheet = next(sheet.worksheet(tab) for tab in preferred_tabs if tab)
    except Exception:
        worksheet = sheet.add_worksheet(title="Sheet1", rows=1000, cols=10)
    return SheetNaverClipApplicantRepository(worksheet, spreadsheet=sheet)


def build_naver_supabase_repository() -> SupabaseNaverRepository:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is not configured"
        )
    return SupabaseNaverRepository(
        supabase_url=settings.SUPABASE_URL,
        service_role_key=settings.SUPABASE_SERVICE_ROLE_KEY,
    )


def build_b2_analytics_service() -> B2AnalyticsService:
    return B2AnalyticsService()
