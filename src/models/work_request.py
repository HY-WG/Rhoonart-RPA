from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class RequestStatus(str, Enum):
    """작품사용신청 처리 상태.

    값(value)은 Google Sheets '작품사용신청' 탭에 한국어로 그대로 저장됩니다.
    저장 형식을 변경하면 기존 시트 데이터가 깨지므로 절대 변경하지 마세요.
    UI 표시용 레이블이 필요하면 .label 프로퍼티를 사용하세요.
    """

    PENDING  = "대기중"
    APPROVED = "승인"
    REJECTED = "반려"

    @property
    def label(self) -> str:
        """사람이 읽기 쉬운 표시 레이블."""
        _labels = {
            RequestStatus.PENDING:  "대기 중",
            RequestStatus.APPROVED: "승인",
            RequestStatus.REJECTED: "반려",
        }
        return _labels[self]


@dataclass
class WorkRequest:
    request_id: str
    applicant_email: str
    drive_file_id: str
    drive_file_name: str
    slack_message_ts: str
    slack_channel_id: str
    status: RequestStatus = RequestStatus.PENDING
    requested_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    row_index: Optional[int] = None
