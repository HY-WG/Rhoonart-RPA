"""YouTube Shorts 신규 채널 발굴 및 분류 크롤러 (C-1 대체).

목적: 기존 시드 채널을 기반으로 유사 신규 채널을 탐색하고 A/B 등급으로 분류.
     - 기존 시드 채널 관리 기능 없음 (읽기 전용)

탐색 전략 (2-Layer):

  ┌─ Layer A. 채널명 키워드 직접 검색 ─────────────────────────────────────┐
  │  "드라마 클립", "영화 명장면" 등 클립 채널 고유 키워드로                 │
  │  YouTube 채널 검색 (type=channel) → 클립 채널 직접 발굴                 │
  │                                                                         │
  │  · 탐색 공간: _CHANNEL_SEARCH_KEYWORDS 개수 고정 (시드 수와 무관)        │
  │  · 비용: 100유닛 × 키워드 수 (기본 7개 = 700유닛)                        │
  │  · 특징: YouTube topicId API가 Shorts에서 0 반환하는 현 상황의 대안      │
  └────────────────────────────────────────────────────────────────────────┘

  ┌─ Layer B. 드라마·영화 제목 기반 키워드 탐색 ────────────────────────────┐
  │  한국 드라마·영화 제목으로 Shorts 영상 검색 → 채널 역추출                │
  │                                                                         │
  │  제목 수집 기준 (scripts/drama_titles.json):                            │
  │    1) manual_titles  : 담당자가 직접 입력·관리 (항상 최우선)             │
  │    2) auto_titles    : 드라마 클립 영상에서 자동 추출 (7일 캐시)         │
  │                        추출 방식:                                        │
  │                          a) 영상 제목의 한국어 hashtag (#드라마명)        │
  │                          b) 에피소드 마커 앞 제목 (N화, EP N)            │
  │                        검색어: "드라마 명장면", "한국 드라마 클립"        │
  │                                                                         │
  │  검색 제한 조건:                                                         │
  │    · publishedAfter  : 최근 6개월 이내 게시된 Shorts만 검색              │
  │    · order=viewCount : 조회수 높은 영상 우선 (인기 클립 채널 포착)        │
  │    · 검색 쿼리 조합  : "{제목} 명장면", "{제목} 클립" (각 100유닛)        │
  │    · 최대 제목 수    : _MAX_DRAMA_TITLES (기본 20개)                     │
  │                                                                         │
  │  · 탐색 공간: 제목 수 × 2 쿼리 (드라마 목록이 늘수록 확장)               │
  │  · 비용: 200유닛 × 제목 수                                              │
  └────────────────────────────────────────────────────────────────────────┘

분류 기준:
  A등급: 월간 숏츠 조회수 ≥ 2,000만
  B등급: 월간 숏츠 조회수 < 2,000만 + 전월 대비 채널 성장률 ≥ 10%
  (성장률: channels.list statistics.viewCount 전월 스냅샷 대비)

YouTube Data API 쿼터 소모 추정 (채널 200개, 제목 10개 기준):
  Layer A  search.list (채널명 키워드 7개)       700 유닛
  Layer B  search.list (제목 10개 × 2 쿼리)   2,000 유닛
  Layer B  자동 제목 추출 search (7일 캐시)       200 유닛/7일
  channels.list (발굴 채널 통계)                  ~4 유닛
  playlistItems.list (영상 목록)                ~200 유닛
  videos.list (Shorts 판별+조회수)              ~200 유닛
  시드 handle → ID 변환                           ~20 유닛
  ────────────────────────────────────────────────────────
  합계 약 3,124 유닛 / 10,000 일일 한도 (제목 10개 기준)
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

import requests

from ...core.logger import CoreLogger
from ...core.utils.datetime_utils import parse_iso_datetime
from ._drama_title import (
    extract_drama_name_from_hashtag as _extract_drama_name_from_hashtag,
    extract_drama_name_with_episode as _extract_drama_name_with_episode,
    load_drama_titles_file as _load_drama_titles_file,
    save_drama_titles_file as _save_drama_titles_file,
    update_manual_drama_titles,       # 공개 함수 — 이름 유지
    MAX_DRAMA_TITLES      as _MAX_DRAMA_TITLES,
    TITLE_SEARCH_MONTHS   as _TITLE_SEARCH_MONTHS,
    TITLE_CACHE_DAYS      as _TITLE_CACHE_DAYS,
    TITLE_SEARCH_SUFFIXES as _TITLE_SEARCH_SUFFIXES,
    AUTO_TITLE_SEED_QUERIES as _AUTO_TITLE_SEED_QUERIES,
)
from ._blocklist import (
    load_blocklist   as _load_blocklist,
    block_channels,                   # 공개 함수 — 이름 유지
    unblock_channels,                 # 공개 함수 — 이름 유지
)
from ._yt_utils import (
    chunks                          as _chunks,
    parse_iso8601_duration          as _parse_duration,
    extract_channel_ids_from_search as _extract_channel_ids,
    extract_email_from_description  as _extract_email_from_description,
    load_seed_urls_from_sheet,        # 공개 함수 — 이름 유지
)

log = CoreLogger(__name__)

# ── 상수 ──────────────────────────────────────────────────────────────────
_YT_API_BASE = "https://www.googleapis.com/youtube/v3"
_REQ_DELAY   = 0.2
_MAX_CHANNELS = 200
_MONTHLY_VIEWS_THRESHOLD = 20_000_000
_GROWTH_RATE_THRESHOLD   = 0.10

# ── Layer A: 채널명 키워드 직접 검색 ──────────────────────────────────────
# type=channel로 채널 이름을 직접 검색 — topicId API가 Shorts에서 0 반환하는
# 현 상황의 실질적 대안. 클립 채널 고유 명칭으로 구성.
_CHANNEL_SEARCH_KEYWORDS = [
    "드라마 클립",           # 한국어 핵심
    "드라마 명장면",
    "영화 명장면",
    "영화 클립",
    "드라마 하이라이트",
    "drama clip shorts",    # 영문 검색 (해외 거주 창작자 포착)
    "한국드라마 클립",
]

# ── 클립 채널 식별 키워드 필터 ─────────────────────────────────────────────
_CLIP_CHANNEL_INCLUDE = {
    "무비", "movie", "극장", "drama", "드라마", "영화", "film", "씨네",
    "시네", "cinema", "클립", "clip", "컷", "cut", "짤", "하이라이트",
    "highlight", "명장면",
}
_CLIP_CHANNEL_EXCLUDE = {
    "게임", "gaming", "먹방", "mukbang", "뷰티", "beauty", "travel", "여행",
    "스포츠", "sports", "kpop", "k-pop", "아이돌", "idol", "뮤직", "music",
    "댄스", "dance", "리뷰", "review", "브이로그", "vlog",
}

# 채널명에 방송사명이 포함된 공식 채널 제외 (권리 보유자 = 계약 대상 아님)
_BROADCASTER_EXCLUDE = {
    "tvn", "jtbc", "sbs", "kbs", "mbc", "ocn", "채널a", "channel a",
    "ebs", "sky drama", "sky sports", "mnet", "olive", "온스타일",
    "스튜디오드래곤",
}

# YouTube topicId — Freebase MID (채널 topicId 조회에만 사용, 탐색에는 미사용)
_TARGET_TOPIC_IDS = {
    "/m/02jjt",   # Entertainment
    "/m/0f2f9",   # Television program
    "/m/02vxn",   # Film
}
_EXCLUDE_TOPIC_IDS = {"/m/01z_f6", "/m/04rlf"}  # K-pop, Music 제외

KST = timezone(timedelta(hours=9))
_HISTORY_PATH = Path("scripts/yt_shorts_history.json")


# ── 데이터 클래스 ─────────────────────────────────────────────────────────

@dataclass
class ChannelDiscovery:
    """발굴된 채널 단위 데이터."""
    channel_id:   str
    handle:       str
    name:         str
    subscriber_count:   int
    total_view_count:   int
    monthly_shorts_views: int
    shorts_count_30d:   int
    topic_ids:    list[str] = field(default_factory=list)
    discovery_source: str = ""
    tier:         str = ""
    growth_rate:  Optional[float] = None
    email:        Optional[str] = None   # 채널 설명에서 추출한 비즈니스 이메일
    crawled_at:   str = field(
        default_factory=lambda: datetime.now(KST).isoformat()
    )


# ── 메인 크롤러 ───────────────────────────────────────────────────────────

class YouTubeShortsCrawler:
    """기존 시드 채널 기반 신규 채널 발굴·분류기."""

    def __init__(
        self,
        api_key: str,
        seed_channel_urls: list[str],
        max_channels: int = _MAX_CHANNELS,
        monthly_threshold: int = _MONTHLY_VIEWS_THRESHOLD,
        growth_threshold: float = _GROWTH_RATE_THRESHOLD,
    ) -> None:
        self._key = api_key
        self._seed_urls = seed_channel_urls
        self._max_ch = max_channels
        self._monthly_thr = monthly_threshold
        self._growth_thr = growth_threshold
        self._quota_used = 0
        self._blocklist: set[str] = _load_blocklist()

    # ── public ────────────────────────────────────────────────────────────

    def discover(self) -> list[ChannelDiscovery]:
        """신규 채널 발굴 → 통계 수집 → 분류."""
        log.info("=== YouTube Shorts 신규 채널 발굴 시작 ===")

        seed_ids = self._resolve_seed_channel_ids()
        log.info("시드 채널 %d개 확인", len(seed_ids))

        candidate_ids: set[str] = set()

        # ── Layer A: 채널명 키워드 직접 검색 ─────────────────────────────
        log.info("[Layer A] 채널명 키워드 직접 검색")
        for keyword in _CHANNEL_SEARCH_KEYWORDS:
            if len(candidate_ids) >= self._max_ch:
                break
            ids = self._search_channels_by_name(keyword)
            before = len(candidate_ids)
            candidate_ids.update(ids)
            log.info("  채널검색 '%s' → +%d채널 (누계 %d)", keyword, len(candidate_ids) - before, len(candidate_ids))
        log.info("[Layer A] 완료 — %d개 후보", len(candidate_ids))

        # ── Layer B: 드라마·영화 제목 기반 키워드 탐색 ────────────────────
        if len(candidate_ids) < self._max_ch:
            log.info("[Layer B] 드라마·영화 제목 기반 탐색")
            drama_titles = self._get_drama_titles()
            published_after = (
                datetime.now(timezone.utc) - timedelta(days=_TITLE_SEARCH_MONTHS * 30)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            log.info("  사용 제목 %d개 / publishedAfter=%s", len(drama_titles), published_after)
            for title in drama_titles:
                if len(candidate_ids) >= self._max_ch:
                    break
                for suffix in _TITLE_SEARCH_SUFFIXES:
                    query = f"{title} {suffix}"
                    ids = self._search_channels_by_shorts_video(
                        query, "KR", published_after=published_after
                    )
                    before = len(candidate_ids)
                    candidate_ids.update(ids)
                    log.info("  '%s' → +%d채널 (누계 %d)", query, len(candidate_ids) - before, len(candidate_ids))
                    if len(candidate_ids) >= self._max_ch:
                        break
            log.info("[Layer B] 완료 — %d개 후보", len(candidate_ids))

        # 시드 + 블록리스트 제외
        candidate_ids -= set(seed_ids)
        blocked_removed = len(candidate_ids & self._blocklist)
        candidate_ids -= self._blocklist
        if blocked_removed:
            log.info("블록리스트 제외 %d개", blocked_removed)
        candidate_ids = set(list(candidate_ids)[: self._max_ch])
        log.info("후보 채널 %d개 (시드·블록리스트 제외 후)", len(candidate_ids))

        # 채널 통계 수집
        discoveries = self._collect_channel_stats(list(candidate_ids))

        # 성장률 계산
        history = self._load_history()
        for ch in discoveries:
            prev = history.get(ch.channel_id)
            if prev and prev.get("total_view_count"):
                delta = ch.total_view_count - prev["total_view_count"]
                ch.growth_rate = delta / prev["total_view_count"] if prev["total_view_count"] else None

        # 등급 분류
        for ch in discoveries:
            ch.tier = self._classify(ch)

        self._save_history(discoveries)

        a_cnt = sum(1 for c in discoveries if c.tier == "A")
        b_cnt = sum(1 for c in discoveries if c.tier == "B")
        log.info(
            "발굴 완료 — A등급: %d, B등급: %d, C등급: %d / 쿼터 사용: %d유닛",
            a_cnt, b_cnt, len(discoveries) - a_cnt - b_cnt, self._quota_used,
        )
        return discoveries

    # ── 시드 채널 ID 확보 ────────────────────────────────────────────────

    def _resolve_seed_channel_ids(self) -> list[str]:
        ids: list[str] = []
        handles: list[str] = []
        for url in self._seed_urls:
            url = unquote(url).rstrip("/")
            m = re.search(r"/channel/(UC[\w-]+)", url)
            if m:
                ids.append(m.group(1))
                continue
            m = re.search(r"/@([^/?\s]+)", url)
            if m:
                handles.append(m.group(1).replace("/shorts", ""))
                continue
            m = re.search(r"/c/([^/?\s]+)", url)
            if m:
                handles.append(m.group(1).replace("/shorts", ""))
        for handle in handles:
            cid = self._handle_to_channel_id(handle)
            if cid:
                ids.append(cid)
        return list(dict.fromkeys(ids))

    def _handle_to_channel_id(self, handle: str) -> Optional[str]:
        data = self._yt_get("channels", {
            "part": "id",
            "forHandle": f"@{handle}" if not handle.startswith("@") else handle,
            "maxResults": 1,
        }, cost=1)
        items = data.get("items", [])
        return items[0]["id"] if items else None

    # ── Layer A: 채널명 키워드 직접 검색 ─────────────────────────────────

    def _search_channels_by_name(self, keyword: str) -> list[str]:
        """채널 이름 키워드 검색 → channel_id 목록 (100유닛).

        type=channel을 사용하여 채널 이름·설명에서 직접 검색.
        topicId API가 Shorts 영역에서 0 반환하는 현 상황의 실질적 대안.
        """
        data = self._yt_get("search", {
            "part": "snippet",
            "type": "channel",
            "q": keyword,
            "regionCode": "KR",
            "relevanceLanguage": "ko",
            "maxResults": 50,
            "order": "relevance",
        }, cost=100)
        seen: set[str] = set()
        result: list[str] = []
        for item in data.get("items", []):
            # type=channel 결과는 id.channelId 또는 snippet.channelId
            cid = (
                item.get("id", {}).get("channelId")
                or item.get("snippet", {}).get("channelId", "")
            )
            if cid and cid not in seen:
                seen.add(cid)
                result.append(cid)
        return result

    # ── Layer B: 드라마·영화 제목 기반 채널 탐색 ─────────────────────────

    def _get_drama_titles(self) -> list[str]:
        """검색에 사용할 한국 드라마·영화 제목 목록 반환.

        우선순위:
          1. drama_titles.json의 manual_titles (담당자 직접 입력, 항상 포함)
          2. drama_titles.json의 auto_titles (캐시 유효 시 재사용)
          3. 드라마 클립 영상에서 자동 추출 후 캐시 갱신
             - 영상 제목의 한국어 hashtag (#마지막썸머, #탁류)
             - 에피소드 마커 앞 드라마명 (N화, EP N)
        """
        data = _load_drama_titles_file()
        manual_titles: list[str] = data.get("manual_titles", [])

        cached_auto: list[str] = data.get("auto_titles", [])
        updated_at_str: str = data.get("updated_at", "")
        cache_valid = False
        if updated_at_str and cached_auto:
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                if (datetime.now(KST) - updated_at).days < _TITLE_CACHE_DAYS:
                    cache_valid = True
            except Exception:
                pass

        if cache_valid:
            auto_titles = cached_auto
            log.info("  [Layer B] 드라마 제목 캐시 사용 (%d개, 갱신: %s)",
                     len(auto_titles), updated_at_str[:10])
        else:
            log.info("  [Layer B] 드라마 클립 영상에서 제목 자동 추출 중...")
            auto_titles = self._extract_drama_titles_from_clip_search()
            _save_drama_titles_file(manual_titles=manual_titles, auto_titles=auto_titles)
            log.info("  [Layer B] 자동 추출 완료 — %d개 제목", len(auto_titles))

        seen: set[str] = set()
        result: list[str] = []
        for t in manual_titles + auto_titles:
            if t and t not in seen:
                seen.add(t)
                result.append(t)
            if len(result) >= _MAX_DRAMA_TITLES:
                break
        return result

    def _extract_drama_titles_from_clip_search(self) -> list[str]:
        """드라마 클립 영상 검색 결과에서 드라마·영화명 추출.

        두 단계:
          1) "_AUTO_TITLE_SEED_QUERIES" 검색 → 최근 6개월 인기 드라마 클립 영상
          2) 각 영상 제목에서 hashtag(#드라마명) 또는 에피소드 마커 기반 제목 추출

        비용: 100유닛 × len(_AUTO_TITLE_SEED_QUERIES) / 7일 캐시
        """
        published_after = (
            datetime.now(timezone.utc) - timedelta(days=_TITLE_SEARCH_MONTHS * 30)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        titles: list[str] = []
        seen: set[str] = set()

        for query in _AUTO_TITLE_SEED_QUERIES:
            data = self._yt_get("search", {
                "part": "snippet",
                "type": "video",
                "videoDuration": "short",
                "q": query,
                "regionCode": "KR",
                "relevanceLanguage": "ko",
                "maxResults": 50,
                "order": "viewCount",
                "publishedAfter": published_after,
            }, cost=100)
            for item in data.get("items", []):
                raw_title = item.get("snippet", {}).get("title", "")
                # 방법 1: hashtag 추출 (가장 정확)
                t = _extract_drama_name_from_hashtag(raw_title)
                # 방법 2: 에피소드 마커 기반 추출 (fallback)
                if not t:
                    t = _extract_drama_name_with_episode(raw_title)
                if t and t not in seen:
                    seen.add(t)
                    titles.append(t)

        return titles

    def _search_channels_by_shorts_video(
        self,
        keyword: str,
        region: str,
        order: str = "viewCount",
        published_after: str = "",
    ) -> list[str]:
        """Shorts 영상 키워드 검색 → 채널 ID 역추출 (100유닛)."""
        params: dict = {
            "part": "snippet",
            "type": "video",
            "videoDuration": "short",
            "q": keyword,
            "regionCode": region,
            "relevanceLanguage": "ko",
            "maxResults": 50,
            "order": order,
        }
        if published_after:
            params["publishedAfter"] = published_after
        data = self._yt_get("search", params, cost=100)
        return _extract_channel_ids(data)

    # ── 클립 채널 분류 필터 ───────────────────────────────────────────────

    def _is_drama_clip_channel(self, name: str, description: str) -> bool:
        name_lower = name.lower()
        desc_lower = description.lower()
        if any(kw in name_lower for kw in _BROADCASTER_EXCLUDE):
            return False
        if any(kw in name_lower for kw in _CLIP_CHANNEL_EXCLUDE):
            return False
        if any(kw in name_lower for kw in _CLIP_CHANNEL_INCLUDE):
            return True
        _DESC_KEYWORDS = {
            "tvn", "jtbc", "kbs", "mbc", "sbs", "ocn", "채널a",
            "넷플릭스", "netflix", "왓챠", "watcha", "웨이브", "wavve", "티빙", "tving",
            "클립", "명장면", "하이라이트", "highlight", "clip",
        }
        if any(kw in desc_lower for kw in _DESC_KEYWORDS):
            return True
        return False

    # ── 채널 통계 + 월간 숏츠 조회수 ─────────────────────────────────────

    def _collect_channel_stats(self, channel_ids: list[str]) -> list[ChannelDiscovery]:
        discoveries: list[ChannelDiscovery] = []
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        for batch in _chunks(channel_ids, 50):
            data = self._yt_get("channels", {
                "part": "id,snippet,statistics,contentDetails,topicDetails",
                "id": ",".join(batch),
                "maxResults": 50,
            }, cost=1)
            returned = len(data.get("items", []))
            log.info("  channels.list 요청 %d개 → 반환 %d개", len(batch), returned)

            for item in data.get("items", []):
                cid = item["id"]
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                content_details = item.get("contentDetails", {})
                topic_details = item.get("topicDetails", {})

                topic_ids = topic_details.get("topicIds", [])
                name = snippet.get("title", "")
                description = snippet.get("description", "")

                if not self._is_drama_clip_channel(name, description):
                    log.debug("  [필터제외] %s", name)
                    continue

                is_music_only = (
                    topic_ids and all(t in _EXCLUDE_TOPIC_IDS for t in topic_ids)
                )
                if is_music_only:
                    continue

                uploads_playlist = (
                    content_details.get("relatedPlaylists", {}).get("uploads", "")
                )
                monthly_views, shorts_count = self._calc_monthly_shorts(
                    uploads_playlist, thirty_days_ago
                )

                sub_count = int(stats.get("subscriberCount") or 0)
                view_count = int(stats.get("viewCount") or 0)

                if sub_count < 100:
                    continue

                # 채널 설명에서 이메일 추출 (추가 API 호출 없이 description 재활용)
                email = _extract_email_from_description(description)

                discoveries.append(ChannelDiscovery(
                    channel_id=cid,
                    handle=snippet.get("customUrl", ""),
                    name=snippet.get("title", ""),
                    subscriber_count=sub_count,
                    total_view_count=view_count,
                    monthly_shorts_views=monthly_views,
                    shorts_count_30d=shorts_count,
                    topic_ids=topic_ids,
                    discovery_source="multi-layer-search",
                    email=email,
                ))

        return discoveries

    def _calc_monthly_shorts(
        self, uploads_playlist: str, cutoff: datetime
    ) -> tuple[int, int]:
        if not uploads_playlist:
            return 0, 0
        items_data = self._yt_get("playlistItems", {
            "part": "contentDetails",
            "playlistId": uploads_playlist,
            "maxResults": 50,
        }, cost=1)
        recent_ids = []
        for item in items_data.get("items", []):
            pub_str = item["contentDetails"].get("videoPublishedAt", "")
            if not pub_str:
                continue
            pub_dt = parse_iso_datetime(pub_str)
            if pub_dt is None:
                continue
            if pub_dt >= cutoff:
                recent_ids.append(item["contentDetails"]["videoId"])
        if not recent_ids:
            return 0, 0
        total_views = 0
        shorts_count = 0
        for batch in _chunks(recent_ids, 50):
            vdata = self._yt_get("videos", {
                "part": "statistics,contentDetails",
                "id": ",".join(batch),
            }, cost=1)
            for v in vdata.get("items", []):
                dur = v.get("contentDetails", {}).get("duration", "")
                secs = _parse_duration(dur)
                if secs <= 60:
                    shorts_count += 1
                    total_views += int(
                        v.get("statistics", {}).get("viewCount") or 0
                    )
        return total_views, shorts_count

    # ── 이메일 보강 (post-hoc) ────────────────────────────────────────────

    def enrich_with_email(self, discoveries: list[ChannelDiscovery]) -> int:
        """이미 발굴된 채널에 이메일 정보를 보강한다 (이메일 없는 채널만 처리).

        channels.list(part=snippet)를 50개 배치로 호출해 description을 가져와
        이메일을 추출한다.  _collect_channel_stats 단계에서 이미 이메일을 설정했으므로
        통상적으로는 호출할 필요 없으나, 기존 발굴 결과를 재처리할 때 유용하다.

        Args:
            discoveries: 보강 대상 ChannelDiscovery 목록

        Returns:
            이메일이 새로 설정된 채널 수
        """
        # 이메일 없는 것만 처리
        targets = [ch for ch in discoveries if ch.email is None]
        if not targets:
            return 0

        id_to_ch: dict[str, ChannelDiscovery] = {ch.channel_id: ch for ch in targets}
        enriched = 0

        for batch in _chunks(list(id_to_ch.keys()), 50):
            data = self._yt_get("channels", {
                "part": "snippet",
                "id": ",".join(batch),
                "maxResults": 50,
            }, cost=1)
            for item in data.get("items", []):
                cid = item["id"]
                desc = item.get("snippet", {}).get("description", "")
                email = _extract_email_from_description(desc)
                if email and cid in id_to_ch:
                    id_to_ch[cid].email = email
                    enriched += 1

        log.info("[C-1] 이메일 보강 완료 — %d/%d채널 이메일 확보", enriched, len(targets))
        return enriched

    # ── 등급 분류 ─────────────────────────────────────────────────────────

    def _classify(self, ch: ChannelDiscovery) -> str:
        if ch.monthly_shorts_views >= self._monthly_thr:
            return "A"
        if ch.growth_rate is not None and ch.growth_rate >= self._growth_thr:
            return "B"
        if ch.growth_rate is None and ch.monthly_shorts_views >= 5_000_000:
            return "B?"
        return "C"

    # ── 히스토리 ──────────────────────────────────────────────────────────

    def _load_history(self) -> dict[str, dict]:
        if _HISTORY_PATH.exists():
            with open(_HISTORY_PATH, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_history(self, discoveries: list[ChannelDiscovery]) -> None:
        history = self._load_history()
        for ch in discoveries:
            history[ch.channel_id] = {
                "total_view_count": ch.total_view_count,
                "saved_at": datetime.now(KST).isoformat(),
            }
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    # ── 블록리스트 (읽기 전용 접근) ──────────────────────────────────────────

    def get_blocklist(self) -> set[str]:
        """현재 블록리스트 channel_id 집합 반환 (읽기 전용)."""
        return _load_blocklist()

    # ── YouTube API 공통 호출 ─────────────────────────────────────────────

    def _yt_get(self, endpoint: str, params: dict, cost: int = 1) -> dict:
        params["key"] = self._key
        url = f"{_YT_API_BASE}/{endpoint}"
        time.sleep(_REQ_DELAY)
        resp = requests.get(url, params=params, timeout=15)
        self._quota_used += cost
        if resp.status_code != 200:
            log.warning("[%s] status=%d body=%s", endpoint, resp.status_code, resp.text[:200])
            return {}
        return resp.json()


