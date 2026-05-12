"""Tests for admin overview routes: /, /health, /api/admin/overview, etc."""
from __future__ import annotations

import pytest

from tests.conftest import _make_result


class TestIndex:
    def test_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Rhoonart RPA Control Server" in resp.text

    def test_contains_nav_links(self, client):
        resp = client.get("/")
        assert "/a3/apply" in resp.text
        assert "/d3/apply" in resp.text
        assert "/docs" in resp.text


class TestHealth:
    def test_status_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "time" in data
        assert "version" in data

    def test_response_schema(self, client):
        data = client.get("/health").json()
        for key in ("status", "time", "dashboard_repository", "auth_required"):
            assert key in data, f"missing key: {key}"


class TestAdminOverview:
    def test_returns_pending_list(self, client):
        resp = client.get("/api/admin/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "pending" in data
        assert isinstance(data["pending"], list)
        assert len(data["pending"]) == 5  # five overview cards

    def test_card_ids_present(self, client):
        cards = client.get("/api/admin/overview").json()["pending"]
        ids = {c["id"] for c in cards}
        assert "work-application" in ids
        assert "naver-youtube-report" in ids
        assert "lead-summary" in ids

    def test_count_fields_are_integers(self, client):
        cards = client.get("/api/admin/overview").json()["pending"]
        for card in cards:
            assert isinstance(card["count"], int), f"card {card['id']} count is not int"

    def test_with_pending_work_requests(self, client, mock_supabase):
        # Make the count call return 3 pending requests
        result_with_count = _make_result([])
        result_with_count.count = 3
        mock_supabase.execute.return_value = result_with_count
        resp = client.get("/api/admin/overview")
        assert resp.status_code == 200


class TestA2ManualRequestStub:
    def test_stub_response(self, client):
        payload = {"channel_name": "테스트채널", "work_title": "테스트작품"}
        resp = client.post("/api/a2/manual-request-stub", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "stub_only"
        assert "channel_name" in data
        assert "work_title" in data

    def test_requires_fields(self, client):
        resp = client.post("/api/a2/manual-request-stub", json={})
        # Pydantic validation — missing required fields → 422
        assert resp.status_code == 422


class TestB2AdminPage:
    def test_returns_html(self, client):
        resp = client.get("/admin/b2")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "B-2" in resp.text
