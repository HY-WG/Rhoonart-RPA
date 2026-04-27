# -*- coding: utf-8 -*-
"""D-2 SupabaseReliefRequestRepository 단위 테스트.

실제 Supabase 연결 없이 supabase-py 클라이언트를 Mock으로 대체하여
Repository의 직렬화·역직렬화 및 쿼리 호출 패턴을 검증한다.

검증 항목:
  1. save_request / get_request — 직렬화 왕복 일관성
  2. list_requests — status 필터 적용 여부
  3. replace_request_items — DELETE 후 INSERT 패턴
  4. save_outbound_mail — upsert 호출 확인
  5. SupabaseRightsHolderDirectory.resolve_contacts — 권리사별 작품 묶기
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest
import pytz

from src.core.repositories.supabase_relief_repository import (
    SupabaseReliefRequestRepository,
    SupabaseRightsHolderDirectory,
)
from src.models import (
    OutboundMail,
    OutboundMailStatus,
    ReliefRequest,
    ReliefRequestItem,
    ReliefRequestStatus,
)

KST = pytz.timezone("Asia/Seoul")


# ── Fake Supabase 체인 빌더 ───────────────────────────────────────────────

def _make_supabase_mock(return_data: list[dict] | None = None) -> MagicMock:
    """supabase-py 클라이언트의 체이닝 쿼리 빌더를 흉내내는 Mock."""
    execute_result = MagicMock()
    execute_result.data = return_data or []

    builder = MagicMock()
    # 모든 체이닝 메서드는 자신을 반환 (method chaining)
    for method in ("select", "insert", "upsert", "update", "delete",
                   "eq", "in_", "order", "limit"):
        getattr(builder, method).return_value = builder
    builder.execute.return_value = execute_result

    client = MagicMock()
    client.table.return_value = builder
    return client, builder


def _sample_request(request_id: str = "relief-abc123") -> ReliefRequest:
    return ReliefRequest(
        request_id=request_id,
        requester_channel_name="테스트 채널",
        requester_email="test@example.com",
        requester_notes="소명 요청합니다",
        status=ReliefRequestStatus.PENDING,
        created_at=datetime(2026, 4, 24, 10, 0, tzinfo=KST),
        updated_at=datetime(2026, 4, 24, 10, 0, tzinfo=KST),
        submitted_via="web",
    )


# ── 테스트 ────────────────────────────────────────────────────────────────

def test_save_and_get_request_round_trip() -> None:
    """save_request 직렬화 → row_to_request 역직렬화 일관성 검증."""
    request = _sample_request()

    # get_request가 반환할 row 데이터를 직렬화 결과로 생성
    row = SupabaseReliefRequestRepository._request_to_row(request)
    client, builder = _make_supabase_mock(return_data=[row])

    repo = SupabaseReliefRequestRepository(client)

    # save_request: upsert 호출 확인
    repo.save_request(request)
    client.table.assert_called_with("relief_requests")
    builder.upsert.assert_called_once()
    upserted_data = builder.upsert.call_args[0][0]
    assert upserted_data["request_id"] == "relief-abc123"
    assert upserted_data["status"] == "pending"
    assert upserted_data["requester_channel_name"] == "테스트 채널"

    # get_request: 역직렬화 확인
    result = repo.get_request("relief-abc123")
    assert result is not None
    assert result.request_id == "relief-abc123"
    assert result.status == ReliefRequestStatus.PENDING
    assert result.requester_email == "test@example.com"


def test_list_requests_with_status_filter() -> None:
    """status 필터가 eq() 호출로 전달되는지 확인."""
    row = SupabaseReliefRequestRepository._request_to_row(_sample_request())
    client, builder = _make_supabase_mock(return_data=[row])

    repo = SupabaseReliefRequestRepository(client)
    results = repo.list_requests(status=ReliefRequestStatus.PENDING)

    # status 필터 적용 확인
    builder.eq.assert_called_with("status", "pending")
    assert len(results) == 1
    assert results[0].status == ReliefRequestStatus.PENDING


def test_replace_request_items_deletes_then_inserts() -> None:
    """replace_request_items가 기존 행 DELETE 후 INSERT하는지 확인."""
    client, builder = _make_supabase_mock(return_data=[])
    repo = SupabaseReliefRequestRepository(client)

    items = [
        ReliefRequestItem(
            request_id="relief-abc123",
            work_id="work-1",
            work_title="신병",
            rights_holder_name="웨이브",
            channel_folder_name="테스트채널",
        )
    ]
    repo.replace_request_items("relief-abc123", items)

    # DELETE 호출 확인
    builder.delete.assert_called_once()
    builder.eq.assert_any_call("request_id", "relief-abc123")
    # INSERT 호출 확인
    builder.insert.assert_called_once()
    inserted = builder.insert.call_args[0][0]
    assert isinstance(inserted, list)
    assert inserted[0]["work_title"] == "신병"


def test_save_outbound_mail_upsert() -> None:
    """save_outbound_mail이 upsert를 호출하는지 확인."""
    client, builder = _make_supabase_mock(return_data=[])
    repo = SupabaseReliefRequestRepository(client)

    mail = OutboundMail(
        mail_id="mail-001",
        request_id="relief-abc123",
        holder_name="웨이브",
        recipient_email="wavve@example.com",
        subject="소명 요청",
        body="<p>내용</p>",
        status=OutboundMailStatus.SENT,
        sent_at=datetime(2026, 4, 24, 10, 30, tzinfo=KST),
    )
    repo.save_outbound_mail(mail)

    builder.upsert.assert_called_once()
    upserted = builder.upsert.call_args[0][0]
    assert upserted["mail_id"] == "mail-001"
    assert upserted["status"] == "sent"


def test_resolve_contacts_groups_by_holder() -> None:
    """같은 권리사의 여러 작품이 하나의 RightsHolderContact로 묶이는지 확인."""
    rows = [
        {
            "holder_id": "h1",
            "holder_name": "웨이브",
            "recipient_email": "wavve@example.com",
            "work_title": "신병",
            "template_key": "rights_holder_request",
        },
        {
            "holder_id": "h1",
            "holder_name": "웨이브",
            "recipient_email": "wavve@example.com",
            "work_title": "재벌집 막내아들",
            "template_key": "rights_holder_request",
        },
        {
            "holder_id": "h2",
            "holder_name": "판씨네마",
            "recipient_email": "pans@example.com",
            "work_title": "청설",
            "template_key": "rights_holder_request",
        },
    ]
    client, builder = _make_supabase_mock(return_data=rows)
    directory = SupabaseRightsHolderDirectory(client)

    contacts = directory.resolve_contacts(["신병", "재벌집 막내아들", "청설"])

    assert len(contacts) == 2
    wavve_contact = next(c for c in contacts if c.holder_name == "웨이브")
    assert set(wavve_contact.work_titles) == {"신병", "재벌집 막내아들"}
    pans_contact = next(c for c in contacts if c.holder_name == "판씨네마")
    assert pans_contact.work_titles == ["청설"]
    assert pans_contact.recipient_email == "pans@example.com"
