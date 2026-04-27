from __future__ import annotations

from datetime import datetime

import pytz

from src.models import MailTemplate, ReliefRequestStatus, RightsHolderContact
from src.services import ReliefRequestService
from tests.fakes import FakeNotifier
from tests.relief_fakes import FakeReliefRequestRepository, FakeRightsHolderDirectory

KST = pytz.timezone("Asia/Seoul")


def test_send_rights_holder_mails_groups_items_and_updates_status() -> None:
    repo = FakeReliefRequestRepository()
    repo.save_mail_template(
        MailTemplate(
            template_key="rights_holder_request",
            subject_template="[Rhoonart] ${requester_channel_name} relief request",
            body_template="Holder: ${holder_name}\n${works_bullet_list}",
            is_html=False,
        )
    )
    notifier = FakeNotifier(send_result=True)
    service = ReliefRequestService(
        repo=repo,
        rights_holder_directory=FakeRightsHolderDirectory(
            [
                RightsHolderContact(
                    holder_id="holder-1",
                    holder_name="Rights A",
                    recipient_email="a@example.com",
                    work_titles=["Work Alpha", "Work Beta"],
                ),
                RightsHolderContact(
                    holder_id="holder-2",
                    holder_name="Rights B",
                    recipient_email="b@example.com",
                    work_titles=["Work Gamma"],
                ),
            ]
        ),
        email_notifier=notifier,
        clock=lambda: KST.localize(datetime(2026, 4, 24, 12, 0)),
    )
    request = service.create_request(
        requester_channel_name="Channel A",
        requester_email="creator@example.com",
        requester_notes="Please review",
        work_items=[
            {"work_id": "w1", "work_title": "Work Alpha", "rights_holder_name": "Rights A"},
            {"work_id": "w2", "work_title": "Work Gamma", "rights_holder_name": "Rights B"},
        ],
    )

    result = service.send_rights_holder_mails(request.request_id)

    assert result.attempted == 2
    assert result.sent == 2
    assert result.failed == 0
    assert result.updated_status == ReliefRequestStatus.MAIL_SENT
    assert len(notifier.sent) == 2
    assert "Work Alpha" in notifier.sent[0]["message"] or "Work Alpha" in notifier.sent[1]["message"]
    assert repo.get_request(request.request_id).status == ReliefRequestStatus.MAIL_SENT
