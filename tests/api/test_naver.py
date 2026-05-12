"""Tests for admin Naver/B2 routes (content-catalog, analytics, collect-jobs)."""
from __future__ import annotations

import pytest

from tests.conftest import load_fixture, _make_result

CLIP_REPORT = load_fixture("naver_clip_report")
RIGHTS_HOLDER = load_fixture("rights_holder")


# ── Content catalog ───────────────────────────────────────────────────────────

class TestContentCatalog:
    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_list_returns_list(self, client, mock_repo, prefix):
        mock_repo.list_content_catalog.return_value = [{"id": 1, "content_name": "작품A"}]
        resp = client.get(f"{prefix}/content-catalog")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_list_empty(self, client, mock_repo, prefix):
        mock_repo.list_content_catalog.return_value = []
        resp = client.get(f"{prefix}/content-catalog")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_create_catalog_item(self, client, mock_repo, prefix):
        mock_repo.upsert_content_catalog_item.return_value = {"id": 1, "content_name": "새작품"}
        payload = {
            "content_name": "새작품",
            "identifier": "new-work-001",
            "rights_holder_name": "테스트권리사",
            "status": "Active",
            "naver_report_enabled": True,
        }
        resp = client.post(f"{prefix}/content-catalog", json=payload)
        assert resp.status_code == 200
        assert resp.json()["content_name"] == "새작품"

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_create_missing_fields(self, client, prefix):
        resp = client.post(f"{prefix}/content-catalog", json={})
        assert resp.status_code == 422


class TestReportEnabled:
    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_update_report_enabled(self, client, mock_repo, prefix):
        mock_repo.update_work_report_enabled.return_value = {"id": 1, "naver_report_enabled": False}
        resp = client.patch(
            f"{prefix}/content-catalog/1/report-enabled",
            json={"naver_report_enabled": False},
        )
        assert resp.status_code == 200


# ── Rights holders ────────────────────────────────────────────────────────────

class TestRightsHolders:
    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_list_rights_holders(self, client, mock_repo, prefix):
        mock_repo.list_rights_holders.return_value = [RIGHTS_HOLDER]
        resp = client.get(f"{prefix}/rights-holders")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert resp.json()[0]["rights_holder_name"] == "테스트권리사"


# ── Clip reports ──────────────────────────────────────────────────────────────

class TestClipReports:
    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_list_clip_reports(self, client, mock_repo, prefix):
        mock_repo.list_clip_reports.return_value = [CLIP_REPORT]
        resp = client.get(f"{prefix}/clip-reports")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["work_title"] == "테스트작품"

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_list_with_title_filter(self, client, mock_repo, prefix):
        mock_repo.list_clip_reports.return_value = [CLIP_REPORT]
        resp = client.get(f"{prefix}/clip-reports?work_title=테스트")
        assert resp.status_code == 200


# ── Analytics ────────────────────────────────────────────────────────────────

class TestAnalytics:
    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_options(self, client, mock_repo, mock_analytics, prefix):
        mock_repo.list_all_clip_reports.return_value = []
        mock_analytics.filter_options.return_value = {"channel_names": ["채널A"]}
        resp = client.get(f"{prefix}/analytics/options")
        assert resp.status_code == 200
        assert "channel_names" in resp.json()

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_analytics_default(self, client, mock_repo, mock_analytics, prefix):
        mock_repo.list_clip_reports_filtered.return_value = []
        mock_analytics.filter_rows.return_value = []
        mock_analytics.summarize.return_value = {"total_views": 0}
        mock_analytics.group_rows.return_value = []
        resp = client.get(f"{prefix}/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "rows" in data

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_analytics_with_filters(self, client, mock_repo, mock_analytics, prefix):
        mock_repo.list_clip_reports_filtered.return_value = []
        mock_analytics.filter_rows.return_value = []
        resp = client.get(f"{prefix}/analytics?channel_name=테스트&group_by=work")
        assert resp.status_code == 200


# ── Looker Studio stub ────────────────────────────────────────────────────────

class TestLookerStudio:
    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_generate_stub_missing_rights_holder(self, client, prefix):
        resp = client.post(f"{prefix}/looker-studio/generate-send", json={})
        assert resp.status_code == 400

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_generate_stub_with_rights_holder(self, client, mock_repo, mock_analytics, prefix):
        mock_repo.list_rights_holders.return_value = [RIGHTS_HOLDER]
        mock_repo.list_clip_reports_filtered.return_value = []
        mock_analytics.filter_rows.return_value = []
        mock_analytics.summarize.return_value = {"total_views": 0}
        mock_analytics.group_rows.return_value = []
        resp = client.post(
            f"{prefix}/looker-studio/generate-send",
            json={"rights_holder_name": "테스트권리사"},
        )
        assert resp.status_code == 200
        assert "stub" in resp.json()


# ── Run report stub ───────────────────────────────────────────────────────────

class TestRunReportStub:
    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_invoke_lambda(self, client, mock_lambda, prefix):
        resp = client.post(f"{prefix}/run-report-stub", json={})
        assert resp.status_code == 200
        assert mock_lambda.called


# ── Collect jobs (async) ──────────────────────────────────────────────────────

class TestCollectJobs:
    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_latest_job_empty(self, client, mock_repo, prefix):
        mock_repo.latest_daily_report_run.return_value = None
        resp = client.get(f"{prefix}/supabase/collect-jobs/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "empty"

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_latest_job_with_data(self, client, mock_repo, prefix):
        mock_repo.latest_daily_report_run.return_value = {
            "run_id": "run-001",
            "status": "success",
            "row_count": 42,
            "checked_at": "2026-05-01T09:00:00+09:00",
            "finished_at": "2026-05-01T09:05:00+09:00",
        }
        resp = client.get(f"{prefix}/supabase/collect-jobs/latest")
        assert resp.status_code == 200
        assert resp.json()["row_count"] == 42

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_get_job_not_found(self, client, prefix):
        resp = client.get(f"{prefix}/supabase/collect-jobs/nonexistent-uuid")
        assert resp.status_code == 404

    @pytest.mark.parametrize("prefix", ["/api/admin/naver", "/api/admin/b2"])
    def test_start_collect_job(self, client, mock_repo, prefix, monkeypatch):
        # Patch the B2TestReportService to avoid real collection
        from unittest.mock import MagicMock
        mock_service = MagicMock()
        mock_service.collect_enabled_reports.return_value = []
        monkeypatch.setattr(
            "src.api.routes.admin_naver.B2TestReportService",
            lambda **kw: mock_service,
        )
        resp = client.post(
            f"{prefix}/supabase/collect-jobs",
            json={"triggered_by": "manual", "max_clips_per_identifier": 100},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data or "status" in data
