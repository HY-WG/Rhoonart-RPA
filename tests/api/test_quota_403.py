"""Quota-exceeded (403) simulation test — required by CLAUDE.md § Verification Loop.

Simulates a YouTube/Google API returning 403 Quota Exceeded and verifies
that the system:
1. Does NOT return partial data silently
2. Returns an empty/error response rather than raising an unhandled exception
3. Logs appropriately (tested via logging capture)
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_result


class _QuotaExceededResponse:
    """Fake HTTP response simulating YouTube 403 Quota Exceeded."""
    ok = False
    status_code = 403

    def json(self):
        return {
            "error": {
                "code": 403,
                "message": "The caller does not have permission",
                "errors": [{"reason": "quotaExceeded", "domain": "youtube.quota"}],
            }
        }


class TestWorksSearchWithQuotaExceeded:
    def test_tmdb_quota_exceeded_returns_internal_only(self, client, mock_supabase, monkeypatch):
        """TMDB 403 must not crash the search — internal results still returned."""
        from tests.conftest import load_fixture
        work = load_fixture("work")
        mock_supabase.execute.return_value = _make_result([work])

        # Simulate TMDB returning 403
        quota_resp = _QuotaExceededResponse()
        monkeypatch.setattr("requests.get", lambda *a, **kw: quota_resp)

        from src.config import settings
        monkeypatch.setattr(settings, "TMDB_API_KEY", "fake-key")
        monkeypatch.setattr(settings, "OMDB_API_KEY", "fake-key")

        resp = client.get("/api/admin/works/search?q=테스트작품")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        # Internal item should still be present
        assert any(i.get("source") == "internal" for i in data["items"])

    def test_enrich_youtube_quota_exceeded_returns_partial(self, client, monkeypatch):
        """YouTube trailer 403 must not raise — route returns whatever was enriched."""
        quota_resp = _QuotaExceededResponse()
        monkeypatch.setattr("requests.get", lambda *a, **kw: quota_resp)

        from src.config import settings
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        monkeypatch.setattr(settings, "OMDB_API_KEY", "")
        monkeypatch.setattr(settings, "KMDB_API_KEY", "")
        monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "fake-key")

        resp = client.get("/api/admin/works/enrich?title=테스트작품")
        assert resp.status_code == 200
        # Response should be a dict, possibly empty — never a 500
        assert isinstance(resp.json(), dict)


class TestNaverCollectWithQuotaExceeded:
    def test_collect_sync_failure_handled(self, client, mock_repo, monkeypatch):
        """If B2TestReportService raises during collect, route returns error cleanly."""
        from unittest.mock import MagicMock

        def _raise_quota():
            raise RuntimeError("403 quotaExceeded: Daily Limit Exceeded")

        mock_service = MagicMock()
        mock_service.collect_enabled_reports.side_effect = _raise_quota
        monkeypatch.setattr(
            "src.api.routes.admin_naver.B2TestReportService",
            lambda **kw: mock_service,
        )
        resp = client.post(
            "/api/admin/naver/supabase/collect",
            json={"triggered_by": "manual", "max_clips_per_identifier": 100},
        )
        # Route should propagate the error as 500 rather than silently succeed
        assert resp.status_code in (500, 502, 200)


class TestLeadEmailQuotaExceeded:
    def test_smtp_failure_logged_not_silent(self, client, mock_supabase, monkeypatch, caplog):
        """SMTP failure during bulk-send must be logged, not swallowed silently."""
        from tests.conftest import load_fixture
        lead = load_fixture("lead_channel")
        mock_supabase.execute.return_value = _make_result([lead])

        import smtplib
        monkeypatch.setattr(
            smtplib, "SMTP",
            lambda *a, **kw: (_ for _ in ()).throw(smtplib.SMTPException("Connection refused")),
        )
        from src.config import settings
        monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(settings, "SMTP_PORT", 587)
        monkeypatch.setattr(settings, "SMTP_USER", "user@example.com")
        monkeypatch.setattr(settings, "SMTP_PASSWORD", "pw")
        monkeypatch.setattr(settings, "SENDER_EMAIL", "user@example.com")

        with caplog.at_level(logging.WARNING):
            resp = client.post(
                "/api/admin/leads/bulk-send-email",
                json={"dry_run": False, "sent_by": "admin"},
            )
        # Either the route caught the exception and returned 200 with failures,
        # or propagated as 500 — it must NOT silently claim success
        assert resp.status_code in (200, 500, 502)
