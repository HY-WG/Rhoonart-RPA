"""Tests for admin works routes: seed-channels, works/search, works/enrich, kakao-creators."""
from __future__ import annotations

import pytest

from tests.conftest import load_fixture, _make_result

WORK = load_fixture("work")
KAKAO = load_fixture("kakao_creator")


class TestSeedChannels:
    def test_returns_items(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([{"id": 1, "platform": "youtube", "status": "active"}])
        resp = client.get("/api/admin/seed-channels")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_empty(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/seed-channels")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_platform_filter(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/seed-channels?platform=youtube")
        assert resp.status_code == 200

    def test_status_filter(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/seed-channels?status=active")
        assert resp.status_code == 200


class TestWorksSearch:
    def test_short_query_returns_empty(self, client):
        resp = client.get("/api/admin/works/search?q=a")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_blank_query_returns_empty(self, client):
        resp = client.get("/api/admin/works/search")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_internal_results(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([WORK])
        resp = client.get("/api/admin/works/search?q=테스트&include_external=false")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_no_external_when_flag_false(self, client, mock_supabase, monkeypatch):
        """With include_external=false, no TMDB/OMDb HTTP calls should be made."""
        call_log = []
        original_get = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("HTTP call made"))  # noqa: E731
        monkeypatch.setattr("requests.get", lambda *a, **kw: call_log.append(a) or _dummy_resp())
        mock_supabase.execute.return_value = _make_result([WORK])
        resp = client.get("/api/admin/works/search?q=테스트&include_external=false")
        assert resp.status_code == 200
        assert call_log == []  # no external HTTP

    def test_deduplicates_results(self, client, mock_supabase):
        # Same work twice should be deduplicated
        mock_supabase.execute.return_value = _make_result([WORK, WORK])
        resp = client.get("/api/admin/works/search?q=테스트&include_external=false")
        assert resp.status_code == 200
        items = resp.json()["items"]
        titles = [i["work_title"] for i in items]
        assert len(titles) == len(set(titles))


def _dummy_resp():
    from unittest.mock import MagicMock
    m = MagicMock()
    m.ok = False
    m.json.return_value = {}
    return m


class TestWorksEnrich:
    def test_empty_title_returns_empty(self, client):
        resp = client.get("/api/admin/works/enrich?title=")
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_no_api_keys_returns_empty(self, client, monkeypatch):
        """With no TMDB/OMDb/KMDB API keys configured, result is empty dict."""
        from src.config import settings
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        monkeypatch.setattr(settings, "OMDB_API_KEY", "")
        monkeypatch.setattr(settings, "KMDB_API_KEY", "")
        monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "")
        resp = client.get("/api/admin/works/enrich?title=테스트작품")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_debug_log_included_when_requested(self, client, monkeypatch):
        from src.config import settings
        monkeypatch.setattr(settings, "TMDB_API_KEY", "")
        monkeypatch.setattr(settings, "OMDB_API_KEY", "")
        monkeypatch.setattr(settings, "KMDB_API_KEY", "")
        monkeypatch.setattr(settings, "YOUTUBE_API_KEY", "")
        resp = client.get("/api/admin/works/enrich?title=테스트&debug_force_empty_sources=kmdb")
        assert resp.status_code == 200
        data = resp.json()
        assert "debug_log" in data

    def test_explicit_source_omdb(self, client, monkeypatch):
        from src.config import settings
        monkeypatch.setattr(settings, "OMDB_API_KEY", "")
        resp = client.get("/api/admin/works/enrich?title=TestWork&source=omdb&external_id=tt1234567")
        assert resp.status_code == 200


class TestKakaoCreators:
    def test_returns_items(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([KAKAO])
        resp = client.get("/api/admin/kakao-creators")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 1

    def test_empty_list(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/kakao-creators")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_status_filter(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/kakao-creators?status=pending")
        assert resp.status_code == 200
