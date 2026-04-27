from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.core.interfaces.repository import IReliefRequestRepository, IRightsHolderDirectory
from src.models import (
    MailTemplate,
    OutboundMail,
    ReliefRequest,
    ReliefRequestItem,
    ReliefRequestStatus,
    RightsHolderContact,
    UploadedDocument,
)


class FakeReliefRequestRepository(IReliefRequestRepository):
    def __init__(self) -> None:
        self.requests: dict[str, ReliefRequest] = {}
        self.items: dict[str, list[ReliefRequestItem]] = {}
        self.templates: dict[str, MailTemplate] = {}
        self.outbound_mails: dict[str, list[OutboundMail]] = {}
        self.documents: dict[str, list[UploadedDocument]] = {}

    def list_requests(
        self,
        status: Optional[ReliefRequestStatus] = None,
    ) -> list[ReliefRequest]:
        requests = list(self.requests.values())
        if status is not None:
            requests = [request for request in requests if request.status == status]
        return list(requests)

    def get_request(self, request_id: str) -> ReliefRequest | None:
        return self.requests.get(request_id)

    def save_request(self, request: ReliefRequest) -> None:
        self.requests[request.request_id] = request

    def update_request(self, request: ReliefRequest) -> None:
        self.requests[request.request_id] = request

    def list_request_items(self, request_id: str) -> list[ReliefRequestItem]:
        return list(self.items.get(request_id, []))

    def replace_request_items(self, request_id: str, items: list[ReliefRequestItem]) -> None:
        self.items[request_id] = list(items)

    def get_mail_template(self, template_key: str) -> MailTemplate | None:
        return self.templates.get(template_key)

    def save_mail_template(self, template: MailTemplate) -> None:
        self.templates[template.template_key] = template

    def list_outbound_mails(self, request_id: str) -> list[OutboundMail]:
        return list(self.outbound_mails.get(request_id, []))

    def save_outbound_mail(self, mail: OutboundMail) -> None:
        self.outbound_mails.setdefault(mail.request_id, []).append(mail)

    def save_uploaded_document(self, document: UploadedDocument) -> None:
        self.documents.setdefault(document.request_id, []).append(document)


class FakeRightsHolderDirectory(IRightsHolderDirectory):
    def __init__(self, contacts: list[RightsHolderContact]) -> None:
        self.contacts = contacts
        self.seen_titles: list[list[str]] = []

    def resolve_contacts(self, work_titles: list[str]) -> list[RightsHolderContact]:
        requested = set(work_titles)
        self.seen_titles.append(list(work_titles))
        return [
            RightsHolderContact(
                holder_id=contact.holder_id,
                holder_name=contact.holder_name,
                recipient_email=contact.recipient_email,
                work_titles=[title for title in contact.work_titles if title in requested],
                template_key=contact.template_key,
            )
            for contact in self.contacts
            if any(title in requested for title in contact.work_titles)
        ]
