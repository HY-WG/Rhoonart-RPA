from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ChannelStat:
    channel_id: str
    channel_name: str
    platform: str  # "naver_clip"
    subscribers: Optional[int] = None
    total_views: Optional[int] = None
    weekly_views: Optional[int] = None
    video_count: Optional[int] = None
    crawled_at: datetime = field(default_factory=datetime.now)


@dataclass
class RightsHolder:
    holder_id: str
    name: str
    email: Optional[str] = None
    slack_channel: Optional[str] = None
    dashboard_url: Optional[str] = None
    channel_ids: list[str] = field(default_factory=list)
