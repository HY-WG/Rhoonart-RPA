"""Shared pytest fixtures for the RPA Control Server API tests.

Design principles:
- No live API calls: Supabase, Google, Lambda, SMTP are all mocked.
- All external HTTP (TMDB, OMDb, etc.) patched via monkeypatch on requests.get.
- Auth is bypassed by overriding the check_auth FastAPI dependency.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path (handles direct pytest invocation)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Fixture data loaders ──────────────────────────────────────────────────────

def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture file from tests/fixtures/."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


# ── Supabase mock builder ─────────────────────────────────────────────────────

def make_supabase_mock(data: list[dict] | None = None, count: int | None = None) -> MagicMock:
    """Return a chainable Supabase client mock.

    All builder methods return ``self`` for fluent chaining.
    ``.execute()`` returns an object with ``.data`` and ``.count``.
    """
    sb = MagicMock()
    result = MagicMock()
    result.data = data if data is not None else []
    result.count = count if count is not None else (len(data) if data else 0)
    result.error = None

    for method_name in (
        "table", "select", "order", "range", "eq", "neq", "ilike",
        "in_", "limit", "single", "update", "insert", "upsert", "delete",
        "not_", "gte", "lte", "gt", "lt", "is_",
    ):
        getattr(sb, method_name).return_value = sb

    sb.execute.return_value = result
    return sb


def _make_result(data: Any) -> MagicMock:
    """Minimal Supabase execute() result."""
    r = MagicMock()
    r.data = data
    r.count = len(data) if isinstance(data, list) else 1
    r.error = None
    return r


# ── Repository & service mock builders ───────────────────────────────────────

def make_repo_mock(
    *,
    content_catalog: list | None = None,
    rights_holders: list | None = None,
    clip_reports: list | None = None,
    schedules: list | None = None,
    delivery_logs: list | None = None,
) -> MagicMock:
    """Return a mock SupabaseNaverRepository."""
    repo = MagicMock()
    repo.list_content_catalog.return_value = content_catalog or []
    repo.list_rights_holders.return_value = rights_holders or []
    repo.list_clip_reports.return_value = clip_reports or []
    repo.list_all_clip_reports.return_value = clip_reports or []
    repo.list_clip_reports_filtered.return_value = clip_reports or []
    repo.list_report_schedules.return_value = schedules or []
    repo.list_report_delivery_logs.return_value = delivery_logs or []
    repo.list_enabled_report_works.return_value = []
    repo.latest_daily_report_run.return_value = None
    repo.upsert_content_catalog_item.return_value = {"id": 1, "content_name": "새작품"}
    repo.update_work_report_enabled.return_value = {"id": 1, "naver_report_enabled": True}
    repo.create_looker_delivery_stub.return_value = {"id": 1}
    repo.mark_report_schedule_sent.return_value = None
    repo.update_report_schedule.return_value = {"schedule_id": 1, "enabled": True}
    repo.create_report_delivery_log.return_value = None
    return repo


def make_analytics_mock() -> MagicMock:
    svc = MagicMock()
    svc.filter_rows.return_value = []
    svc.filter_options.return_value = {"channel_names": [], "work_titles": []}
    svc.summarize.return_value = {"total_views": 0, "total_clips": 0}
    svc.group_rows.return_value = []
    return svc


# ── Patch targets ─────────────────────────────────────────────────────────────

_SUPABASE_PATCH_TARGETS = [
    "src.api.routes.admin_overview.get_supabase",
    "src.api.routes.portal.get_supabase",
    "src.api.routes.admin_work_requests.get_supabase",
    "src.api.routes.admin_works.get_supabase",
    "src.api.routes.admin_copyright.get_supabase",
    "src.api.routes.admin_leads.get_supabase",
    "src.api.routes.applications.get_supabase",
]

_REPO_PATCH_TARGETS = [
    "src.api.routes.admin_overview.build_naver_supabase_repository",
    "src.api.routes.admin_naver.build_naver_supabase_repository",
    "src.api.routes.admin_reports.build_naver_supabase_repository",
]

_ANALYTICS_PATCH_TARGETS = [
    "src.api.routes.admin_naver.build_b2_analytics_service",
]

_LAMBDA_PATCH_TARGETS = [
    "src.api.routes.admin_naver.invoke_lambda",
    "src.api.routes.applications.invoke_lambda",
]


# ── Core fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_supabase() -> MagicMock:
    return make_supabase_mock(data=[])


@pytest.fixture()
def mock_repo() -> MagicMock:
    return make_repo_mock()


@pytest.fixture()
def mock_analytics() -> MagicMock:
    return make_analytics_mock()


@pytest.fixture()
def mock_lambda() -> MagicMock:
    return MagicMock(return_value={"status": "ok", "message": "invoked"})


# ── TestClient with all dependencies mocked ───────────────────────────────────

@pytest.fixture()
def client(mock_supabase, mock_repo, mock_analytics, mock_lambda, monkeypatch):
    """
    TestClient with:
    - check_auth bypassed
    - get_supabase() mocked in all route modules
    - build_naver_supabase_repository() mocked
    - build_b2_analytics_service() mocked
    - invoke_lambda() mocked
    - External HTTP (TMDB, OMDb, etc.) returns empty/404
    - SMTP, Google APIs stubbed out
    """
    for target in _SUPABASE_PATCH_TARGETS:
        monkeypatch.setattr(target, lambda sb=mock_supabase: sb)

    for target in _REPO_PATCH_TARGETS:
        monkeypatch.setattr(target, lambda repo=mock_repo: repo)

    for target in _ANALYTICS_PATCH_TARGETS:
        monkeypatch.setattr(target, lambda svc=mock_analytics: svc)

    for target in _LAMBDA_PATCH_TARGETS:
        monkeypatch.setattr(target, mock_lambda)

    # Stub all outbound HTTP so no real network calls happen
    empty_http = MagicMock()
    empty_http.ok = False
    empty_http.status_code = 404
    empty_http.json.return_value = {}
    monkeypatch.setattr("requests.get", lambda *a, **kw: empty_http)
    monkeypatch.setattr("requests.post", lambda *a, **kw: empty_http)

    # Stub relief service (used by admin_overview)
    mock_relief = MagicMock()
    mock_relief.list_requests.return_value = []
    monkeypatch.setattr(
        "src.api.routes.admin_overview.get_relief_request_service",
        lambda: mock_relief,
    )

    from src.api.rpa_server import app
    from src.api.dependencies import check_auth

    app.dependency_overrides[check_auth] = lambda: None

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
