"""
top10_today.py — 오늘의 예능(Entertainment) 장르 TOP 10 영상 추출
-----------------------------------------------------------------
YouTube Data API의 mostPopular 차트에서 Entertainment 카테고리(ID=24)
영상을 가져와 조회수 내림차순으로 정렬한 뒤 Google Spreadsheet에 기록합니다.

Usage:
    python top10_today.py

Config:
    .env 파일에서 YOUTUBE_API_KEY, GOOGLE_SPREADSHEET_ID,
    GOOGLE_CREDENTIALS_FILE, TOP10_REGION_CODE 를 읽습니다.
"""

import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    YOUTUBE_API_KEY,
    TOP10_REGION_CODE,
    TARGET_CATEGORY_ID,
)
from youtube_client import CATEGORY_MAP
from sheets_client import SheetsClient

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("top10_today.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# YouTube helpers
# ------------------------------------------------------------------

def _parse_duration(iso: str) -> str:
    """PT4M13S → 4:13 형식으로 변환."""
    if not iso:
        return ""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return iso
    h, mi, s = (int(v or 0) for v in m.groups())
    if h:
        return f"{h}:{mi:02d}:{s:02d}"
    return f"{mi}:{s:02d}"


def fetch_top10_entertainment(region_code: str = "KR") -> list[dict]:
    """YouTube mostPopular 차트에서 Entertainment TOP 10 영상을 가져옵니다.

    - chart: mostPopular
    - videoCategoryId: 24 (Entertainment)
    - regionCode: 기본 KR (한국)
    - 조회수 내림차순 정렬 후 상위 10개 반환
    """
    if not YOUTUBE_API_KEY:
        raise ValueError("YOUTUBE_API_KEY is not set in .env")

    service = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # mostPopular 차트 호출 — 최대 50개 요청 후 조회수로 재정렬
    try:
        response = service.videos().list(
            part="snippet,contentDetails,statistics",
            chart="mostPopular",
            videoCategoryId=TARGET_CATEGORY_ID,
            regionCode=region_code,
            maxResults=50,
        ).execute()
    except HttpError as e:
        logger.error(f"YouTube API 오류: {e}")
        raise

    items = response.get("items", [])
    logger.info(f"API 응답: {len(items)}개 영상 수신 (region={region_code})")

    videos = []
    for item in items:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        thumbnails = snippet.get("thumbnails", {})
        category_id = snippet.get("categoryId", "")
        video_id = item.get("id", "")

        view_count = int(stats.get("viewCount") or 0)

        videos.append({
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "view_count": view_count,
            "like_count": stats.get("likeCount", ""),
            "comment_count": stats.get("commentCount", ""),
            "duration": _parse_duration(content.get("duration", "")),
            "category_id": category_id,
            "category_name": CATEGORY_MAP.get(category_id, ""),
            "region": region_code,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_high": thumbnails.get("high", {}).get("url", ""),
        })

    # 조회수 내림차순 정렬
    videos.sort(key=lambda v: v["view_count"], reverse=True)

    # 순위 부여 및 상위 10개 추출
    top10 = []
    for rank, v in enumerate(videos[:10], start=1):
        v["rank"] = rank
        top10.append(v)

    return top10


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info(f"=== 오늘의 예능 TOP 10 수집 시작 ({today}, region={TOP10_REGION_CODE}) ===")

    try:
        top10 = fetch_top10_entertainment(region_code=TOP10_REGION_CODE)

        if not top10:
            logger.warning("수집된 영상이 없습니다. 지역 코드나 카테고리를 확인하세요.")
            return

        logger.info("--- TOP 10 결과 ---")
        for v in top10:
            logger.info(
                f"[{v['rank']:2d}위] {v['title'][:40]:40s} | "
                f"조회수: {v['view_count']:>10,} | {v['channel_title']}"
            )

        sheets = SheetsClient()
        written = sheets.write_top10(top10)
        logger.info(f"=== 완료: {written}개 행을 스프레드시트에 기록했습니다 ===")

    except Exception as e:
        logger.exception(f"오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()
