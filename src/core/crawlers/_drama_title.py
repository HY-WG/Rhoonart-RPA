# -*- coding: utf-8 -*-
"""드라마·영화 제목 추출 및 관리 유틸리티 (C-1 내부 모듈).

이 모듈은 youtube_shorts_crawler.py 에서만 임포트합니다.
외부에서 직접 임포트하지 마세요 (모듈명 앞 `_`가 내부 표시입니다).
공개 헬퍼 함수인 update_manual_drama_titles 는 예외입니다.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

KST = timezone(timedelta(hours=9))

# ── 경로 ──────────────────────────────────────────────────────────────────
_DRAMA_TITLES_PATH = Path("scripts/drama_titles.json")

# ── 탐색 설정 ─────────────────────────────────────────────────────────────
MAX_DRAMA_TITLES    = 20   # 제목 탐색 최대 수
TITLE_SEARCH_MONTHS = 6    # publishedAfter: 최근 N개월
TITLE_CACHE_DAYS    = 7    # auto_titles 캐시 갱신 주기
TITLE_SEARCH_SUFFIXES  = ["명장면", "클립"]
AUTO_TITLE_SEED_QUERIES = [
    "드라마 명장면",
    "한국 드라마 클립",
]
_TMDB_API_BASE = "https://api.themoviedb.org/3"
_KOBIS_API_BASE = "https://www.kobis.or.kr/kobisopenapi/webservice/rest"

# ── 드라마명 추출 정규식 ──────────────────────────────────────────────────
# 방송사/플랫폼 prefix 제거
_DRAMA_PREFIX_RE = re.compile(
    r'^\s*[\[【]?(?:tvN|JTBC|KBS\d*|MBC|SBS|OCN|EBS|채널A|'
    r'넷플릭스|Netflix|왓챠|Watcha|티빙|Tving|웨이브|Wavve)[\]】]?\s*[|·\-]?\s*'
    r'(?:드라마|영화|예능)?\s*',
    re.IGNORECASE,
)
# 에피소드·클립 suffix 제거
_DRAMA_EPISODE_RE = re.compile(
    r'\s*(?:\(?\d+\s*(?:화|회|부)\)?|EP\.?\s*\d+|E\d+|Ep\s*\d+|'
    r'시즌\s*\d+|Season\s*\d+|S\d+E\d+|'
    r'클립|명장면|하이라이트|Highlight|Clip|모음|티저|예고편?|OST|'
    r'리뷰|분석|해설|결말|엔딩|스포|레전드|full\s*ver|MV|M/V).*$',
    re.IGNORECASE,
)
# 개인 일상 콘텐츠 감지
_PERSONAL_CONTENT_RE = re.compile(
    r'\b(?:vlog|daily|일상|브이로그|먹방|mukbang|haul|룩북|lookbook|'
    r'shorts\s*challenge|챌린지)\b',
    re.IGNORECASE,
)
# 에피소드 마커 존재 여부
_HAS_EPISODE_RE = re.compile(
    r'\d+\s*(?:화|회|부)|EP\.?\s*\d+|E\d+(?!\d)|Ep\s*\d+|'
    r'시즌\s*\d+|Season\s*\d+|\[\s*[가-힣\w]+\s*\]\s*\d+',
    re.IGNORECASE,
)
# 드라마 hashtag 패턴
_DRAMA_HASHTAG_RE = re.compile(r'#([가-힣][가-힣\w,\s]{1,15})')
# hashtag 불용어
_HASHTAG_STOPWORDS = {
    "드라마", "영화", "예능", "클립", "명장면", "하이라이트", "shorts",
    "유머", "comedy", "viral", "kbs", "mbc", "sbs", "tvn", "jtbc", "ocn",
    "넷플릭스", "왓챠", "티빙", "웨이브", "유튜브", "드라마쇼츠", "드라마명장면",
    "드라마클립", "영화클립", "공포", "스릴러", "로맨스", "로맨틱", "사이다",
    "레전드", "highlight", "drama", "shorts", "fyp", "viral", "추천",
}
_TITLE_SOURCE_STOPWORDS = {
    "예고편", "티저", "메이킹", "비하인드", "하이라이트", "명장면", "클립",
    "리뷰", "해설", "결말", "스포", "모음", "ost", "mv", "shorts",
}


# ── 추출 함수 ─────────────────────────────────────────────────────────────

def extract_drama_name_from_hashtag(video_title: str) -> Optional[str]:
    """영상 제목의 한국어 hashtag에서 드라마·영화명 추출.

    Examples:
        "여사친이 치마를 입었을 때 #마지막썸머 #kbs" → "마지막썸머"
        "드라마 장면 #탁류 #드라마명장면"            → "탁류"
    """
    for m in _DRAMA_HASHTAG_RE.finditer(video_title):
        tag = m.group(1).strip()
        tag_lower = tag.lower().replace(" ", "")
        if tag_lower in _HASHTAG_STOPWORDS:
            continue
        if len(tag) >= 2 and re.search(r"[가-힣]{2,}", tag):
            return tag
    return None


def extract_drama_name_with_episode(video_title: str) -> Optional[str]:
    """에피소드 마커(N화, EP N)가 있는 제목에서 드라마명 추출.

    에피소드 마커가 없으면 None 반환 — 줄거리 설명문 오추출 방지.

    Examples:
        "눈물의 여왕 16화 명장면"    → "눈물의 여왕"
        "[tvN] 졸업 6화 하이라이트"  → "졸업"
        "MBC 드라마 연인 E12 클립"   → "연인"
    """
    if not _HAS_EPISODE_RE.search(video_title):
        return None
    text = _DRAMA_PREFIX_RE.sub("", video_title).strip()
    text = _DRAMA_EPISODE_RE.sub("", text).strip(" |-·[]【】「」")
    if _PERSONAL_CONTENT_RE.search(text):
        return None
    if len(text) >= 2 and re.search(r"[가-힣]{2,}", text):
        return text
    return None


# ── 기준 데이터 기반 자동 제목 수집 ───────────────────────────────────────

def collect_reference_titles(max_titles: int = MAX_DRAMA_TITLES) -> list[str]:
    """TMDB/KOBIS 기준 데이터에서 최신·인기 드라마/영화 제목을 수집한다.

    우선순위:
      1. TMDB TV trending/week, on_the_air, discover TV
      2. TMDB movie trending/week, now_playing, discover movie
      3. KOBIS 최근 7일 일별 박스오피스

    API 키가 없는 소스는 조용히 건너뛴다.
    """
    tmdb_titles = _dedupe_titles(_collect_tmdb_titles(), max_titles=max_titles)
    kobis_titles = _dedupe_titles(_collect_kobis_titles(), max_titles=8)
    return _dedupe_titles(
        tmdb_titles[:12] + kobis_titles + tmdb_titles[12:],
        max_titles=max_titles,
    )


def _collect_tmdb_titles() -> list[str]:
    api_key = os.environ.get("TMDB_API_KEY", "").strip()
    if not api_key:
        return []

    six_months_ago = (datetime.now(KST) - timedelta(days=TITLE_SEARCH_MONTHS * 30)).date().isoformat()
    requests_to_make = [
        ("tv", "trending/tv/week", {}),
        ("tv", "tv/on_the_air", {"region": "KR"}),
        ("tv", "discover/tv", {
            "watch_region": "KR",
            "with_origin_country": "KR",
            "with_genres": "18",
            "with_watch_monetization_types": "flatrate",
            "sort_by": "popularity.desc",
            "first_air_date.gte": six_months_ago,
        }),
        ("movie", "trending/movie/week", {}),
        ("movie", "movie/now_playing", {"region": "KR"}),
        ("movie", "discover/movie", {
            "region": "KR",
            "with_original_language": "ko",
            "sort_by": "popularity.desc",
            "primary_release_date.gte": six_months_ago,
        }),
    ]

    titles: list[str] = []
    for media_type, endpoint, extra in requests_to_make:
        payload = _request_json(
            f"{_TMDB_API_BASE}/{endpoint}",
            {
                "api_key": api_key,
                "language": "ko-KR",
                "page": 1,
                **extra,
            },
        )
        for item in payload.get("results", []):
            if not _is_korean_tmdb_item(item, media_type):
                continue
            titles.extend([
                str(item.get("name") or ""),
                str(item.get("title") or ""),
            ])
    return titles


def _is_korean_tmdb_item(item: dict, media_type: str) -> bool:
    original_language = str(item.get("original_language") or "").lower()
    if original_language == "ko":
        if media_type == "tv":
            return 18 in (item.get("genre_ids") or [])
        return True
    if media_type == "tv":
        origin_country = item.get("origin_country") or []
        return "KR" in origin_country and 18 in (item.get("genre_ids") or [])
    return False


def _collect_kobis_titles() -> list[str]:
    api_key = os.environ.get("KOBIS_API_KEY", "").strip()
    if not api_key:
        return []

    titles: list[str] = []
    today = datetime.now(KST).date()
    for days_ago in range(1, 8):
        target_dt = (today - timedelta(days=days_ago)).strftime("%Y%m%d")
        payload = _request_json(
            f"{_KOBIS_API_BASE}/boxoffice/searchDailyBoxOfficeList.json",
            {"key": api_key, "targetDt": target_dt, "repNationCd": "K"},
        )
        boxoffice = payload.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
        titles.extend(str(item.get("movieNm") or "") for item in boxoffice)
    return titles


def _request_json(url: str, params: dict) -> dict:
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def _dedupe_titles(titles: list[str], *, max_titles: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in titles:
        title = _normalize_reference_title(raw)
        if not title or title in seen:
            continue
        seen.add(title)
        result.append(title)
        if len(result) >= max_titles:
            break
    return result


def _normalize_reference_title(raw: str) -> str:
    title = re.sub(r"\s+", " ", raw or "").strip(" \t\r\n-:|·")
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    if not title:
        return ""
    lowered = title.lower().replace(" ", "")
    if any(word in lowered for word in _TITLE_SOURCE_STOPWORDS):
        return ""
    if not re.search(r"[가-힣]{2,}", title):
        return ""
    if len(title) < 2 or len(title) > 30:
        return ""
    return title


# ── 파일 I/O ─────────────────────────────────────────────────────────────

def load_drama_titles_file() -> dict:
    if not _DRAMA_TITLES_PATH.exists():
        return {"manual_titles": [], "auto_titles": [], "updated_at": ""}
    with open(_DRAMA_TITLES_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_drama_titles_file(manual_titles: list[str], auto_titles: list[str]) -> None:
    _DRAMA_TITLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_DRAMA_TITLES_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "manual_titles": manual_titles,
                "auto_titles": auto_titles,
                "updated_at": datetime.now(KST).isoformat(),
                "_comment": {
                    "manual_titles": "담당자가 직접 관리. 최근 6개월 방영·인기 드라마/영화 제목 입력.",
                    "auto_titles": "TMDB/KOBIS 기준 데이터에서 수집한 최신·인기 드라마/영화 제목 (7일 캐시).",
                    "updated_at": "auto_titles 마지막 갱신 시각.",
                },
            },
            f, ensure_ascii=False, indent=2,
        )


def update_manual_drama_titles(titles: list[str]) -> None:
    """manual_titles 목록 업데이트.

    Example::

        from src.core.crawlers._drama_title import update_manual_drama_titles
        update_manual_drama_titles([
            "눈물의 여왕", "졸업", "연인", "이재, 곧 죽습니다", "오징어게임",
        ])
    """
    data = load_drama_titles_file()
    data["manual_titles"] = list(dict.fromkeys(t.strip() for t in titles if t.strip()))
    with open(_DRAMA_TITLES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
