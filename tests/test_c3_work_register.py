# -*- coding: utf-8 -*-
"""C-3. 신규 작품 등록 핸들러 단위 테스트.

검증 항목:
  1. admin_client 미전달 시 StubAdminAPIClient 자동 사용 → success=True
  2. guideline=None → guideline_method="skipped", success=True
  3. 빈 WorkGuideline (is_empty=True) → guideline_method="skipped"
  4. 단순 가이드라인 (should_use_notion=False) → guideline_method="admin_text"
  5. 복잡 가이드라인 (should_use_notion=True) + dry_run → guideline_method="notion_page"
  6. 복잡 가이드라인 + create_guideline_page 모킹 → notion URL 저장
  7. create_guideline_page 실패(None 반환) → success=False
  8. HttpAdminAPIClient + register_work 성공 → work_id 반환
  9. HttpAdminAPIClient + register_work HTTP 오류 → success=False
  10. dry_run=True → work_id="dry-run-work-id", API 미호출
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.core.clients.admin_api_client import (
    HttpAdminAPIClient,
    StubAdminAPIClient,
)
from src.handlers.c3_work_register import run
from src.models.work import Work
from src.models.work_guideline import WorkGuideline


# ── 픽스처 헬퍼 ──────────────────────────────────────────────────────────────────

def _make_work(**overrides) -> Work:
    defaults = dict(
        work_title="신병",
        rights_holder_name="웨이브",
        release_year=2022,
        description="군대 이야기",
        director="홍길동",
        cast="배우1, 배우2",
        genre="드라마",
        video_type="드라마",
        country="한국",
        platforms=["웨이브", "넷플릭스"],
        platform_video_url="https://wavve.com/play/xxx",
        trailer_url="https://youtube.com/watch?v=xxx",
        source_download_url="https://drive.google.com/xxx",
    )
    defaults.update(overrides)
    return Work(**defaults)


def _make_simple_guideline() -> WorkGuideline:
    """should_use_notion() == False 인 단순 가이드라인."""
    return WorkGuideline(
        source_provided_date=date(2024, 5, 1),
        review_required=False,
    )


def _make_complex_guideline() -> WorkGuideline:
    """should_use_notion() == True 인 복잡 가이드라인 (텍스트 300자 초과)."""
    return WorkGuideline(
        usage_notes="주의사항: " + "가" * 200,
        format_guide="포맷: " + "나" * 150,
        other_platforms="네이버 클립 가능 / 카카오 숏폼 불가",
        logo_subtitle_provided=True,
        review_required=True,
    )


# ── 테스트 케이스 ────────────────────────────────────────────────────────────────

class TestRunWithStubClient:

    def test_no_admin_client_uses_stub_automatically(self) -> None:
        """admin_client 미전달 → StubAdminAPIClient 자동 사용 → success=True."""
        result = run(work=_make_work())

        assert result["success"] is True
        assert result["work_id"] is not None
        assert result["work_title"] == "신병"
        assert result["rights_holder_name"] == "웨이브"

    def test_explicit_stub_client(self) -> None:
        """StubAdminAPIClient 명시 전달 → success=True."""
        result = run(work=_make_work(), admin_client=StubAdminAPIClient())

        assert result["success"] is True
        assert result["work_id"] is not None

    def test_guideline_none_skips_step2(self) -> None:
        """guideline=None → 가이드라인 등록 건너뜀."""
        result = run(work=_make_work(), guideline=None, admin_client=StubAdminAPIClient())

        assert result["success"] is True
        assert result["guideline_method"] == "skipped"
        assert result["guideline_ref"] == ""

    def test_empty_guideline_skips_step2(self) -> None:
        """WorkGuideline() (모든 필드 None) → is_empty=True → skipped."""
        empty = WorkGuideline()
        assert empty.is_empty()

        result = run(work=_make_work(), guideline=empty, admin_client=StubAdminAPIClient())

        assert result["success"] is True
        assert result["guideline_method"] == "skipped"

    def test_simple_guideline_uses_admin_text(self) -> None:
        """단순 가이드라인 → should_use_notion=False → admin_text 방식."""
        guideline = _make_simple_guideline()
        assert not guideline.should_use_notion()

        result = run(work=_make_work(), guideline=guideline, admin_client=StubAdminAPIClient())

        assert result["success"] is True
        assert result["guideline_method"] == "admin_text"
        assert result["guideline_ref"] != ""  # 텍스트 미리보기가 들어있음

    def test_complex_guideline_dry_run_uses_notion(self) -> None:
        """복잡 가이드라인 + dry_run=True → notion_page 방식, API 미호출."""
        guideline = _make_complex_guideline()
        assert guideline.should_use_notion()

        result = run(
            work=_make_work(),
            guideline=guideline,
            admin_client=StubAdminAPIClient(),
            dry_run=True,
        )

        assert result["success"] is True
        assert result["guideline_method"] == "notion_page"
        assert "dry-run" in result["guideline_ref"]

    def test_dry_run_returns_fixed_work_id(self) -> None:
        """dry_run=True → work_id='dry-run-work-id'."""
        result = run(work=_make_work(), admin_client=StubAdminAPIClient(), dry_run=True)

        assert result["work_id"] == "dry-run-work-id"


class TestRunNotionPage:

    def test_notion_page_created_and_url_stored(self) -> None:
        """create_guideline_page 모킹 → 반환 URL이 guideline_ref에 저장됨."""
        guideline = _make_complex_guideline()
        fake_url = "https://www.notion.so/page-abc123"

        with patch(
            "src.handlers.c3_work_register.create_guideline_page",
            return_value=fake_url,
        ):
            result = run(
                work=_make_work(),
                guideline=guideline,
                admin_client=StubAdminAPIClient(),
            )

        assert result["success"] is True
        assert result["guideline_method"] == "notion_page"
        assert result["guideline_ref"] == fake_url

    def test_notion_page_creation_fails(self) -> None:
        """create_guideline_page → None 반환 시 success=False."""
        guideline = _make_complex_guideline()

        with patch(
            "src.handlers.c3_work_register.create_guideline_page",
            return_value=None,
        ):
            result = run(
                work=_make_work(),
                guideline=guideline,
                admin_client=StubAdminAPIClient(),
            )

        assert result["success"] is False
        assert result["guideline_method"] == "notion_page"
        assert result["work_id"] is not None  # STEP 1은 성공

    def test_notion_page_called_with_correct_args(self) -> None:
        """create_guideline_page 에 work_title과 guideline이 올바르게 전달됨."""
        guideline = _make_complex_guideline()
        work = _make_work(work_title="청설")

        with patch(
            "src.handlers.c3_work_register.create_guideline_page",
            return_value="https://notion.so/x",
        ) as mock_create:
            run(work=work, guideline=guideline, admin_client=StubAdminAPIClient())

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["work_title"] == "청설"
        assert call_kwargs["guideline"] is guideline


class TestRunWithHttpClient:

    def _mock_post_success(self, work_id: str = "work-abc123"):
        """register_work 성공 mock."""
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"id": work_id}
        fake_resp.raise_for_status.return_value = None
        return fake_resp

    def test_http_client_register_work_success(self) -> None:
        """HttpAdminAPIClient + 성공 응답 → work_id 반환."""
        client = HttpAdminAPIClient(base_url="https://admin.example.com", token="tok")
        fake_resp = self._mock_post_success("work-123")

        with patch(
            "src.core.clients.admin_api_client.http_requests.post",
            return_value=fake_resp,
        ):
            result = run(work=_make_work(), admin_client=client)

        assert result["success"] is True
        assert result["work_id"] == "work-123"
        assert result["guideline_method"] == "skipped"

    def test_http_client_register_work_api_failure(self) -> None:
        """HttpAdminAPIClient + HTTP 오류 → success=False, work_id=None."""
        client = HttpAdminAPIClient(base_url="https://admin.example.com", token="tok")

        with patch(
            "src.core.clients.admin_api_client.http_requests.post",
            side_effect=RuntimeError("HTTP 500"),
        ):
            result = run(work=_make_work(), admin_client=client)

        assert result["success"] is False
        assert result["work_id"] is None

    def test_http_client_register_work_empty_id(self) -> None:
        """HTTP 응답 body에 id 없음 → success=False."""
        client = HttpAdminAPIClient(base_url="https://admin.example.com", token="tok")
        fake_resp = MagicMock()
        fake_resp.json.return_value = {}  # id 없음
        fake_resp.raise_for_status.return_value = None

        with patch(
            "src.core.clients.admin_api_client.http_requests.post",
            return_value=fake_resp,
        ):
            result = run(work=_make_work(), admin_client=client)

        assert result["success"] is False
        assert result["work_id"] is None

    def test_http_client_payload_fields(self) -> None:
        """register_work 호출 시 Work 필드 전체가 payload에 포함됨."""
        client = HttpAdminAPIClient(base_url="https://admin.example.com", token="tok")
        captured: list[dict] = []

        def fake_post(url, json=None, headers=None, timeout=None):
            captured.append(json or {})
            resp = MagicMock()
            resp.json.return_value = {"id": "work-xyz"}
            resp.raise_for_status.return_value = None
            return resp

        with patch(
            "src.core.clients.admin_api_client.http_requests.post",
            side_effect=fake_post,
        ):
            run(work=_make_work(), admin_client=client)

        assert len(captured) == 1
        payload = captured[0]
        assert payload["title"] == "신병"
        assert payload["rights_holder"] == "웨이브"
        assert payload["release_year"] == 2022
        assert payload["genre"] == "드라마"
        assert payload["platforms"] == ["웨이브", "넷플릭스"]
        assert payload["platform_video_url"] == "https://wavve.com/play/xxx"

    def test_http_client_update_guideline_text(self) -> None:
        """admin_text 방식: PATCH /api/works/{id}/guideline 호출됨."""
        client = HttpAdminAPIClient(base_url="https://admin.example.com", token="tok")
        guideline = _make_simple_guideline()
        patched_urls: list[str] = []

        def fake_post(url, **kw):
            resp = MagicMock()
            resp.json.return_value = {"id": "work-555"}
            resp.raise_for_status.return_value = None
            return resp

        def fake_patch(url, **kw):
            patched_urls.append(url)
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            return resp

        with patch("src.core.clients.admin_api_client.http_requests.post", side_effect=fake_post), \
             patch("src.core.clients.admin_api_client.http_requests.patch", side_effect=fake_patch):
            result = run(work=_make_work(), guideline=guideline, admin_client=client)

        assert result["success"] is True
        assert result["guideline_method"] == "admin_text"
        assert any("work-555" in url for url in patched_urls)
