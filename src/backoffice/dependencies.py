from __future__ import annotations

from datetime import datetime

import pytz

from ..core.notifiers.null_notifier import NullNotifier
from ..models import MailTemplate, ReliefRequestStatus, RightsHolderContact
from ..services import ReliefRequestService
from .in_memory import InMemoryReliefRequestRepository, InMemoryRightsHolderDirectory

KST = pytz.timezone("Asia/Seoul")


def build_demo_service() -> ReliefRequestService:
    repo = InMemoryReliefRequestRepository()
    repo.save_mail_template(
        MailTemplate(
            template_key="rights_holder_request",
            subject_template="[루나트] ${requester_channel_name} 채널 수익화 소명 요청",
            body_template=(
                "<p>${holder_name} 담당자님 안녕하세요.</p>"
                "<p>${requester_channel_name} 채널의 수익화 소명 요청 건을 전달드립니다.</p>"
                "<p>신청 작품 목록</p>"
                "<pre>${works_bullet_list}</pre>"
                "<p>신청자 메일: ${requester_email}</p>"
                "<p>추가 메모: ${requester_notes}</p>"
            ),
            is_html=True,
        )
    )
    service = ReliefRequestService(
        repo=repo,
        rights_holder_directory=InMemoryRightsHolderDirectory(
            [
                RightsHolderContact(
                    holder_id="holder-1",
                    holder_name="Rights A",
                    recipient_email="rights-a@example.com",
                    work_titles=["신병", "재벌집 막내아들"],
                ),
                RightsHolderContact(
                    holder_id="holder-2",
                    holder_name="Rights B",
                    recipient_email="rights-b@example.com",
                    work_titles=["청설"],
                ),
            ]
        ),
        email_notifier=NullNotifier(),
    )
    request = service.create_request(
        requester_channel_name="예시 채널",
        requester_email="creator@example.com",
        requester_notes="수익화 제한 해제 요청",
        submitted_via="web",
        work_items=[
            {
                "work_id": "work-1",
                "work_title": "신병",
                "rights_holder_name": "Rights A",
                "channel_folder_name": "예시 채널",
            },
            {
                "work_id": "work-2",
                "work_title": "청설",
                "rights_holder_name": "Rights B",
                "channel_folder_name": "예시 채널",
            },
        ],
    )
    request.status = ReliefRequestStatus.PENDING
    request.updated_at = datetime.now(KST)
    repo.update_request(request)
    return service


_service = build_demo_service()


def get_relief_request_service() -> ReliefRequestService:
    return _service
