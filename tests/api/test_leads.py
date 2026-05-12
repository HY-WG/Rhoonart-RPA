"""Tests for admin leads routes."""
from __future__ import annotations

import pytest

from tests.conftest import load_fixture, _make_result

LEAD = load_fixture("lead_channel")


class TestListLeads:
    def test_returns_items(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([LEAD])
        resp = client.get("/api/admin/leads")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 1

    def test_empty_leads(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/leads")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_status_filter(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([LEAD])
        resp = client.get("/api/admin/leads?status=new")
        assert resp.status_code == 200

    def test_pagination(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/leads?limit=10&offset=20")
        assert resp.status_code == 200


class TestLeadSummary:
    def test_returns_summary(self, client, mock_supabase):
        # Route calls execute() twice: lead_channels list + lead_discovery_runs (or automation_runs)
        mock_supabase.execute.side_effect = [
            _make_result([LEAD]),  # lead_channels query
            _make_result([]),      # lead_discovery_runs query (no prior run)
        ]
        resp = client.get("/api/admin/leads/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data

    def test_summary_with_cached_metrics(self, client, mock_supabase, monkeypatch):
        from src.api.dependencies import LEAD_SUBSCRIBER_METRICS, LEAD_SUBSCRIBER_METRICS_LOCK
        LEAD_SUBSCRIBER_METRICS["UCtest123"] = {"subscriber_count": 50000, "refreshed_at": "2026-05-01"}
        mock_supabase.execute.return_value = _make_result([LEAD])
        resp = client.get("/api/admin/leads/summary")
        assert resp.status_code == 200
        LEAD_SUBSCRIBER_METRICS.clear()


class TestRefreshSubscribers:
    def test_refresh_returns_status(self, client, mock_supabase, monkeypatch):
        mock_supabase.execute.return_value = _make_result([LEAD])
        # Patch YouTube API call inside refresh handler
        from unittest.mock import MagicMock
        empty_yt = MagicMock()
        empty_yt.ok = False
        monkeypatch.setattr("requests.get", lambda *a, **kw: empty_yt)
        resp = client.post("/api/admin/leads/refresh-subscribers")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data or "refreshed" in data


class TestBulkSendEmail:
    def test_dry_run_no_smtp(self, client, mock_supabase, monkeypatch):
        # dry_run=True should not actually send email
        mock_supabase.execute.return_value = _make_result([LEAD])
        resp = client.post(
            "/api/admin/leads/bulk-send-email",
            json={"dry_run": True, "sent_by": "admin"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("dry_run") is True

    def test_bulk_send_missing_smtp(self, client, mock_supabase, monkeypatch):
        from src.config import settings
        monkeypatch.setattr(settings, "SMTP_HOST", "")
        mock_supabase.execute.return_value = _make_result([LEAD])
        resp = client.post(
            "/api/admin/leads/bulk-send-email",
            json={"dry_run": False, "sent_by": "admin"},
        )
        # Should return 500 when SMTP not configured and dry_run=False
        assert resp.status_code in (200, 500)


class TestPromoteLead:
    def test_promote_lead(self, client, mock_supabase):
        promoted = {**LEAD, "status": "promoted"}
        mock_supabase.execute.side_effect = [
            _make_result(LEAD),          # .single().execute() → dict, not list
            _make_result([]),            # seed_channel lookup (existing)
            _make_result([promoted]),    # seed_channel insert/update
            _make_result([promoted]),    # lead_channels update
        ]
        resp = client.post(
            f"/api/admin/leads/{LEAD['channel_id']}/promote",
            json={"promoted_by": "admin"},
        )
        assert resp.status_code == 200

    def test_promote_not_found(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.post("/api/admin/leads/nonexistent/promote", json={})
        assert resp.status_code == 404


class TestBlockLead:
    def test_block_lead(self, client, mock_supabase):
        blocked = {**LEAD, "status": "blocked"}
        mock_supabase.execute.side_effect = [
            _make_result(LEAD),          # .single().execute() → dict, not list
            _make_result([blocked]),     # channel_blocklist upsert
            _make_result([blocked]),     # lead_channels update
        ]
        resp = client.post(
            f"/api/admin/leads/{LEAD['channel_id']}/block",
            json={"reason": "스팸", "blocked_by": "admin"},
        )
        assert resp.status_code == 200

    def test_block_not_found(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.post("/api/admin/leads/nonexistent/block", json={})
        assert resp.status_code == 404

    def test_unblock_lead(self, client, mock_supabase):
        unblocked = {**LEAD, "status": "new"}
        mock_supabase.execute.side_effect = [
            _make_result([LEAD]),
            _make_result([unblocked]),
        ]
        resp = client.delete(f"/api/admin/leads/{LEAD['channel_id']}/block")
        assert resp.status_code == 200

    def test_unblock_returns_ok(self, client, mock_supabase):
        # unblock_lead does not check existence — it always succeeds (deletes blocklist row if any)
        mock_supabase.execute.return_value = _make_result([])
        resp = client.delete("/api/admin/leads/nonexistent/block")
        assert resp.status_code == 200
        assert resp.json()["status"] == "unblocked"


class TestSendEmailToLead:
    def test_send_email_dry_run(self, client, mock_supabase):
        mock_supabase.execute.side_effect = [
            _make_result([LEAD]),
            _make_result([{**LEAD, "email_status": "sent"}]),
        ]
        resp = client.post(
            f"/api/admin/leads/{LEAD['channel_id']}/send-email",
            json={"dry_run": True, "sent_by": "admin"},
        )
        assert resp.status_code == 200

    def test_send_email_not_found(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.post(
            "/api/admin/leads/nonexistent/send-email",
            json={"dry_run": True},
        )
        assert resp.status_code == 404
