from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Genre(str, Enum):
    """리드 채널 장르.

    값(value)은 Google Sheets '리드' 탭에 한국어로 그대로 저장됩니다.
    저장 형식을 변경하면 기존 시트 데이터가 깨지므로 절대 변경하지 마세요.
    UI 표시용 레이블이 필요하면 .label 프로퍼티를 사용하세요.
    """

    ENTERTAINMENT = "예능"
    DRAMA_MOVIE   = "드라마·영화"
    OTHER         = "기타"

    @property
    def label(self) -> str:
        """사람이 읽기 쉬운 표시 레이블."""
        _labels = {
            Genre.ENTERTAINMENT: "예능",
            Genre.DRAMA_MOVIE:   "드라마·영화",
            Genre.OTHER:         "기타",
        }
        return _labels[self]


class EmailSentStatus(str, Enum):
    """콜드메일 발송 상태.

    값(value)은 Google Sheets '리드' 탭에 한국어로 그대로 저장됩니다.
    저장 형식을 변경하면 기존 시트 데이터가 깨지므로 절대 변경하지 마세요.
    UI 표시용 레이블이 필요하면 .label 프로퍼티를 사용하세요.
    """

    NOT_SENT = "미발송"
    SENT     = "발송완료"
    BOUNCED  = "반송"
    REPLIED  = "응답"

    @property
    def label(self) -> str:
        """사람이 읽기 쉬운 표시 레이블."""
        _labels = {
            EmailSentStatus.NOT_SENT: "미발송",
            EmailSentStatus.SENT:     "발송 완료",
            EmailSentStatus.BOUNCED:  "반송",
            EmailSentStatus.REPLIED:  "응답",
        }
        return _labels[self]


@dataclass
class Lead:
    channel_id: str
    channel_name: str
    channel_url: str
    platform: str  # "youtube"
    genre: Genre
    monthly_shorts_views: int
    subscribers: Optional[int] = None
    email: Optional[str] = None
    email_sent_status: EmailSentStatus = EmailSentStatus.NOT_SENT
    discovered_at: datetime = field(default_factory=datetime.now)
    last_contacted_at: Optional[datetime] = None


@dataclass
class LeadFilter:
    genre: Optional[Genre] = None
    min_monthly_views: int = 0
    email_sent_status: Optional[EmailSentStatus] = None
    platform: Optional[str] = None
