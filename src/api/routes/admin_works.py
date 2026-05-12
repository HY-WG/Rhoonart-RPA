"""Admin works routes — seed channels, works search/enrich, kakao creators."""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests as http_requests
from fastapi import APIRouter, Depends

from src.api.dependencies import (
    KST,
    WORK_SEARCH_EXTERNAL_CACHE,
    WORK_SEARCH_EXTERNAL_CACHE_TTL_SECONDS,
    check_auth,
    get_supabase,
)
from src.config import settings

router = APIRouter(tags=["works"])
logger = logging.getLogger(__name__)

# ── Genre / country mapping tables ───────────────────────────────────────────

_TMDB_TV_GENRES: dict[int, str] = {
    18: "드라마", 35: "코미디", 80: "범죄", 99: "다큐",
    10759: "액션", 10749: "로맨스", 10765: "SF", 10768: "역사",
    9648: "스릴러", 16: "애니메이션",
}
_TMDB_MOVIE_GENRES: dict[int, str] = {
    18: "드라마", 35: "코미디", 80: "범죄", 99: "다큐",
    28: "액션", 10749: "로맨스", 878: "SF", 36: "역사",
    53: "스릴러", 27: "공포", 14: "판타지", 16: "애니메이션",
}
_COUNTRY_MAP: dict[str, str] = {
    "KR": "한국", "US": "미국", "JP": "일본",
    "CN": "중국", "TW": "중국", "GB": "미국",
}
_VALID_GENRES = {"로맨스", "스릴러", "액션", "코미디", "판타지", "역사", "SF", "공포", "드라마", "다큐"}
_TITLE_SEARCH_ALIASES: dict[str, list[str]] = {
    "헌티드": ["House on Haunted Hill", "The Haunted", "Haunted"],
}
_KMDB_GENRE_MAP: dict[str, str] = {
    "드라마": "드라마", "멜로/로맨스": "로맨스", "로맨스": "로맨스",
    "액션": "액션", "코미디": "코미디", "SF": "SF", "공포": "공포",
    "스릴러": "스릴러", "판타지": "판타지", "역사": "역사",
    "다큐멘터리": "다큐", "애니메이션": "애니메이션",
}
_NAVER_GENRE_MAP: dict[str, str] = {
    "드라마": "드라마", "멜로/로맨스": "로맨스", "로맨스": "로맨스",
    "액션": "액션", "코미디": "코미디", "SF": "SF", "공포": "공포",
    "스릴러": "스릴러", "판타지": "판타지", "사극": "역사", "역사": "역사",
    "다큐": "다큐",
}


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _tmdb_genre(genre_ids: list[int], media_type: str) -> str:
    genre_map = _TMDB_TV_GENRES if media_type == "tv" else _TMDB_MOVIE_GENRES
    for gid in genre_ids:
        g = genre_map.get(gid)
        if g and g in _VALID_GENRES:
            return g
    return ""


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> None:
    """Fill missing keys in *base* from *extra*."""
    for k, v in extra.items():
        if v and not base.get(k):
            base[k] = v


def _work_search_item(
    *,
    title: str,
    year: str = "",
    source: str,
    external_id: str,
    media_type: str = "",
    rights_holder_name: str = "",
    identifier: str = "",
) -> dict[str, Any]:
    return {
        "work_id": external_id or f"{source}:{title}:{year}",
        "work_title": title,
        "display_title": f"{title} ({year})" if year else title,
        "release_year": year,
        "rights_holder_name": rights_holder_name,
        "identifier": identifier,
        "source": source,
        "external_id": external_id,
        "media_type": media_type,
    }


def _normalize_omdb_value(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text in {"", "N/A"} else text


def _map_omdb_type(value: str) -> str:
    return "드라마" if value == "series" else "영화"


def _map_omdb_country(value: str) -> str:
    text = value.lower()
    if "south korea" in text or "korea" in text:
        return "한국"
    if "united states" in text or "usa" in text:
        return "미국"
    if "japan" in text:
        return "일본"
    if "china" in text or "hong kong" in text or "taiwan" in text:
        return "중국"
    return "기타" if value else ""


def _map_external_genre(value: str) -> str:
    genre_text = value.lower()
    candidates = [
        ("romance", "로맨스"), ("thriller", "스릴러"), ("action", "액션"),
        ("comedy", "코미디"), ("fantasy", "판타지"), ("history", "역사"),
        ("sci-fi", "SF"), ("science fiction", "SF"), ("horror", "공포"),
        ("animation", "애니메이션"), ("drama", "드라마"),
    ]
    for token, mapped in candidates:
        if token in genre_text:
            return mapped
    return ""


# ── OMDb ─────────────────────────────────────────────────────────────────────

def _omdb_detail(params: dict[str, str]) -> dict[str, Any]:
    key = settings.OMDB_API_KEY
    if not key:
        logger.info("work enrich fallback: OMDb skipped because OMDB_API_KEY is empty")
        return {}
    resp = http_requests.get(
        "https://www.omdbapi.com/",
        params={**params, "apikey": key, "plot": "full", "r": "json"},
        timeout=6,
    )
    if not resp.ok:
        logger.info("work enrich fallback: OMDb HTTP %s", resp.status_code)
        return {}
    data = resp.json()
    if data.get("Response") == "False":
        logger.info("work enrich fallback: OMDb empty response: %s", data.get("Error"))
        return {}
    out: dict[str, Any] = {}
    year = _normalize_omdb_value(data.get("Year"))[:4]
    if year:
        out["release_year"] = year
    media_type = _normalize_omdb_value(data.get("Type"))
    if media_type:
        out["video_type"] = _map_omdb_type(media_type)
    plot = _normalize_omdb_value(data.get("Plot"))
    if plot:
        out["description"] = plot
    genre = _map_external_genre(_normalize_omdb_value(data.get("Genre")))
    if genre:
        out["genre"] = genre
    country = _map_omdb_country(_normalize_omdb_value(data.get("Country")))
    if country:
        out["country"] = country
    director = _normalize_omdb_value(data.get("Director"))
    if director:
        out["director"] = director
    cast = _normalize_omdb_value(data.get("Actors"))
    if cast:
        out["cast"] = cast
    return out


def _enrich_omdb(title: str, external_id: str = "") -> dict[str, Any]:
    if external_id:
        return _omdb_detail({"i": external_id})
    return _omdb_detail({"t": title})


def _search_omdb_titles(title: str, limit: int) -> list[dict[str, Any]]:
    key = settings.OMDB_API_KEY
    if not key:
        return []
    try:
        resp = http_requests.get(
            "https://www.omdbapi.com/",
            params={"apikey": key, "s": title, "type": "movie", "r": "json", "page": 1},
            timeout=6,
        )
        if not resp.ok:
            return []
        items = resp.json().get("Search") or []
        return [
            _work_search_item(
                title=_normalize_omdb_value(item.get("Title")),
                year=_normalize_omdb_value(item.get("Year"))[:4],
                source="omdb",
                external_id=_normalize_omdb_value(item.get("imdbID")),
                media_type=_normalize_omdb_value(item.get("Type")),
            )
            for item in items[:limit]
            if _normalize_omdb_value(item.get("Title"))
        ]
    except Exception as exc:
        logger.info("work search: OMDb failed: %s", exc)
        return []


# ── TVmaze ────────────────────────────────────────────────────────────────────

def _tvmaze_show_to_result(show: dict[str, Any]) -> dict[str, Any]:
    year = str(show.get("premiered") or "")[:4]
    return _work_search_item(
        title=str(show.get("name") or "").strip(),
        year=year,
        source="tvmaze",
        external_id=str(show.get("id") or ""),
        media_type="series",
    )


def _search_tvmaze_titles(title: str, limit: int) -> list[dict[str, Any]]:
    try:
        resp = http_requests.get(
            "https://api.tvmaze.com/search/shows",
            params={"q": title},
            timeout=6,
        )
        if not resp.ok:
            return []
        results = []
        for item in resp.json()[:limit]:
            show = item.get("show") or {}
            if show.get("name"):
                results.append(_tvmaze_show_to_result(show))
        return results
    except Exception as exc:
        logger.info("work search: TVmaze failed: %s", exc)
        return []


def _enrich_tvmaze(title: str, external_id: str = "") -> dict[str, Any]:
    try:
        if external_id:
            resp = http_requests.get(f"https://api.tvmaze.com/shows/{external_id}", timeout=6)
            show = resp.json() if resp.ok else {}
        else:
            resp = http_requests.get(
                "https://api.tvmaze.com/singlesearch/shows",
                params={"q": title},
                timeout=6,
            )
            show = resp.json() if resp.ok else {}
        if not show:
            logger.info("work enrich fallback: TVmaze returned no show")
            return {}
        out: dict[str, Any] = {
            "video_type": "드라마",
            "release_year": str(show.get("premiered") or "")[:4],
            "description": re.sub(
                r"<[^>]+>",
                "",
                __import__("html").unescape(str(show.get("summary") or "")),
            ).strip(),
        }
        genre = _map_external_genre(", ".join(show.get("genres") or []))
        if genre:
            out["genre"] = genre
        country = (
            ((show.get("network") or {}).get("country") or {}).get("code")
            or ((show.get("webChannel") or {}).get("country") or {}).get("code")
            or ""
        )
        if country:
            out["country"] = _COUNTRY_MAP.get(country, "기타")
        show_id = str(show.get("id") or external_id)
        if show_id:
            cast_resp = http_requests.get(f"https://api.tvmaze.com/shows/{show_id}/cast", timeout=5)
            if cast_resp.ok:
                cast_names = [
                    ((item.get("person") or {}).get("name") or "")
                    for item in cast_resp.json()[:5]
                ]
                cast_names = [name for name in cast_names if name]
                if cast_names:
                    out["cast"] = ", ".join(cast_names)
            crew_resp = http_requests.get(f"https://api.tvmaze.com/shows/{show_id}/crew", timeout=5)
            if crew_resp.ok:
                creators = [
                    (item.get("person") or {}).get("name")
                    for item in crew_resp.json()
                    if str(item.get("type") or "").lower() in {"creator", "director"}
                ]
                if creators:
                    out["director"] = creators[0]
        return {key: value for key, value in out.items() if value}
    except Exception as exc:
        logger.info("work enrich fallback: TVmaze failed: %s", exc)
        return {}


# ── TMDB ─────────────────────────────────────────────────────────────────────

def _search_tmdb_titles(title: str, limit: int) -> list[dict[str, Any]]:
    key = settings.TMDB_API_KEY
    if not key or limit <= 0:
        return []

    def _request(query_title: str, display_query_title: str = "") -> list[dict[str, Any]]:
        resp = http_requests.get(
            "https://api.themoviedb.org/3/search/multi",
            params={"query": query_title, "language": "ko-KR", "api_key": key, "page": 1, "include_adult": "false"},
            timeout=6,
        )
        if not resp.ok:
            logger.info("work search: TMDB HTTP %s", resp.status_code)
            return []
        results: list[dict[str, Any]] = []
        for item in resp.json().get("results", []):
            media_type = item.get("media_type")
            if media_type not in {"movie", "tv"}:
                continue
            item_title = str(
                item.get("title") or item.get("name") or item.get("original_title") or item.get("original_name") or ""
            ).strip()
            if not item_title:
                continue
            date_value = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
            year = str(date_value or "")[:4]
            result = _work_search_item(
                title=display_query_title or item_title,
                year=year,
                source="tmdb",
                external_id=f"{media_type}:{item.get('id')}",
                media_type=str(media_type),
            )
            result["source_title"] = item_title
            results.append(result)
            if len(results) >= limit:
                break
        return results

    try:
        aliases = _TITLE_SEARCH_ALIASES.get(title.strip(), [])
        results: list[dict[str, Any]] = []
        for alias in aliases:
            results.extend(_request(alias, title.strip()))
            if len(results) >= limit:
                break
        if len(results) < limit:
            results.extend(_request(title))
        return results[:limit]
    except Exception as exc:
        logger.info("work search: TMDB failed: %s", exc)
        return []


def _enrich_tmdb(title: str, external_id: str = "") -> dict[str, Any]:
    key = settings.TMDB_API_KEY
    if not key:
        return {}
    try:
        if external_id and ":" in external_id:
            media_type, raw_tmdb_id = external_id.split(":", 1)
            if media_type not in {"movie", "tv"}:
                return {}
            tmdb_id = int(raw_tmdb_id)
            detail_resp = http_requests.get(
                f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}",
                params={"language": "ko-KR", "api_key": key},
                timeout=6,
            )
            if not detail_resp.ok:
                return {}
            detail = detail_resp.json()
            item = {
                **detail,
                "media_type": media_type,
                "title": detail.get("title") or detail.get("name"),
                "release_date": detail.get("release_date"),
                "first_air_date": detail.get("first_air_date"),
                "genre_ids": [genre.get("id") for genre in detail.get("genres", [])],
                "origin_country": detail.get("origin_country") or [],
            }
        else:
            resp = http_requests.get(
                "https://api.themoviedb.org/3/search/multi",
                params={"query": title, "language": "ko-KR", "api_key": key, "page": 1},
                timeout=6,
            )
            if not resp.ok:
                return {}
            items = [i for i in resp.json().get("results", []) if i.get("media_type") in ("movie", "tv")]
            if not items:
                return {}
            item = items[0]
            media_type = item["media_type"]
            tmdb_id = int(item["id"])

        out: dict[str, Any] = {}
        if media_type == "tv":
            out["video_type"] = "드라마"
            out["release_year"] = (item.get("first_air_date") or "")[:4]
            origins: list[str] = item.get("origin_country") or []
        else:
            out["video_type"] = "영화"
            out["release_year"] = (item.get("release_date") or "")[:4]
            origins = []
        out["description"] = item.get("overview") or ""
        poster_path = item.get("poster_path")
        if poster_path:
            out["thumbnail_url"] = f"https://image.tmdb.org/t/p/w500{poster_path}"
        genre = _tmdb_genre(item.get("genre_ids") or [], media_type)
        if genre:
            out["genre"] = genre
        if origins:
            mapped_c = _COUNTRY_MAP.get(origins[0])
            if mapped_c:
                out["country"] = mapped_c
        credits_resp = http_requests.get(
            f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/credits",
            params={"language": "ko-KR", "api_key": key},
            timeout=5,
        )
        if credits_resp.ok:
            credits = credits_resp.json()
            cast_names = [m["name"] for m in (credits.get("cast") or [])[:5] if m.get("name")]
            if cast_names:
                out["cast"] = ", ".join(cast_names)
            dirs = [m["name"] for m in (credits.get("crew") or []) if m.get("job") == "Director" and m.get("name")]
            if dirs:
                out["director"] = dirs[0]
        return out
    except Exception as exc:
        logger.info("work enrich fallback: TMDB failed: %s", exc)
        return {}


# ── KMDB ─────────────────────────────────────────────────────────────────────

def _enrich_kmdb(title: str) -> dict[str, Any]:
    key = settings.KMDB_API_KEY
    if not key:
        return {}
    try:
        resp = http_requests.get(
            "https://api.kmdb.or.kr/v1/movie/search",
            params={"collection": "kmdb_query", "detail": "Y", "query": title, "ServiceKey": key, "listCount": 3},
            timeout=6,
        )
        if not resp.ok:
            return {}
        data = resp.json()
        items = (data.get("Data") or [{}])[0].get("Result") or []
        if not items:
            return {}
        item = items[0]
        out: dict[str, Any] = {}
        year = str(item.get("prodYear") or "").strip()
        if year and year.isdigit():
            out["release_year"] = year
        movie_type = str(item.get("movieType") or "").strip()
        if "드라마" in movie_type:
            out["video_type"] = "드라마"
        elif movie_type:
            out["video_type"] = "영화"
        genres_raw = str(item.get("genre") or "").split(",")
        for g in genres_raw:
            mapped = _KMDB_GENRE_MAP.get(g.strip())
            if mapped:
                out["genre"] = mapped
                break
        nation = str(item.get("nation") or "").strip()
        if "한국" in nation:
            out["country"] = "한국"
        elif "미국" in nation:
            out["country"] = "미국"
        elif "일본" in nation:
            out["country"] = "일본"
        directors = item.get("directors", {}).get("director") or []
        if directors and isinstance(directors, list):
            out["director"] = directors[0].get("directorNm", "")
        elif isinstance(directors, dict):
            out["director"] = directors.get("directorNm", "")
        actors = item.get("actors", {}).get("actor") or []
        if isinstance(actors, list):
            names = [a.get("actorNm", "") for a in actors[:5] if a.get("actorNm")]
            if names:
                out["cast"] = ", ".join(names)
        elif isinstance(actors, dict):
            nm = actors.get("actorNm", "")
            if nm:
                out["cast"] = nm
        plots = item.get("plots", {}).get("plot") or []
        if isinstance(plots, list) and plots:
            out["description"] = plots[0].get("plotText", "")
        elif isinstance(plots, dict):
            out["description"] = plots.get("plotText", "")
        return out
    except Exception:
        return {}


# ── Naver movie scraping ──────────────────────────────────────────────────────

def _enrich_naver_movie(title: str) -> dict[str, Any]:
    try:
        from bs4 import BeautifulSoup  # noqa: PLC0415
    except ImportError:
        return {}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9",
        }
        search_url = (
            "https://movie.naver.com/movie/search/result.nhn"
            f"?query={http_requests.utils.quote(title)}&section=movie&ie=utf8"
        )
        resp = http_requests.get(search_url, headers=headers, timeout=7)
        if not resp.ok:
            return {}
        soup = BeautifulSoup(resp.text, "lxml")
        item = (
            soup.select_one(".result_item.result_movie")
            or soup.select_one(".result_thumb")
            or soup.select_one("li.result_item")
        )
        if not item:
            return {}
        out: dict[str, Any] = {}
        info_spans = item.select(".info span") or item.select("p.info span")
        info_texts = [s.get_text(strip=True) for s in info_spans]
        for text in info_texts:
            if text.isdigit() and len(text) == 4:
                out.setdefault("release_year", text)
            elif text in ("한국", "미국", "일본", "중국"):
                out.setdefault("country", text)
            else:
                mapped = _NAVER_GENRE_MAP.get(text)
                if mapped:
                    out.setdefault("genre", mapped)
                if text in ("드라마", "연속극"):
                    out.setdefault("video_type", "드라마")
                elif text in ("영화", "단편영화"):
                    out.setdefault("video_type", "영화")
        dir_tag = (
            item.select_one(".info.dir a")
            or item.select_one("p.info.dir a")
            or item.select_one("[class*='director'] a")
        )
        if dir_tag:
            out["director"] = dir_tag.get_text(strip=True)
        act_tags = item.select(".info.act a") or item.select("p.info.act a")
        if act_tags:
            out["cast"] = ", ".join(t.get_text(strip=True) for t in act_tags[:5])
        return out
    except Exception:
        return {}


# ── Watcha Pedia fallback ─────────────────────────────────────────────────────

def _enrich_watcha_pedia(title: str) -> dict[str, Any]:
    try:
        from bs4 import BeautifulSoup  # noqa: PLC0415
    except ImportError:
        return {}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.7",
        }
        resp = http_requests.get(
            f"https://pedia.watcha.com/ko-KR/search?query={http_requests.utils.quote(title)}",
            headers=headers,
            timeout=7,
        )
        if not resp.ok:
            return {}
        soup = BeautifulSoup(resp.text, "lxml")
        text = soup.get_text(" ", strip=True)
        out: dict[str, Any] = {}
        if "영화" in text:
            out["video_type"] = "영화"
        elif "TV" in text or "시리즈" in text or "드라마" in text:
            out["video_type"] = "드라마"
        for token in text.split():
            cleaned = token.strip("()[]·,")
            if cleaned.isdigit() and len(cleaned) == 4:
                out["release_year"] = cleaned
                break
        for country in ("한국", "미국", "일본", "중국", "영국"):
            if country in text:
                out["country"] = country
                break
        return out
    except Exception:
        return {}


# ── YouTube trailer ───────────────────────────────────────────────────────────

def _enrich_youtube_trailer(title: str) -> dict[str, Any]:
    key = settings.YOUTUBE_API_KEY
    if not key:
        return {}
    try:
        resp = http_requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": f"{title} 공식 트레일러",
                "type": "video",
                "maxResults": 3,
                "key": key,
                "relevanceLanguage": "ko",
                "videoEmbeddable": "true",
            },
            timeout=5,
        )
        if resp.ok:
            yt_items = resp.json().get("items", [])
            if yt_items:
                vid = yt_items[0]["id"]["videoId"]
                return {"trailer_url": f"https://www.youtube.com/watch?v={vid}"}
    except Exception:
        pass
    return {}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/api/admin/seed-channels")
def list_seed_channels(
    platform: str = "",
    status: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    """Supabase seed_channel 목록 조회."""
    sb = get_supabase()
    q = (
        sb.table("seed_channel")
        .select("*")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if platform:
        q = q.eq("platform", platform)
    if status:
        q = q.eq("status", status)
    result = q.execute()
    return {"items": result.data or []}


@router.get("/api/admin/works/search")
def search_works(q: str = "", limit: int = 20, include_external: bool = True) -> dict[str, Any]:
    """작품명 검색 (자동완성용). 내부 작품 + OMDb/TVmaze 후보를 함께 반환."""
    q = q.strip()
    if len(q) < 2:
        return {"items": []}
    sb = get_supabase()
    internal_items: list[dict[str, Any]] = []
    try:
        result = (
            sb.table("works")
            .select("id,work_title,release_year,rights_holder_id")
            .ilike("work_title", f"%{q}%")
            .order("work_title")
            .limit(limit)
            .execute()
        )
        internal_items = [
            {
                "work_id": item.get("id"),
                "work_title": item.get("work_title") or "",
                "display_title": (
                    f"{item.get('work_title')} ({item.get('release_year')})"
                    if item.get("release_year")
                    else item.get("work_title") or ""
                ),
                "release_year": str(item.get("release_year") or ""),
                "rights_holder_name": "",
                "identifier": "",
                "source": "internal",
                "external_id": str(item.get("id") or ""),
                "media_type": "",
            }
            for item in (result.data or [])
        ]
    except Exception as exc:
        logger.info("work search: works lookup failed: %s", exc)
        try:
            result = (
                sb.table("naver_works")
                .select("id,work_title,rights_holder_name,identifier")
                .ilike("work_title", f"%{q}%")
                .order("work_title")
                .limit(limit)
                .execute()
            )
            internal_items = [
                {
                    "work_id": item.get("id"),
                    "work_title": item.get("work_title") or "",
                    "display_title": item.get("work_title") or "",
                    "release_year": "",
                    "rights_holder_name": item.get("rights_holder_name") or "",
                    "identifier": item.get("identifier") or "",
                    "source": "internal",
                    "external_id": str(item.get("id") or ""),
                    "media_type": "",
                }
                for item in (result.data or [])
            ]
        except Exception as fallback_exc:
            logger.info("work search: naver_works lookup failed: %s", fallback_exc)

    external_items: list[dict[str, Any]] = []
    if include_external and len(internal_items) < limit:
        external_limit = max(0, limit - len(internal_items))
        cache_key = f"{q.lower()}:{external_limit}"
        cached = WORK_SEARCH_EXTERNAL_CACHE.get(cache_key)
        if cached and time.monotonic() - cached[0] < WORK_SEARCH_EXTERNAL_CACHE_TTL_SECONDS:
            external_items = cached[1]
        else:
            external_items.extend(_search_tmdb_titles(q, external_limit))
            remaining = max(0, limit - len(internal_items) - len(external_items))
            external_items.extend(_search_omdb_titles(q, remaining))
            remaining = max(0, limit - len(internal_items) - len(external_items))
            external_items.extend(_search_tvmaze_titles(q, remaining))
            WORK_SEARCH_EXTERNAL_CACHE[cache_key] = (time.monotonic(), external_items)

    seen: set[tuple[str, str]] = set()
    items: list[dict[str, Any]] = []
    for item in [*internal_items, *external_items]:
        key = (str(item.get("work_title") or "").lower(), str(item.get("release_year") or ""))
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return {"items": items[:limit]}


@router.get("/api/admin/works/enrich")
def enrich_work_info(
    title: str,
    source: str = "",
    external_id: str = "",
    debug_force_empty_sources: str = "",
) -> dict[str, Any]:
    """
    작품명으로 메타데이터 자동 완성.
    우선순위: KMDB → Naver Movie → TMDB → OMDb → TVmaze → YouTube.
    각 소스는 앞 소스가 채우지 못한 필드만 보완한다.
    """
    if not title or not title.strip():
        return {}

    result: dict[str, Any] = {}
    debug_log: list[str] = []
    forced_empty = {part.strip().lower() for part in debug_force_empty_sources.split(",") if part.strip()}

    def _source_allowed(name: str) -> bool:
        if name in forced_empty:
            message = f"{name} forced empty for fallback verification"
            logger.info("work enrich fallback: %s", message)
            debug_log.append(message)
            return False
        return True

    def _apply(name: str, producer) -> None:
        before = dict(result)
        data = producer() if _source_allowed(name) else {}
        _merge(result, data)
        filled = [key for key, value in result.items() if value and not before.get(key)]
        message = f"{name}: filled {', '.join(filled) if filled else 'none'}"
        logger.info("work enrich fallback: %s", message)
        debug_log.append(message)

    explicit_candidate = bool(source and external_id)
    if source == "omdb" and external_id:
        _apply("omdb", lambda: _enrich_omdb(title, external_id))
    elif source == "tvmaze" and external_id:
        _apply("tvmaze", lambda: _enrich_tvmaze(title, external_id))
    elif source == "tmdb" and external_id:
        _apply("tmdb", lambda: _enrich_tmdb(title, external_id))

    if explicit_candidate:
        _apply("youtube", lambda: _enrich_youtube_trailer(f"{title} {result.get('release_year') or ''}".strip()))
        if debug_force_empty_sources:
            result["debug_log"] = debug_log
        return result

    _apply("kmdb", lambda: _enrich_kmdb(title))
    if len([v for v in result.values() if v]) < 4:
        _apply("naver", lambda: _enrich_naver_movie(title))
    _apply("tmdb", lambda: _enrich_tmdb(title))
    if len([v for v in result.values() if v]) < 4:
        _apply("omdb", lambda: _enrich_omdb(title))
    if len([v for v in result.values() if v]) < 4:
        _apply("tvmaze", lambda: _enrich_tvmaze(title))
    _apply("youtube", lambda: _enrich_youtube_trailer(title))

    if debug_force_empty_sources:
        result["debug_log"] = debug_log
    return result


@router.get("/api/admin/kakao-creators")
def list_kakao_creators(
    status: str = "",
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    """Supabase kakao_creators 목록 조회."""
    sb = get_supabase()
    q = (
        sb.table("kakao_creators")
        .select("*")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if status:
        q = q.eq("status", status)
    result = q.execute()
    return {"items": result.data or []}
