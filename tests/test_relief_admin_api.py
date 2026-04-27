from __future__ import annotations

from fastapi.testclient import TestClient

from src.backoffice.app import build_app
from src.models import MailTemplate, RightsHolderContact
from src.services import ReliefRequestService
from tests.fakes import FakeNotifier
from tests.relief_fakes import FakeReliefRequestRepository, FakeRightsHolderDirectory


def _build_client() -> tuple[TestClient, FakeReliefRequestRepository, FakeNotifier]:
    repo = FakeReliefRequestRepository()
    repo.save_mail_template(
        MailTemplate(
            template_key="rights_holder_request",
            subject_template="[Rhoonart] ${requester_channel_name}",
            body_template="Works\n${works_bullet_list}",
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
                    recipient_email="rights@example.com",
                    work_titles=["Work Alpha"],
                )
            ]
        ),
        email_notifier=notifier,
    )
    service.create_request(
        requester_channel_name="Admin Test Channel",
        requester_email="creator@example.com",
        requester_notes="Admin review",
        work_items=[
            {
                "work_id": "work-1",
                "work_title": "Work Alpha",
                "rights_holder_name": "Rights A",
                "channel_folder_name": "Admin Test Channel",
            }
        ],
    )
    app = build_app(service=service)
    client = TestClient(app)
    return client, repo, notifier


def test_admin_can_list_and_read_relief_requests() -> None:
    client, _, _ = _build_client()

    list_response = client.get("/api/admin/relief-requests")
    request_id = list_response.json()[0]["request_id"]
    detail_response = client.get(f"/api/admin/relief-requests/{request_id}")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["items"][0]["work_title"] == "Work Alpha"


def test_admin_can_send_rights_holder_mail() -> None:
    client, repo, notifier = _build_client()
    request_id = client.get("/api/admin/relief-requests").json()[0]["request_id"]

    response = client.post(
        f"/api/admin/relief-requests/{request_id}/send-mails",
        json={"template_key": "rights_holder_request"},
    )

    assert response.status_code == 200
    assert response.json()["sent"] == 1
    assert response.json()["updated_status"] == "mail_sent"
    assert len(notifier.sent) == 1
    assert repo.list_outbound_mails(request_id)[0].recipient_email == "rights@example.com"
