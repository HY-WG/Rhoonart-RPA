"""Tests for admin copyright-claims and official-documents routes."""
from __future__ import annotations

import pytest

from tests.conftest import load_fixture, _make_result

CLAIM = load_fixture("copyright_claim")


class TestListCopyrightClaims:
    def test_returns_items_and_groups(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([CLAIM])
        resp = client.get("/api/admin/copyright-claims")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "groups" in data
        assert "fallback" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["groups"], list)

    def test_fallback_on_db_error(self, client, mock_supabase):
        # When Supabase raises, route falls back to sample data
        mock_supabase.execute.side_effect = Exception("DB unavailable")
        resp = client.get("/api/admin/copyright-claims")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fallback"] is True

    def test_empty_claims(self, client, mock_supabase):
        results = [_make_result([]), _make_result([])]
        mock_supabase.execute.side_effect = results
        resp = client.get("/api/admin/copyright-claims")
        assert resp.status_code == 200


class TestRequestCopyrightClaim:
    def test_request_for_sample_holder(self, client, mock_supabase):
        # sample-holder IDs are resolved without a DB lookup
        mock_supabase.execute.side_effect = [
            _make_result([]),   # update copyright_claims
            _make_result([]),   # right_holder_status
            _make_result([]),   # optional_doc lookup
        ]
        resp = client.post(
            "/api/admin/copyright-claims/right-holders/sample-holder-1/request",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "right_holder_id" in data

    def test_request_for_real_holder(self, client, mock_supabase):
        from tests.conftest import make_supabase_mock
        mock_supabase.execute.side_effect = [
            _make_result([]),                                          # update claims
            _make_result([{"rights_holder_name": "테스트권리사"}]),    # rights_holders lookup
            _make_result([]),                                          # right_holder_status
            _make_result([]),                                          # doc lookup
        ]
        resp = client.post(
            "/api/admin/copyright-claims/right-holders/rh-001/request",
            json={},
        )
        assert resp.status_code == 200


class TestOfficialDocuments:
    def test_list_official_documents(self, client, mock_supabase):
        doc = {
            "id": "od-001",
            "work_id": "1",
            "right_holder_id": "rh-001",
            "content_body": {},
            "official_document_status": "not_requested",
        }
        mock_supabase.execute.return_value = _make_result([doc])
        resp = client.get("/api/admin/official-documents")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_get_document_not_found(self, client, mock_supabase):
        # Route always returns 200 with fallback data when document not found
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/admin/official-documents/nonexistent")
        assert resp.status_code == 200
        assert resp.json().get("fallback") is True

    def test_get_document_found(self, client, mock_supabase):
        doc = {"id": "od-001", "work_id": "1", "content_body": {}}
        mock_supabase.execute.return_value = _make_result([doc])
        resp = client.get("/api/admin/official-documents/od-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "od-001"

    def test_put_document_upsert(self, client, mock_supabase):
        saved = {"id": "od-001", "work_id": "1", "content_body": {"claim_number": "2026-001"}}
        mock_supabase.execute.return_value = _make_result([saved])
        resp = client.put(
            "/api/admin/official-documents/od-001",
            json={"content_body": {"claim_number": "2026-001"}, "work_id": "1"},
        )
        assert resp.status_code == 200


class TestPartnerCopyrightClaims:
    def test_list_partner_claims(self, client, mock_supabase):
        mock_supabase.execute.return_value = _make_result([CLAIM])
        resp = client.get("/api/partner/copyright-claims")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_get_partner_document_not_found(self, client, mock_supabase):
        # Route always returns 200 with fallback data when document not found
        mock_supabase.execute.return_value = _make_result([])
        resp = client.get("/api/partner/official-documents/od-missing")
        assert resp.status_code == 200
        assert resp.json().get("fallback") is True


class TestOfficialDocumentFile:
    def test_download_file_not_found(self, client, mock_supabase, monkeypatch):
        # Patch the storage download to raise 404
        from fastapi import HTTPException

        def _raise(*a, **kw):
            raise HTTPException(status_code=404, detail="not found")

        monkeypatch.setattr(
            "src.api.routes.admin_copyright.download_official_document_file",
            _raise,
        )
        mock_supabase.execute.return_value = _make_result([{"id": "od-001", "official_document_file_name": "test.pdf"}])
        resp = client.get("/api/admin/copyright-claims/od-001/official-document-file")
        assert resp.status_code == 404
