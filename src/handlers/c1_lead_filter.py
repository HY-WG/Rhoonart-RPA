# -*- coding: utf-8 -*-
"""C-1. 리드 발굴 자동화 핸들러 (YouTube Shorts 채널 탐색기).

플로우:
1. 시드 채널 URL 목록을 Google Sheets에서 로드
   (시드 채널 시트: 18HY8-FdG_nAe-gOP7WNKiu5k7xMQliW9oxvKTcLC8Is, gid=1224056617)
2. YouTubeShortsCrawler 2-Layer 탐색 실행
   - Layer A: 채널명 키워드 직접 검색 (type=channel)
   - Layer B: 드라마·영화 제목 기반 Shorts 영상 검색 → 업로더 채널 수집
3. A/B/B?/C 등급으로 분류 (블록리스트 채널 자동 제외)
4. A/B/B? 등급 채널을 Lead 모델로 변환 → 리드 시트에 upsert
5. 결과 요약 반환

등급 기준:
  A:  월간 숏츠 조회수 ≥ 2,000만
  B:  월간 숏츠 조회수 < 2,000만 AND 전월 대비 성장률 ≥ 10%
  B?: 첫 실행 시 성장률 없음 → 월 500만 이상이면 잠재 후보
  C:  기준 미달 (리드 목록에 추가하지 않음)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytz

from ..core.crawlers.youtube_shorts_crawler import (
    YouTubeShortsCrawler,
    ChannelDiscovery,
    load_seed_urls_from_sheet,
)
from ..core.interfaces.repository import ILeadRepository, ILogRepository
from ..core.interfaces.notifier import INotifier
from ..core.logger import CoreLogger
from ..models.lead import Lead, Genre, EmailSentStatus

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)

TASK_ID   = "C-1"
TASK_NAME = "리드 발굴 (YouTube Shorts 채널 탐색기)"

_MIN_TIER_TO_UPSERT = {"A", "B", "B?"}  # C등급은 리드 시트에 추가하지 않음


def run(
    lead_repo: ILeadRepository,
    log_repo: ILogRepository,
    slack_notifier: INotifier,
    api_key: str,
    seed_sheet_id: str,
    seed_sheet_gid: str = "1224056617",
    max_channels: int = 200,
) -> dict:
    """C-1 리드 발굴 실행.

    Args:
        lead_repo:       리드 upsert 저장소
        log_repo:        로그 기록 저장소
        slack_notifier:  에러 알림 클라이언트
        api_key:         YouTube Data API v3 키
        seed_sheet_id:   시드 채널 URL이 있는 Google Sheets ID
        seed_sheet_gid:  시드 채널 탭 GID (기본: 1224056617)
        max_channels:    최대 탐색 채널 수 (단위 절약)

    Returns:
        {
            "discovered": int,      # 전체 발굴 채널 수
            "tier_a": int,
            "tier_b": int,
            "tier_b_potential": int,
            "tier_c": int,
            "upserted": int,        # 리드 시트에 추가/갱신된 수
        }
    """
    log.info("[C-1] 시드 채널 목록 로드 중 (sheet=%s, gid=%s)", seed_sheet_id, seed_sheet_gid)
    seed_urls = load_seed_urls_from_sheet(seed_sheet_id, seed_sheet_gid)
    log.info("[C-1] 시드 채널 %d개 로드 완료", len(seed_urls))

    crawler = YouTubeShortsCrawler(
        api_key=api_key,
        seed_channel_urls=seed_urls,
        max_channels=max_channels,
    )
    results: list[ChannelDiscovery] = crawler.discover()

    # 등급별 분류
    tier_a  = [r for r in results if r.tier == "A"]
    tier_b  = [r for r in results if r.tier == "B"]
    tier_bp = [r for r in results if r.tier == "B?"]
    tier_c  = [r for r in results if r.tier == "C"]

    log.info(
        "[C-1] 탐색 완료 — 전체: %d  A: %d  B: %d  B?: %d  C: %d",
        len(results), len(tier_a), len(tier_b), len(tier_bp), len(tier_c),
    )

    # A/B/B? 등급만 리드 시트에 upsert
    to_upsert = [r for r in results if r.tier in _MIN_TIER_TO_UPSERT]
    leads     = [_to_lead(r) for r in to_upsert]
    upserted  = lead_repo.upsert_leads(leads) if leads else 0

    log.info("[C-1] 리드 upsert 완료 — %d건 (A+B+B?=%d)", upserted, len(leads))

    return {
        "discovered":        len(results),
        "tier_a":            len(tier_a),
        "tier_b":            len(tier_b),
        "tier_b_potential":  len(tier_bp),
        "tier_c":            len(tier_c),
        "upserted":          upserted,
    }


def _to_lead(r: ChannelDiscovery) -> Lead:
    """ChannelDiscovery → Lead 모델 변환."""
    now = datetime.now(KST)

    # 채널 URL 조합
    handle = r.handle.lstrip("@") if r.handle else r.channel_id
    channel_url = (
        f"https://www.youtube.com/@{handle}"
        if r.handle
        else f"https://www.youtube.com/channel/{r.channel_id}"
    )

    return Lead(
        channel_id=r.channel_id,
        channel_name=r.name,
        channel_url=channel_url,
        platform="youtube",
        genre=Genre.DRAMA_MOVIE,        # C-1은 드라마·영화 클립 채널만 수집
        monthly_shorts_views=r.monthly_shorts_views,
        subscribers=r.subscriber_count,
        email=r.email,                  # 채널 설명에서 추출된 이메일 (없으면 None)
        email_sent_status=EmailSentStatus.NOT_SENT,
        discovered_at=now,
    )
