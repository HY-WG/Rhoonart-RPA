"""Tests for applications routes: A3/D3 HTML forms, triggers, monthly report."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from tests.conftest import _make_result


# ── HTML form pages ───────────────────────────────────────────────────────────

class TestA3ApplyPage:
    def test_returns_html(self, client):
        resp = client.get("/a3/apply")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_contains_form(self, client):
        resp = client.get("/a3/apply")
        assert '<form id="a3-form"' in resp.text
        assert "naver_id" in resp.text
        assert "naver_clip_profile_id" in resp.text


class TestD3ApplyPage:
    def test_returns_html(self, client):
        resp = client.get("/d3/apply")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_contains_form(self, client):
        resp = client.get("/d3/apply")
        assert '<form id="d3-form"' in resp.text
        assert "creator_name" in resp.text

    def test_prefills_channel_name(self, client):
        resp = client.get("/d3/apply?channel_name=테스트채널&channel_id=UCtest123&platform=youtube")
        assert resp.status_code == 200


# ── A3 applicants ─────────────────────────────────────────────────────────────

class TestA3Applicants:
    def test_list_requires_no_auth(self, client, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.list_applicants.return_value = []
        monkeypatch.setattr("src.api.routes.applications.build_naver_clip_repository", lambda: mock_repo)
        resp = client.get("/api/a3/applicants")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_applicant(self, client, monkeypatch):
        from src.models import NaverClipApplicant, RepresentativeChannelPlatform
        from datetime import datetime
        mock_applicant = MagicMock(spec=NaverClipApplicant)
        mock_applicant.applicant_id = "app-001"
        mock_applicant.name = "홍길동"
        mock_applicant.phone_number = "010-0000-0000"
        mock_applicant.naver_id = "naverId01"
        mock_applicant.naver_clip_profile_name = "클립프로필"
        mock_applicant.naver_clip_profile_id = "profile-001"
        mock_applicant.representative_channel_name = "테스트채널"
        mock_applicant.representative_channel_platform = RepresentativeChannelPlatform.YOUTUBE
        mock_applicant.channel_url = "https://youtube.com/@test"
        mock_applicant.submitted_at = datetime(2026, 5, 1, 9, 0, 0)

        mock_repo = MagicMock()
        mock_repo.create_applicant.return_value = mock_applicant
        monkeypatch.setattr("src.api.routes.applications.build_naver_clip_repository", lambda: mock_repo)

        payload = {
            "name": "홍길동",
            "phone_number": "010-0000-0000",
            "naver_id": "naverId01",
            "naver_clip_profile_name": "클립프로필",
            "naver_clip_profile_id": "profile-001",
            "representative_channel_name": "테스트채널",
            "representative_channel_platform": "유튜브",  # enum value, not key
            "channel_url": "https://youtube.com/@test",
        }
        resp = client.post("/api/a3/applicants", json=payload)
        assert resp.status_code == 200
        assert resp.json()["name"] == "홍길동"

    def test_create_missing_fields(self, client):
        resp = client.post("/api/a3/applicants", json={"name": "홍길동"})
        assert resp.status_code == 422


# ── Task triggers ─────────────────────────────────────────────────────────────

class TestTriggers:
    @pytest.mark.parametrize("task_id", ["A-2", "A-3", "B-2", "C-1", "C-2", "C-4", "D-3"])
    def test_trigger_task_by_id(self, client, mock_lambda, task_id):
        resp = client.post(f"/api/tasks/{task_id}/trigger", json={"payload": {}})
        assert resp.status_code == 200
        mock_lambda.assert_called()

    def test_trigger_unknown_task(self, client):
        resp = client.post("/api/tasks/Z-99/trigger", json={"payload": {}})
        assert resp.status_code == 404

    def test_trigger_a2(self, client, mock_lambda):
        payload = {"payload": {"channel_name": "테스트", "work_title": "작품A"}}
        resp = client.post("/api/a2/trigger", json=payload)
        assert resp.status_code == 200
        mock_lambda.assert_called()

    def test_trigger_a3(self, client, mock_lambda, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.post("/api/a3/trigger", json={"payload": {}})
        assert resp.status_code == 200

    def test_trigger_b2(self, client, mock_lambda):
        resp = client.post("/api/b2/trigger", json={"payload": {}})
        assert resp.status_code == 200

    def test_trigger_c1(self, client, mock_lambda):
        resp = client.post("/api/c1/trigger", json={"payload": {}})
        assert resp.status_code == 200

    def test_trigger_c2(self, client, mock_lambda):
        resp = client.post("/api/c2/trigger", json={"payload": {}})
        assert resp.status_code == 200

    def test_trigger_c3_with_work_payload(self, client, mock_lambda, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        payload = {
            "payload": {
                "work_title": "테스트작품",
                "rights_holder_name": "테스트권리사",
                "platforms": ["youtube"],
            }
        }
        resp = client.post("/api/c3/trigger", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data or "supabase_work_error" in data

    def test_trigger_c4(self, client, mock_lambda):
        resp = client.post("/api/c4/trigger", json={"payload": {}})
        assert resp.status_code == 200

    def test_trigger_d3(self, client, mock_lambda):
        resp = client.post("/api/d3/trigger", json={"payload": {}})
        assert resp.status_code == 200


# ── Monthly report ────────────────────────────────────────────────────────────

class TestMonthlyReport:
    def _make_sheet_repo(self, monkeypatch):
        mock_repo = MagicMock()
        mock_repo.applicant_sheet_embed_url.return_value = {
            "sheet_id": "test-id",
            "gid": "0",
            "url": "https://docs.google.com/spreadsheets/d/test-id/edit",
            "embed_url": "https://docs.google.com/spreadsheets/d/test-id/edit?rm=minimal",
        }
        mock_repo.get_manager.return_value = {
            "manager_name": "테스트매니저",
            "manager_email": "mgr@example.com",
            "updated_at": "",
        }
        mock_repo.update_manager.return_value = {
            "manager_name": "새매니저",
            "manager_email": "new@example.com",
            "updated_at": "2026-05-01T09:00:00+09:00",
        }
        mock_repo.export_current_sheet_xlsx.return_value = (
            "naver_inbound_202605.xlsx",
            b"PK\x03\x04fake-xlsx-content",
        )
        monkeypatch.setattr(
            "src.api.routes.applications.build_naver_monthly_report_config_repository",
            lambda: mock_repo,
        )
        return mock_repo

    def test_get_monthly_report(self, client, monkeypatch):
        self._make_sheet_repo(monkeypatch)
        resp = client.get("/api/admin/naver/monthly-report")
        assert resp.status_code == 200
        data = resp.json()
        assert "sheet" in data
        assert "manager" in data

    def test_update_manager(self, client, monkeypatch):
        self._make_sheet_repo(monkeypatch)
        resp = client.patch(
            "/api/admin/naver/monthly-report/manager",
            json={"manager_name": "새매니저", "manager_email": "new@example.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["manager_name"] == "새매니저"

    def test_update_manager_missing_name(self, client, monkeypatch):
        self._make_sheet_repo(monkeypatch)
        resp = client.patch(
            "/api/admin/naver/monthly-report/manager",
            json={"manager_name": "", "manager_email": "x@y.com"},
        )
        assert resp.status_code == 422

    def test_export_xlsx(self, client, monkeypatch):
        self._make_sheet_repo(monkeypatch)
        resp = client.get("/api/admin/naver/monthly-report/export.xlsx")
        assert resp.status_code == 200
        assert "spreadsheet" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")
