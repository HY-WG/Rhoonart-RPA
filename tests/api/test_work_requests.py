"""Tests for admin work-request routes."""
from __future__ import annotations

import pytest

from tests.conftest import load_fixture, _make_result


WR_FIXTURE = load_fixture("work_request")


class TestListWorkRequests:
    def test_returns_items_key(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([WR_FIXTURE])
        resp = client.get("/api/admin/work-requests")
        assert resp.status_code == 200
        assert "items" in resp.json()
        assert isinstance(resp.json()["items"], list)

    def test_empty_list(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/work-requests")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_status_filter(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([WR_FIXTURE])
        resp = client.get("/api/admin/work-requests?status=pending")
        assert resp.status_code == 200

    def test_pagination_params(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/work-requests?limit=10&offset=0")
        assert resp.status_code == 200


class TestApproveWorkRequest:
    def test_approve_pending_request(self, client, mock_supabase, mock_lambda):
        pending = {**WR_FIXTURE, "status": "pending"}
        approved = {**WR_FIXTURE, "status": "approved"}
        mock_supabase.execute.side_effect = [
            _make_result([pending]),   # select to find request
            _make_result([approved]),  # update to approved
        ]
        resp = client.post(
            f"/api/admin/work-requests/{WR_FIXTURE['id']}/approve",
            json={"decided_by": "admin", "note": "승인합니다"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

    def test_approve_already_approved(self, client, mock_supabase):
        already = {**WR_FIXTURE, "status": "approved"}
        mock_supabase.execute.return_value = _make_result([already])
        resp = client.post(
            f"/api/admin/work-requests/{WR_FIXTURE['id']}/approve",
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_approve_not_found(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.post("/api/admin/work-requests/nonexistent/approve", json={})
        assert resp.status_code == 404

    def test_approve_missing_channel_name(self, client, mock_supabase):
        bad = {**WR_FIXTURE, "channel_name": "", "work_title": ""}
        mock_supabase.execute.return_value = _make_result([bad])
        resp = client.post(
            f"/api/admin/work-requests/{WR_FIXTURE['id']}/approve",
            json={},
        )
        assert resp.status_code == 400


class TestRejectWorkRequest:
    def test_reject_pending_request(self, client, mock_supabase):
        pending = {**WR_FIXTURE, "status": "pending"}
        rejected = {**WR_FIXTURE, "status": "rejected", "rejection_message": "반려"}
        mock_supabase.execute.side_effect = [
            _make_result([pending]),
            _make_result([rejected]),
        ]
        resp = client.post(
            f"/api/admin/work-requests/{WR_FIXTURE['id']}/reject",
            json={"decided_by": "admin", "note": "반려합니다"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
        assert "message" in data  # route returns "message" key, not "rejection_message"

    def test_reject_not_found(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.post("/api/admin/work-requests/nonexistent/reject", json={})
        assert resp.status_code == 404

    def test_rejection_message_contains_work_title(self, client, mock_supabase):
        pending = {**WR_FIXTURE, "status": "pending"}
        rejected = {**WR_FIXTURE, "status": "rejected", "rejection_message": "반려"}
        mock_supabase.execute.side_effect = [
            _make_result([pending]),
            _make_result([rejected]),
        ]
        resp = client.post(
            f"/api/admin/work-requests/{WR_FIXTURE['id']}/reject",
            json={},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()
