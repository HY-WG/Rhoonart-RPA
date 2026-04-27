from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ReliefRequestStatus(str, Enum):
    """정산 요청 처리 단계.

    값(value)은 영어 소문자로 Supabase DB에 저장됩니다.
    Supabase(PostgreSQL) 스키마와 일치해야 하므로 절대 변경하지 마세요.
    (참고: creator/work_request 모델의 한국어 Enum과 다른 이유는
     해당 모델이 Google Sheets 저장용, 이 모델은 Supabase 저장용이기 때문입니다.)
    """

    SUBMITTED        = "submitted"
    PENDING          = "pending"
    MAIL_SENT        = "mail_sent"
    REPLY_RECEIVED   = "reply_received"
    READY_TO_FORWARD = "ready_to_forward"
    FORWARDED        = "forwarded"
    COMPLETED        = "completed"
    REJECTED         = "rejected"

    @property
    def label(self) -> str:
        """사람이 읽기 쉬운 한국어 표시 레이블."""
        _labels = {
            ReliefRequestStatus.SUBMITTED:        "제출됨",
            ReliefRequestStatus.PENDING:          "검토 중",
            ReliefRequestStatus.MAIL_SENT:        "메일 발송 완료",
            ReliefRequestStatus.REPLY_RECEIVED:   "회신 수신",
            ReliefRequestStatus.READY_TO_FORWARD: "전달 준비",
            ReliefRequestStatus.FORWARDED:        "전달 완료",
            ReliefRequestStatus.COMPLETED:        "처리 완료",
            ReliefRequestStatus.REJECTED:         "반려",
        }
        return _labels[self]


class OutboundMailStatus(str, Enum):
    """외부 발송 메일 상태.

    값(value)은 영어 소문자로 Supabase DB에 저장됩니다.
    Supabase(PostgreSQL) 스키마와 일치해야 하므로 절대 변경하지 마세요.
    """

    PENDING = "pending"
    SENT    = "sent"
    FAILED  = "failed"

    @property
    def label(self) -> str:
        """사람이 읽기 쉬운 한국어 표시 레이블."""
        _labels = {
            OutboundMailStatus.PENDING: "발송 대기",
            OutboundMailStatus.SENT:    "발송 완료",
            OutboundMailStatus.FAILED:  "발송 실패",
        }
        return _labels[self]


@dataclass
class ReliefRequest:
    request_id: str
    requester_channel_name: str
    requester_email: str
    requester_notes: str = ""
    status: ReliefRequestStatus = ReliefRequestStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    submitted_via: str = "web"
    row_index: Optional[int] = None


@dataclass
class ReliefRequestItem:
    request_id: str
    work_id: str
    work_title: str
    rights_holder_name: str
    channel_folder_name: str = ""


@dataclass
class RightsHolderContact:
    holder_id: str
    holder_name: str
    recipient_email: str
    work_titles: list[str] = field(default_factory=list)
    template_key: str = "rights_holder_request"


@dataclass
class MailTemplate:
    template_key: str
    subject_template: str
    body_template: str
    is_html: bool = True


@dataclass
class OutboundMail:
    mail_id: str
    request_id: str
    holder_name: str
    recipient_email: str
    subject: str
    body: str
    status: OutboundMailStatus
    sent_at: Optional[datetime] = None
    error_message: str = ""


@dataclass
class UploadedDocument:
    document_id: str
    request_id: str
    holder_name: str
    drive_file_id: str
    drive_file_url: str
    stored_path: str
    uploaded_at: Optional[datetime] = None

