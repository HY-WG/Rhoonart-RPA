"""Tests for admin reports routes (Metabase, Naver schedules)."""
from __future__ import annotations

import pytest

from tests.conftest import load_fixture

RIGHTS_HOLDER = load_fixture("rights_holder")

_SCHEDULE = {
    "schedule_id": 1,
    "rights_holder_name": "테스트권리사",
    "enabled": True,
    "days_of_week": [1, 3, 5],
    "send_time": "11:00",
    "timezone": "Asia/Seoul",
    "recipient_emails": ["admin@example.com"],
    "metabase_embed_url": "http://localhost:3000/public/dashboard/test-uuid",
    "last_sent_at": None,
}


class TestMetabaseReport:
    def test_list_reports(self, client, mock_repo):
        mock_repo.list_rights_holders.return_value = [RIGHTS_HOLDER]
        resp = client.get("/api/admin/reports/metabase")
        assert resp.status_code == 200
        data = resp.json()
        assert "reports" in data
        assert isinstance(data["reports"], list)

    def test_list_reports_empty(self, client, mock_repo):
        mock_repo.list_rights_holders.return_value = []
        resp = client.get("/api/admin/reports/metabase")
        assert resp.status_code == 200
        assert resp.json()["reports"] == []

    def test_report_configured_flag(self, client, mock_repo):
        mock_repo.list_rights_holders.return_value = [RIGHTS_HOLDER]
        data = client.get("/api/admin/reports/metabase").json()
        report = data["reports"][0]
        assert report["configured"] is True

    def test_report_without_embed_url(self, client, mock_repo):
        rh_no_url = {**RIGHTS_HOLDER, "metabase_embed_url": ""}
        mock_repo.list_rights_holders.return_value = [rh_no_url]
        data = client.get("/api/admin/reports/metabase").json()
        report = data["reports"][0]
        assert report["configured"] is False


class TestSendMetabaseReport:
    def test_send_not_found(self, client, mock_repo):
        mock_repo.list_rights_holders.return_value = []
        resp = client.post(
            "/api/admin/reports/metabase/send",
            json={"rights_holder_name": "없는권리사"},
        )
        assert resp.status_code == 404

    def test_send_missing_email(self, client, mock_repo):
        rh_no_email = {**RIGHTS_HOLDER, "email": ""}
        mock_repo.list_rights_holders.return_value = [rh_no_email]
        resp = client.post(
            "/api/admin/reports/metabase/send",
            json={"rights_holder_name": RIGHTS_HOLDER["rights_holder_name"]},
        )
        assert resp.status_code == 400

    def test_send_missing_dashboard_url(self, client, mock_repo):
        rh_no_url = {**RIGHTS_HOLDER, "metabase_embed_url": ""}
        mock_repo.list_rights_holders.return_value = [rh_no_url]
        resp = client.post(
            "/api/admin/reports/metabase/send",
            json={"rights_holder_name": RIGHTS_HOLDER["rights_holder_name"]},
        )
        assert resp.status_code == 400

    def test_send_missing_rights_holder_name(self, client):
        resp = client.post("/api/admin/reports/metabase/send", json={})
        assert resp.status_code == 422


class TestNaverReportSchedules:
    def test_list_schedules(self, client, mock_repo):
        mock_repo.list_report_schedules.return_value = [_SCHEDULE]
        mock_repo.list_enabled_report_works.return_value = []
        mock_repo.list_report_delivery_logs.return_value = []
        resp = client.get("/api/admin/reports/naver/schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert "schedules" in data
        assert "works" in data
        assert "logs" in data

    def test_list_schedules_empty(self, client, mock_repo):
        from src.api.dependencies import NAVER_REPORT_SCHEDULES_CACHE
        NAVER_REPORT_SCHEDULES_CACHE.clear()  # evict cache populated by prior test
        mock_repo.list_report_schedules.return_value = []
        resp = client.get("/api/admin/reports/naver/schedules")
        assert resp.status_code == 200
        assert resp.json()["schedules"] == []

    def test_update_schedule_valid(self, client, mock_repo):
        mock_repo.update_report_schedule.return_value = {**_SCHEDULE}
        resp = client.patch(
            "/api/admin/reports/naver/schedules/1",
            json={
                "enabled": True,
                "days_of_week": [1, 3],
                "send_time": "11:00",
                "timezone": "Asia/Seoul",
                "recipient_emails": ["admin@example.com"],
                "include_work_ids": [],
            },
        )
        assert resp.status_code == 200

    def test_update_schedule_invalid_days(self, client):
        resp = client.patch(
            "/api/admin/reports/naver/schedules/1",
            json={
                "enabled": True,
                "days_of_week": [0, 8],  # out of 1–7 range
                "send_time": "11:00",
                "recipient_emails": [],
                "include_work_ids": [],
            },
        )
        assert resp.status_code == 400

    def test_update_schedule_invalid_time(self, client):
        resp = client.patch(
            "/api/admin/reports/naver/schedules/1",
            json={
                "enabled": True,
                "days_of_week": [1],
                "send_time": "not-a-time",
                "recipient_emails": [],
                "include_work_ids": [],
            },
        )
        assert resp.status_code == 400


class TestRunDueSchedules:
    def test_run_due_no_due_schedules(self, client, mock_repo):
        mock_repo.list_report_schedules.return_value = []
        resp = client.post("/api/admin/reports/naver/schedules/run-due")
        assert resp.status_code == 200
        data = resp.json()
        assert data["due_count"] == 0
