# -*- coding: utf-8 -*-
"""C-1. 리드 발굴 핸들러 단위 테스트.

외부 의존성(YouTube API, Google Sheets)은 모두 monkeypatch로 대체.
검증 항목:
  1. A/B/B? 등급 채널만 리드 시트에 upsert (C등급 제외)
  2. 반환 딕셔너리의 등급별 카운트 정확성
  3. ChannelDiscovery → Lead 모델 변환 정확성 (handle 유/무)
  4. 채널 설명에서 이메일 추출 로직
  5. 이메일이 Lead 모델에 올바르게 전달되는지
"""
from __future__ import annotations

import pytest

from src.core.crawlers.youtube_shorts_crawler import (
    ChannelDiscovery,
    _extract_email_from_description,
)
from src.handlers import c1_lead_filter
from tests.fakes import FakeLeadRepo, FakeLogRepo, FakeNotifier


def _make_channel(
    channel_id: str,
    tier: str,
    *,
    monthly_views: int = 5_000_000,
    handle: str = "",
) -> ChannelDiscovery:
    return ChannelDiscovery(
        channel_id=channel_id,
        handle=handle,
        name=f"Channel {channel_id}",
        subscriber_count=100_000,
        total_view_count=50_000_000,
        monthly_shorts_views=monthly_views,
        shorts_count_30d=30,
        tier=tier,
    )


class FakeYTCrawler:
    """YouTubeShortsCrawler 대역 — 고정 채널 목록 반환."""

    def __init__(self, discoveries: list[ChannelDiscovery]):
        self._discoveries = discoveries

    def discover(self) -> list[ChannelDiscovery]:
        return self._discoveries


def test_c1_only_upserts_qualifiable_tiers(monkeypatch) -> None:
    """A/B/B? 등급만 리드 시트에 upsert되고 C등급은 건너뜀."""
    discoveries = [
        _make_channel("ch-a", "A", monthly_views=25_000_000, handle="@drama_a"),
        _make_channel("ch-b", "B", monthly_views=8_000_000,  handle="@drama_b"),
        _make_channel("ch-bp", "B?", monthly_views=6_000_000),
        _make_channel("ch-c1", "C", monthly_views=1_000_000),
        _make_channel("ch-c2", "C", monthly_views=500_000),
    ]

    monkeypatch.setattr(c1_lead_filter, "load_seed_urls_from_sheet", lambda *_: [])
    monkeypatch.setattr(
        c1_lead_filter, "YouTubeShortsCrawler",
        lambda **_: FakeYTCrawler(discoveries),
    )

    lead_repo = FakeLeadRepo(upsert_result=3)  # A+B+B? = 3건
    result = c1_lead_filter.run(
        lead_repo=lead_repo,
        log_repo=FakeLogRepo(),
        slack_notifier=FakeNotifier(),
        api_key="test-key",
        seed_sheet_id="sheet-id",
    )

    # C등급 2건 제외, A+B+B? 3건만 upsert
    assert len(lead_repo.upserted) == 3
    upserted_ids = {lead.channel_id for lead in lead_repo.upserted}
    assert upserted_ids == {"ch-a", "ch-b", "ch-bp"}
    assert "ch-c1" not in upserted_ids
    assert "ch-c2" not in upserted_ids


def test_c1_returns_correct_tier_counts(monkeypatch) -> None:
    """반환 딕셔너리의 등급별 카운트가 정확한지 검증."""
    discoveries = [
        _make_channel("a1", "A"),
        _make_channel("a2", "A"),
        _make_channel("b1", "B"),
        _make_channel("bp1", "B?"),
        _make_channel("bp2", "B?"),
        _make_channel("c1", "C"),
    ]

    monkeypatch.setattr(c1_lead_filter, "load_seed_urls_from_sheet", lambda *_: [])
    monkeypatch.setattr(
        c1_lead_filter, "YouTubeShortsCrawler",
        lambda **_: FakeYTCrawler(discoveries),
    )

    result = c1_lead_filter.run(
        lead_repo=FakeLeadRepo(upsert_result=4),
        log_repo=FakeLogRepo(),
        slack_notifier=FakeNotifier(),
        api_key="test-key",
        seed_sheet_id="sheet-id",
    )

    assert result["discovered"] == 6
    assert result["tier_a"] == 2
    assert result["tier_b"] == 1
    assert result["tier_b_potential"] == 2
    assert result["tier_c"] == 1
    assert result["upserted"] == 4


def test_c1_lead_has_correct_url_with_handle(monkeypatch) -> None:
    """handle 있는 채널 → @handle 형식 URL 생성."""
    discoveries = [_make_channel("ch-1", "A", handle="@drama_clips")]

    monkeypatch.setattr(c1_lead_filter, "load_seed_urls_from_sheet", lambda *_: [])
    monkeypatch.setattr(
        c1_lead_filter, "YouTubeShortsCrawler",
        lambda **_: FakeYTCrawler(discoveries),
    )

    lead_repo = FakeLeadRepo(upsert_result=1)
    c1_lead_filter.run(
        lead_repo=lead_repo,
        log_repo=FakeLogRepo(),
        slack_notifier=FakeNotifier(),
        api_key="test-key",
        seed_sheet_id="sheet-id",
    )

    lead = lead_repo.upserted[0]
    assert lead.channel_url == "https://www.youtube.com/@drama_clips"
    assert lead.channel_id == "ch-1"
    assert lead.platform == "youtube"


def test_c1_lead_uses_channel_id_url_when_no_handle(monkeypatch) -> None:
    """handle 없는 채널 → /channel/{id} 형식 URL 생성."""
    discoveries = [_make_channel("UC_test_123", "B", handle="")]

    monkeypatch.setattr(c1_lead_filter, "load_seed_urls_from_sheet", lambda *_: [])
    monkeypatch.setattr(
        c1_lead_filter, "YouTubeShortsCrawler",
        lambda **_: FakeYTCrawler(discoveries),
    )

    lead_repo = FakeLeadRepo(upsert_result=1)
    c1_lead_filter.run(
        lead_repo=lead_repo,
        log_repo=FakeLogRepo(),
        slack_notifier=FakeNotifier(),
        api_key="test-key",
        seed_sheet_id="sheet-id",
    )

    lead = lead_repo.upserted[0]
    assert lead.channel_url == "https://www.youtube.com/channel/UC_test_123"


def test_c1_returns_zero_upserted_when_no_qualifying_channels(monkeypatch) -> None:
    """C등급만 있을 때 upsert 0건, 리드 저장소 호출 없음."""
    discoveries = [
        _make_channel("c1", "C"),
        _make_channel("c2", "C"),
    ]

    monkeypatch.setattr(c1_lead_filter, "load_seed_urls_from_sheet", lambda *_: [])
    monkeypatch.setattr(
        c1_lead_filter, "YouTubeShortsCrawler",
        lambda **_: FakeYTCrawler(discoveries),
    )

    lead_repo = FakeLeadRepo(upsert_result=0)
    result = c1_lead_filter.run(
        lead_repo=lead_repo,
        log_repo=FakeLogRepo(),
        slack_notifier=FakeNotifier(),
        api_key="test-key",
        seed_sheet_id="sheet-id",
    )

    assert result["upserted"] == 0
    assert lead_repo.upserted == []


# ── 이메일 추출 단위 테스트 ────────────────────────────────────────────────────

@pytest.mark.parametrize("description,expected", [
    # 일반 비즈니스 이메일 포함
    ("비즈니스 문의: business@dramachannel.com", "business@dramachannel.com"),
    # 'Contact:' 형식
    ("Contact: hello@clips.co.kr\n구독해주세요!", "hello@clips.co.kr"),
    # YouTube 공식 도메인 제외 → None
    ("youtube.com/t/contact@youtube.com", None),
    # 설명 없음 → None
    ("", None),
    # 이메일 없는 설명 → None
    ("드라마 클립 모음 채널입니다. 구독 부탁드려요!", None),
    # 여러 이메일 중 첫 번째 반환
    ("문의: first@example.com 또는 second@example.com", "first@example.com"),
])
def test_extract_email_from_description(description: str, expected) -> None:
    """채널 설명에서 이메일 추출 — 다양한 포맷 검증."""
    assert _extract_email_from_description(description) == expected


def test_c1_lead_email_propagated_from_channel(monkeypatch) -> None:
    """ChannelDiscovery.email이 Lead.email로 올바르게 전달되는지 검증."""
    discoveries = [
        ChannelDiscovery(
            channel_id="ch-email",
            handle="@drama_with_email",
            name="이메일있는채널",
            subscriber_count=500_000,
            total_view_count=100_000_000,
            monthly_shorts_views=30_000_000,
            shorts_count_30d=50,
            tier="A",
            email="contact@dramachannel.kr",
        )
    ]

    monkeypatch.setattr(c1_lead_filter, "load_seed_urls_from_sheet", lambda *_: [])
    monkeypatch.setattr(
        c1_lead_filter, "YouTubeShortsCrawler",
        lambda **_: FakeYTCrawler(discoveries),
    )

    lead_repo = FakeLeadRepo(upsert_result=1)
    c1_lead_filter.run(
        lead_repo=lead_repo,
        log_repo=FakeLogRepo(),
        slack_notifier=FakeNotifier(),
        api_key="test-key",
        seed_sheet_id="sheet-id",
    )

    lead = lead_repo.upserted[0]
    assert lead.email == "contact@dramachannel.kr"


def test_c1_lead_email_none_when_no_email_in_channel(monkeypatch) -> None:
    """ChannelDiscovery.email=None이면 Lead.email도 None."""
    discoveries = [
        ChannelDiscovery(
            channel_id="ch-no-email",
            handle="@drama_no_email",
            name="이메일없는채널",
            subscriber_count=200_000,
            total_view_count=50_000_000,
            monthly_shorts_views=25_000_000,
            shorts_count_30d=30,
            tier="A",
            email=None,
        )
    ]

    monkeypatch.setattr(c1_lead_filter, "load_seed_urls_from_sheet", lambda *_: [])
    monkeypatch.setattr(
        c1_lead_filter, "YouTubeShortsCrawler",
        lambda **_: FakeYTCrawler(discoveries),
    )

    lead_repo = FakeLeadRepo(upsert_result=1)
    c1_lead_filter.run(
        lead_repo=lead_repo,
        log_repo=FakeLogRepo(),
        slack_notifier=FakeNotifier(),
        api_key="test-key",
        seed_sheet_id="sheet-id",
    )

    lead = lead_repo.upserted[0]
    assert lead.email is None
