from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4

import pytz

KST = pytz.timezone("Asia/Seoul")


class RepresentativeChannelPlatform(str, Enum):
    NAVER_CLIP = "네이버 클립프로필(네이버 TV 포함)"
    YOUTUBE = "유튜브"
    INSTAGRAM = "인스타그램"
    TIKTOK = "틱톡"
    KAKAO_SHORTFORM = "카카오톡숏폼"


@dataclass
class NaverClipApplicant:
    applicant_id: str
    name: str
    phone_number: str
    naver_id: str
    naver_clip_profile_name: str
    naver_clip_profile_id: str
    representative_channel_name: str
    representative_channel_platform: RepresentativeChannelPlatform
    channel_url: str
    submitted_at: datetime

    @classmethod
    def create(
        cls,
        *,
        name: str,
        phone_number: str,
        naver_id: str,
        naver_clip_profile_name: str,
        naver_clip_profile_id: str,
        representative_channel_name: str,
        representative_channel_platform: RepresentativeChannelPlatform,
        channel_url: str,
    ) -> "NaverClipApplicant":
        return cls(
            applicant_id=f"a3-{uuid4().hex[:12]}",
            name=name.strip(),
            phone_number=phone_number.strip(),
            naver_id=naver_id.strip(),
            naver_clip_profile_name=naver_clip_profile_name.strip(),
            naver_clip_profile_id=naver_clip_profile_id.strip(),
            representative_channel_name=representative_channel_name.strip(),
            representative_channel_platform=representative_channel_platform,
            channel_url=channel_url.strip(),
            submitted_at=datetime.now(KST),
        )
