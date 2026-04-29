"""네이버 클립 해시태그 페이지 크롤러 (B-2) - GraphQL 직접 호출 방식.

API 탐색 결과 (2026-04-23):
  - 엔드포인트: POST https://clip.naver.com/api/graphql
  - 인증 불필요: Content-Type: application/json 헤더만으로 200 응답
  - operation: ContentsQuery (cursor 기반 페이지네이션)
  - 클립 노드 주요 필드:
      count                    → 클립 누적 조회수
      interaction.like.count   → 좋아요 수
      interaction.comment.count→ 댓글 수
      user.profileId           → 크리에이터 채널 ID
      publishedTime            → 게시 시각 (ISO 8601, KST)
  - 해시태그 집계 통계 전용 API 없음 → 모든 클립을 순회하여 집계

성능 개선 (2026-04-28):
  - use_parallel=True 시 ThreadPoolExecutor로 해시태그 병렬 크롤링
  - on_progress 콜백으로 외부에서 진행 상황 추적 가능
  - 해시태그당 페이지 단위 진행 로그 추가
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import requests

from ...core.logger import CoreLogger

log = CoreLogger(__name__)

_GRAPHQL_URL = "https://clip.naver.com/api/graphql"
_HEADERS = {"Content-Type": "application/json"}
_PAGE_SIZE = 50       # 최대 허용 확인 필요, 기본 18보다 크게 시도
_MAX_CLIPS = 2000     # 해시태그당 최대 수집 클립 수 (루프 안전장치)
_REQ_DELAY = 0.3      # 요청 간 딜레이(초)

KST = timezone(timedelta(hours=9))

_CONTENTS_QUERY = """
query ContentsQuery(
  $input: ContentsInput!
  $first: Int
  $after: String
  $sessionId: String
  $reverse: Boolean = false
  $count: Int
  $sessionStartTime: Float
) {
  contents(
    input: $input
    first: $first
    after: $after
    sessionId: $sessionId
    reverse: $reverse
    count: $count
    sessionStartTime: $sessionStartTime
  ) {
    pageInfo {
      hasNextPage
      endCursor
      __typename
    }
    sessionId
    sessionStartTime
    __typename
    edges {
      cursor
      __typename
      node {
        __typename
        id
        mediaId
        mediaType
        title
        endUrl
        publishedTime
        count
        user {
          profileId
          nickname
          __typename
        }
        interaction {
          like   { count __typename }
          comment { count __typename }
          __typename
        }
      }
    }
  }
}
"""


@dataclass
class ClipStat:
    """클립 한 건의 통계."""
    media_id: str
    profile_id: str
    nickname: str
    title: str
    video_url: str
    published_time: Optional[datetime]
    views: int
    likes: int
    comments: int


@dataclass
class NaverClipHashtagStat:
    """해시태그 단위 집계 통계."""
    identifier: str           # 식별코드 (해시태그)
    content_name: str         # 콘텐츠명
    total_views: int          # 전체 클립 누적 조회수 합산
    clip_count: int           # 전체 클립 수
    weekly_views: int         # 최근 7일 게시 클립 조회수 합산
    new_clips_this_week: int  # 최근 7일 신규 클립 수
    total_likes: int          # 전체 좋아요 합산
    clips: list[ClipStat] = field(default_factory=list)  # 원본 클립 목록


class NaverClipCrawler:
    """네이버 클립 해시태그 GraphQL 크롤러.

    Playwright 없이 requests 직접 호출.
    ContentsQuery를 cursor 기반으로 페이지네이션하여 모든 클립을 수집한 뒤 집계한다.

    Args:
        contents: [(식별코드, 콘텐츠명), ...] 목록
        max_clips: 해시태그당 최대 수집 클립 수 (기본 2000)
        week_days: '주간' 기준 일수 (기본 7)
        use_parallel: True 시 ThreadPoolExecutor로 해시태그를 병렬 처리 (기본 False)
        max_workers: 병렬 처리 시 최대 동시 요청 수 (기본 4)
        on_progress: 해시태그 1개 완료 시 호출될 콜백 (completed: int, total: int) -> None
    """

    def __init__(
        self,
        contents: list[tuple[str, str]],
        max_clips: int = _MAX_CLIPS,
        week_days: int = 7,
        use_parallel: bool = False,
        max_workers: int = 4,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        self._contents = contents
        self._max_clips = max_clips
        self._week_cutoff = datetime.now(KST) - timedelta(days=week_days)
        self._use_parallel = use_parallel
        self._max_workers = max_workers
        self._on_progress = on_progress

    # ── public ────────────────────────────────────────────────────────────

    def crawl(self) -> list[dict]:
        """모든 식별코드를 순회하여 집계 통계를 반환한다."""
        return [
            self._stat_to_dict(stat, stat.identifier, stat.content_name)
            for stat in self.crawl_stats()
        ]

    def crawl_stats(self) -> list[NaverClipHashtagStat]:
        """모든 식별코드를 순회하여 해시태그별 원본/집계 통계를 반환한다."""
        total = len(self._contents)
        log.info("[NaverClipCrawler] 크롤링 시작 - 대상 %d개 해시태그 (병렬=%s)", total, self._use_parallel)

        if self._use_parallel and total > 1:
            return self._crawl_parallel_stats(total)
        return self._crawl_sequential_stats(total)

    def _crawl_sequential_stats(self, total: int) -> list[NaverClipHashtagStat]:
        """해시태그 순차 크롤링."""
        results: list[NaverClipHashtagStat] = []
        for idx, (identifier, content_name) in enumerate(self._contents, 1):
            log.info("[B-2] (%d/%d) '%s' 크롤링 시작...", idx, total, content_name)
            stat = self._crawl_hashtag(identifier, content_name)
            if stat:
                results.append(stat)
                log.info(
                    "[B-2] (%d/%d) '%s' 완료 - %d클립 / 누적조회 %d / 주간조회 %d",
                    idx, total, content_name,
                    stat.clip_count, stat.total_views, stat.weekly_views,
                )
            if self._on_progress:
                try:
                    self._on_progress(idx, total)
                except Exception:
                    pass
        return results

    def _crawl_parallel_stats(self, total: int) -> list[NaverClipHashtagStat]:
        """해시태그 병렬 크롤링 (ThreadPoolExecutor)."""
        workers = min(self._max_workers, total)
        log.info("[NaverClipCrawler] 병렬 크롤링 시작 - workers=%d", workers)

        results_map: dict[str, NaverClipHashtagStat] = {}
        completed = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_item = {
                executor.submit(self._crawl_hashtag, identifier, content_name): (identifier, content_name)
                for identifier, content_name in self._contents
            }
            for future in as_completed(future_to_item):
                identifier, content_name = future_to_item[future]
                completed += 1
                try:
                    stat = future.result()
                    if stat:
                        results_map[identifier] = stat
                        log.info(
                            "[B-2] (%d/%d) '%s' 완료 - %d클립 / 누적조회 %d / 주간조회 %d",
                            completed, total, content_name,
                            stat.clip_count, stat.total_views, stat.weekly_views,
                        )
                except Exception as e:
                    log.error("[B-2] (%d/%d) '%s' 크롤링 실패: %s", completed, total, content_name, e)

                if self._on_progress:
                    try:
                        self._on_progress(completed, total)
                    except Exception:
                        pass

        # 원래 순서 유지
        return [results_map[idf] for idf, _ in self._contents if idf in results_map]

    @staticmethod
    def _stat_to_dict(stat: "NaverClipHashtagStat", identifier: str, content_name: str) -> dict:
        return {
            "channel_id":    identifier,
            "channel_name":  content_name,
            "platform":      "naver_clip",
            "total_views":   stat.total_views,
            "weekly_views":  stat.weekly_views,
            "video_count":   stat.clip_count,
            "new_clips_week": stat.new_clips_this_week,
            "total_likes":   stat.total_likes,
        }

    # ── internal ──────────────────────────────────────────────────────────

    def _crawl_hashtag(
        self, identifier: str, content_name: str
    ) -> Optional[NaverClipHashtagStat]:
        """단일 해시태그 전체 클립 수집 및 집계."""
        clips: list[ClipStat] = []
        cursor: Optional[str] = None
        session_id: Optional[str] = None
        session_start_time: Optional[float] = None
        page_num = 0

        while len(clips) < self._max_clips:
            page_num += 1
            try:
                resp_data = self._fetch_page(
                    identifier, cursor, session_id, session_start_time
                )
            except Exception as e:
                log.error("[%s] 페이지 %d 요청 실패: %s", identifier, page_num, e)
                break

            contents = resp_data.get("data", {}).get("contents", {})
            # 세션 정보 유지 (페이지네이션 연속성)
            if session_id is None:
                session_id = contents.get("sessionId")
                session_start_time = contents.get("sessionStartTime")

            edges = contents.get("edges") or []
            before = len(clips)
            for edge in edges:
                node = edge.get("node") or {}
                clip = self._parse_node(node)
                if clip:
                    clips.append(clip)
            after = len(clips)

            # 페이지 단위 진행 로그 (5페이지마다 or 첫 페이지)
            if page_num == 1 or page_num % 5 == 0:
                log.info(
                    "[%s] 페이지 %d 완료 - 이번 페이지 %d건 / 누적 %d클립",
                    identifier, page_num, after - before, after,
                )

            page_info = contents.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                log.info("[%s] 마지막 페이지 도달 (페이지 %d, 총 %d클립)", identifier, page_num, len(clips))
                break
            cursor = page_info.get("endCursor")
            if not cursor:
                break

            time.sleep(_REQ_DELAY)

        if not clips:
            log.warning("[%s] %s - 수집된 클립 없음", identifier, content_name)
            return None

        return self._aggregate(identifier, content_name, clips)

    def _fetch_page(
        self,
        identifier: str,
        after: Optional[str],
        session_id: Optional[str],
        session_start_time: Optional[float],
    ) -> dict:
        """ContentsQuery 한 페이지 요청."""
        variables: dict = {
            "reverse": False,
            "input": {
                "recType": "AIRS",
                "airsArea": f"hashtag.{identifier}",
                "panelType": "page_tag",
            },
            "first": _PAGE_SIZE,
        }
        if after:
            variables["after"] = after
        if session_id:
            variables["sessionId"] = session_id
        if session_start_time is not None:
            variables["sessionStartTime"] = session_start_time

        payload = {
            "operationName": "ContentsQuery",
            "variables": variables,
            "extensions": {
                "clientLibrary": {"name": "@apollo/client", "version": "4.1.6"}
            },
            "query": _CONTENTS_QUERY,
        }

        resp = requests.post(
            _GRAPHQL_URL,
            json=payload,
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {data['errors']}")
        return data

    def _parse_node(self, node: dict) -> Optional[ClipStat]:
        """GraphQL 노드 → ClipStat 변환."""
        try:
            media_id = node.get("mediaId") or node.get("id", "")
            user = node.get("user") or {}
            interaction = node.get("interaction") or {}
            like = interaction.get("like") or {}
            comment = interaction.get("comment") or {}

            # publishedTime: "2025-12-15T19:04:50.000+0900"
            pub_str = node.get("publishedTime")
            published_time: Optional[datetime] = None
            if pub_str:
                try:
                    published_time = datetime.fromisoformat(pub_str)
                except Exception:
                    pass

            return ClipStat(
                media_id=media_id,
                profile_id=user.get("profileId", ""),
                nickname=user.get("nickname", ""),
                title=str(node.get("title") or "").strip(),
                video_url=str(node.get("endUrl") or "").strip(),
                published_time=published_time,
                views=int(node.get("count") or 0),
                likes=int(like.get("count") or 0),
                comments=int(comment.get("count") or 0),
            )
        except Exception as e:
            log.debug("노드 파싱 오류 (건너뜀): %s", e)
            return None

    def _aggregate(
        self, identifier: str, content_name: str, clips: list[ClipStat]
    ) -> NaverClipHashtagStat:
        """클립 목록 → 해시태그 집계 통계."""
        total_views = sum(c.views for c in clips)
        total_likes = sum(c.likes for c in clips)
        clip_count = len(clips)

        weekly_clips = [
            c for c in clips
            if c.published_time and c.published_time >= self._week_cutoff
        ]
        weekly_views = sum(c.views for c in weekly_clips)
        new_clips_this_week = len(weekly_clips)

        return NaverClipHashtagStat(
            identifier=identifier,
            content_name=content_name,
            total_views=total_views,
            clip_count=clip_count,
            weekly_views=weekly_views,
            new_clips_this_week=new_clips_this_week,
            total_likes=total_likes,
            clips=clips,
        )
