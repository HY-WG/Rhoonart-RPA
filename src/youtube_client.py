import re
import logging
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import (
    YOUTUBE_API_KEY, BATCH_SIZE,
    TARGET_CATEGORY_ID, MAX_VIDEOS_PER_CHANNEL,
    EMAIL_REGEX, QUOTA_DAILY_LIMIT,
)

logger = logging.getLogger(__name__)

CATEGORY_MAP = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "18": "Short Movies",
    "19": "Travel & Events", "20": "Gaming", "21": "Videoblogging",
    "22": "People & Blogs", "23": "Comedy", "24": "Entertainment",
    "25": "News & Politics", "26": "Howto & Style", "27": "Education",
    "28": "Science & Technology", "29": "Nonprofits & Activism",
}


class YouTubeClient:
    def __init__(self):
        if not YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY is not set in .env")
        self.service = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        self.quota_used = 0

    def _check_quota(self, cost: int):
        self.quota_used += cost
        if self.quota_used >= QUOTA_DAILY_LIMIT:
            raise RuntimeError(
                f"Quota limit approached ({self.quota_used} units). Halting to protect daily quota."
            )

    # ------------------------------------------------------------------
    # Channel methods
    # ------------------------------------------------------------------

    def search_channels(self, keyword: str, max_results: int = 50) -> list[str]:
        """Search channels by keyword and return list of channel IDs."""
        channel_ids = []
        next_page_token = None

        while len(channel_ids) < max_results:
            try:
                self._check_quota(100)  # search.list costs 100 units
                request = self.service.search().list(
                    part="id",
                    type="channel",
                    q=keyword,
                    maxResults=min(BATCH_SIZE, max_results - len(channel_ids)),
                    pageToken=next_page_token,
                )
                response = request.execute()
                for item in response.get("items", []):
                    channel_ids.append(item["id"]["channelId"])
                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break
            except HttpError as e:
                if e.status_code == 403:
                    logger.error("Quota exceeded (403). Halting search.")
                    raise RuntimeError("YouTube API quota exceeded.") from e
                logger.warning(f"Search error: {e}. Skipping page.")
                break

        logger.info(f"Found {len(channel_ids)} channels for keyword '{keyword}'")
        return channel_ids

    def fetch_channels(self, channel_ids: list[str]) -> list[dict]:
        """Fetch full channel metadata for a list of channel IDs."""
        results = []
        for i in range(0, len(channel_ids), BATCH_SIZE):
            batch = channel_ids[i: i + BATCH_SIZE]
            try:
                self._check_quota(1)
                response = self.service.channels().list(
                    part="snippet,statistics,brandingSettings,contentDetails",
                    id=",".join(batch),
                    maxResults=BATCH_SIZE,
                ).execute()
                for item in response.get("items", []):
                    results.append(self._parse_channel(item))
            except HttpError as e:
                if e.status_code == 403:
                    raise RuntimeError("YouTube API quota exceeded.") from e
                logger.warning(f"Channel fetch error for batch {i}: {e}")
        return results

    def _parse_channel(self, item: dict) -> dict:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        branding = item.get("brandingSettings", {})
        thumbnails = snippet.get("thumbnails", {})

        description = snippet.get("description", "") or ""
        emails = self._extract_emails(description)

        return {
            "channel_id": item.get("id"),
            "title": snippet.get("title"),
            "description": description[:500],
            "custom_url": snippet.get("customUrl"),
            "published_at": snippet.get("publishedAt"),
            "country": snippet.get("country"),
            "subscriber_count": stats.get("subscriberCount"),    # None if hidden
            "view_count": stats.get("viewCount"),
            "video_count": stats.get("videoCount"),
            "thumbnail_default": thumbnails.get("default", {}).get("url"),
            "thumbnail_medium": thumbnails.get("medium", {}).get("url"),
            "thumbnail_high": thumbnails.get("high", {}).get("url"),
            "banner_url": branding.get("image", {}).get("bannerExternalUrl"),
            "keywords": branding.get("channel", {}).get("keywords"),
            "email": "|".join(emails) if emails else None,
            "email_source": "channel_description" if emails else None,
        }

    # ------------------------------------------------------------------
    # Video methods
    # ------------------------------------------------------------------

    def fetch_videos_for_channel(self, channel_id: str) -> list[dict]:
        """Fetch the most recent Entertainment videos for a channel.

        Crawling standard:
        - Category: Entertainment (ID 24)
        - Limit: MAX_VIDEOS_PER_CHANNEL (10) most recent videos
        - Order: date descending (newest first)
        - Non-Entertainment videos returned by search are discarded after fetch
        """
        video_ids = []

        try:
            self._check_quota(100)  # search.list costs 100 units
            response = self.service.search().list(
                part="id",
                channelId=channel_id,
                type="video",
                videoCategoryId=TARGET_CATEGORY_ID,   # Entertainment only
                order="date",                          # newest first
                maxResults=MAX_VIDEOS_PER_CHANNEL,     # stop at 10
            ).execute()
            for item in response.get("items", []):
                video_ids.append(item["id"]["videoId"])
        except HttpError as e:
            if e.status_code == 403:
                raise RuntimeError("YouTube API quota exceeded.") from e
            logger.warning(f"Video search error for channel {channel_id}: {e}")
            return []

        videos = self.fetch_videos(video_ids)

        # Secondary guard: discard any video whose category does not match
        # (search.list category filter is approximate on YouTube's side)
        filtered = [v for v in videos if v.get("category_id") == TARGET_CATEGORY_ID]
        discarded = len(videos) - len(filtered)
        if discarded:
            logger.info(f"  Discarded {discarded} non-Entertainment video(s) for channel {channel_id}")

        return filtered

    def fetch_videos(self, video_ids: list[str]) -> list[dict]:
        """Fetch full video metadata for a list of video IDs."""
        results = []
        for i in range(0, len(video_ids), BATCH_SIZE):
            batch = video_ids[i: i + BATCH_SIZE]
            try:
                self._check_quota(1)
                response = self.service.videos().list(
                    part="snippet,contentDetails,statistics",
                    id=",".join(batch),
                    maxResults=BATCH_SIZE,
                ).execute()
                for item in response.get("items", []):
                    results.append(self._parse_video(item))
            except HttpError as e:
                if e.status_code == 403:
                    raise RuntimeError("YouTube API quota exceeded.") from e
                logger.warning(f"Video fetch error for batch {i}: {e}")
        return results

    def _parse_video(self, item: dict) -> dict:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        thumbnails = snippet.get("thumbnails", {})
        tags = snippet.get("tags", [])
        description = snippet.get("description", "") or ""
        emails = self._extract_emails(description)
        category_id = snippet.get("categoryId", "")

        return {
            "video_id": item.get("id"),
            "channel_id": snippet.get("channelId"),
            "title": snippet.get("title"),
            "description": description[:1000],
            "tags": "|".join(tags) if tags else None,
            "published_at": snippet.get("publishedAt"),
            "duration": content.get("duration"),               # ISO 8601 e.g. PT4M13S
            "view_count": stats.get("viewCount"),
            "like_count": stats.get("likeCount"),              # None if hidden
            "comment_count": stats.get("commentCount"),        # None if disabled
            "thumbnail_default": thumbnails.get("default", {}).get("url"),
            "thumbnail_medium": thumbnails.get("medium", {}).get("url"),
            "thumbnail_high": thumbnails.get("high", {}).get("url"),
            "category_id": category_id,
            "category_name": CATEGORY_MAP.get(category_id),
            "live_broadcast_status": snippet.get("liveBroadcastContent"),
            "email": "|".join(emails) if emails else None,
            "email_source": "video_description" if emails else None,
        }

    # ------------------------------------------------------------------
    # Email extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_emails(text: str) -> list[str]:
        """Extract unique email addresses from text using regex."""
        if not text:
            return []
        return list(set(re.findall(EMAIL_REGEX, text)))
