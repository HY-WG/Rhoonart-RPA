from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Optional

from ..core.interfaces.repository import IReliefRequestRepository, IRightsHolderDirectory
from ..models import (
    MailTemplate,
    OutboundMail,
    ReliefRequest,
    ReliefRequestItem,
    ReliefRequestStatus,
    RightsHolderContact,
    UploadedDocument,
)


class InMemoryReliefRequestRepository(IReliefRequestRepository):
    def __init__(self) -> None:
        self._requests: dict[str, ReliefRequest] = {}
        self._items: dict[str, list[ReliefRequestItem]] = {}
        self._templates: dict[str, MailTemplate] = {}
        self._outbound_mails: dict[str, list[OutboundMail]] = {}
        self._documents: dict[str, list[UploadedDocument]] = {}

    def list_requests(
        self,
        status: Optional[ReliefRequestStatus] = None,
    ) -> list[ReliefRequest]:
        requests = list(self._requests.values())
        if status is not None:
            requests = [request for request in requests if request.status == status]
        return sorted(
            requests,
            key=lambda request: request.created_at or datetime.min,
            reverse=True,
        )

    def get_request(self, request_id: str) -> Optional[ReliefRequest]:
        return self._requests.get(request_id)

    def save_request(self, request: ReliefRequest) -> None:
        self._requests[request.request_id] = request

    def update_request(self, request: ReliefRequest) -> None:
        self._requests[request.request_id] = request

    def list_request_items(self, request_id: str) -> list[ReliefRequestItem]:
        return list(self._items.get(request_id, []))

    def replace_request_items(self, request_id: str, items: list[ReliefRequestItem]) -> None:
        self._items[request_id] = list(items)

    def get_mail_template(self, template_key: str) -> Optional[MailTemplate]:
        return self._templates.get(template_key)

    def save_mail_template(self, template: MailTemplate) -> None:
        self._templates[template.template_key] = template

    def list_outbound_mails(self, request_id: str) -> list[OutboundMail]:
        return list(self._outbound_mails.get(request_id, []))

    def save_outbound_mail(self, mail: OutboundMail) -> None:
        self._outbound_mails.setdefault(mail.request_id, []).append(mail)

    def save_uploaded_document(self, document: UploadedDocument) -> None:
        self._documents.setdefault(document.request_id, []).append(document)


class InMemoryRightsHolderDirectory(IRightsHolderDirectory):
    def __init__(self, contacts: list[RightsHolderContact]) -> None:
        self._contacts = list(contacts)

    def resolve_contacts(self, work_titles: list[str]) -> list[RightsHolderContact]:
        requested = set(work_titles)
        resolved: list[RightsHolderContact] = []
        for contact in self._contacts:
            matched_titles = [title for title in contact.work_titles if title in requested]
            if matched_titles:
                resolved.append(replace(contact, work_titles=matched_titles))
        return resolved
