# -*- coding: utf-8 -*-
"""C-1. 리드 발굴 자동화 핸들러 (YouTube Shorts 채널 탐색기).

트리거 종류:
  [monthly]  매월 1일 자동 실행 — 전체 채널 탐색 후 리드 시트 upsert
  [work_threshold]  신규 작품 등록 후 7일(2주) 이내 '작품사용신청'이 5개 이하일 시 자동 실행
                    → 리드 발굴 + 관리자 Slack 알림 발송

플로우:
1. 시드 채널 URL 목록을 Google Sheets에서 로드
   (시드 채널 시트: 18HY8-FdG_nAe-gOP7WNKiu5k7xMQliW9oxvKTcLC8Is, gid=1224056617)
2. YouTubeShortsCrawler 2-Layer 탐색 실행
   - Layer A: 채널명 키워드 직접 검색 (type=channel)
   - Layer B: 드라마·영화 제목 기반 Shorts 영상 검색 → 업로더 채널 수집
3. A/B/B?/C 등급으로 분류 (블록리스트 채널 자동 제외)
4. A/B/B? 등급 채널을 Lead 모델로 변환 → 리드 시트에 upsert
5. (work_threshold 트리거 시) Slack 알림 발송:
   {작품이름}의 이용 채널 수가 적어 리드발굴을 진행했습니다.
   리드발굴 {TIMESTAMP} 진행,
   {대표 TOP3 채널 이름}
   자세한 정보는 SHEET를 확인해주세요. [시트링크]
6. 결과 요약 반환

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

# Slack 알림 채널 — 환경변수 또는 기본값
import os as _os
_SLACK_NOTIFY_CHANNEL = _os.environ.get("SLACK_LEAD_NOTIFY_CHANNEL", _os.environ.get("SLACK_ERROR_CHANNEL", ""))


def _build_slack_notify_message(
    work_title: str,
    results: list,
    lead_sheet_url: str,
    timestamp: Optional[str] = None,
) -> str:
    """work_threshold 트리거 후 Slack 알림 메시지 생성.

    포맷:
        {작품이름}의 이용 채널 수가 적어 리드발굴을 진행했습니다.
        리드발굴 {TIMESTAMP} 진행,
        {대표 TOP3 채널 이름}
        자세한 정보는 SHEET를 확인해주세요. [시트링크]
    """
    if timestamp is None:
        timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    # A → B → B? 순으로 상위 3개 채널 선택
    tier_order = {"A": 0, "B": 1, "B?": 2, "C": 3}
    top3 = sorted(
        [r for r in results if r.tier in _MIN_TIER_TO_UPSERT],
        key=lambda r: (tier_order.get(r.tier, 9), -(r.monthly_shorts_views or 0)),
    )[:3]

    top3_names = "\n".join(
        f"  • {r.name} ({r.tier}등급, 월 {(r.monthly_shorts_views or 0):,}회)"
        for r in top3
    ) if top3 else "  • (발굴된 채널 없음)"

    return (
        f"*{work_title}*의 이용 채널 수가 적어 리드발굴을 진행했습니다.\n"
        f"리드발굴 {timestamp} 진행,\n"
        f"{top3_names}\n"
        f"자세한 정보는 SHEET를 확인해주세요. <{lead_sheet_url}|시트링크>"
    )


def run_for_work(
    work_title: str,
    lead_repo: ILeadRepository,
    log_repo: ILogRepository,
    slack_notifier: INotifier,
    api_key: str,
    seed_sheet_id: str,
    lead_sheet_url: str = "",
    seed_sheet_gid: str = "1224056617",
    max_channels: int = 200,
    seed_urls: list[str] | None = None,
) -> dict:
    """work_threshold 트리거 — 특정 작품의 채널 부족 시 리드 발굴 실행.

    Args:
        work_title:      작품명 (Slack 알림에 표시)
        lead_sheet_url:  리드 시트 URL (Slack 알림 링크)
        나머지:          run() 와 동일

    Returns:
        run() 결과 + slack_sent: bool
    """
    log.info("[C-1][work_threshold] 작품 '%s' — 채널 부족 리드발굴 시작", work_title)

    result = run(
        lead_repo=lead_repo,
        log_repo=log_repo,
        slack_notifier=slack_notifier,
        api_key=api_key,
        seed_sheet_id=seed_sheet_id,
        seed_sheet_gid=seed_sheet_gid,
        max_channels=max_channels,
        seed_urls=seed_urls,
    )

    # 발굴된 채널 목록은 lead_repo.upsert 전에 저장해 두기 어려우므로
    # run()의 summary 정보를 바탕으로 알림 생성
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    top_line = (
        f"  A등급 {result['tier_a']}개 · B등급 {result['tier_b']}개 · "
        f"B?등급 {result['tier_b_potential']}개 (총 upsert {result['upserted']}건)"
    )
    message = (
        f"*{work_title}*의 이용 채널 수가 적어 리드발굴을 진행했습니다.\n"
        f"리드발굴 {timestamp} 진행,\n"
        f"{top_line}\n"
        f"자세한 정보는 SHEET를 확인해주세요."
        + (f" <{lead_sheet_url}|시트링크>" if lead_sheet_url else "")
    )

    slack_sent = False
    try:
        channel = _SLACK_NOTIFY_CHANNEL
        if channel:
            slack_notifier.send(channel=channel, text=message)
            slack_sent = True
            log.info("[C-1][work_threshold] Slack 알림 발송 완료 → %s", channel)
        else:
            log.warning("[C-1][work_threshold] SLACK_LEAD_NOTIFY_CHANNEL 미설정 — Slack 알림 생략")
    except Exception as exc:  # noqa: BLE001
        log.error("[C-1][work_threshold] Slack 알림 발송 실패: %s", exc)

    result["trigger"] = "work_threshold"
    result["work_title"] = work_title
    result["slack_sent"] = slack_sent
    return result


def run(
    lead_repo: ILeadRepository,
    log_repo: ILogRepository,
    slack_notifier: INotifier,
    api_key: str,
    seed_sheet_id: str,
    seed_sheet_gid: str = "1224056617",
    max_channels: int = 200,
    seed_urls: list[str] | None = None,
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
    if seed_urls is None:
        log.info("[C-1] 시드 채널 목록 로드 중 (sheet=%s, gid=%s)", seed_sheet_id, seed_sheet_gid)
        seed_urls = load_seed_urls_from_sheet(seed_sheet_id, seed_sheet_gid)
    else:
        log.info("[C-1] Supabase seed_channel에서 받은 시드 채널 목록 사용")
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
        tier=r.tier,
        subscribers=r.subscriber_count,
        email=r.email,                  # 채널 설명에서 추출된 이메일 (없으면 None)
        email_sent_status=EmailSentStatus.NOT_SENT,
        discovered_at=now,
    )
