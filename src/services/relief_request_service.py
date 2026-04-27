from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from string import Template
from typing import Callable, Optional
from uuid import uuid4

import pytz

from ..core.interfaces.notifier import INotifier
from ..core.interfaces.repository import IReliefRequestRepository, IRightsHolderDirectory
from ..models import (
    MailTemplate,
    OutboundMail,
    OutboundMailStatus,
    ReliefRequest,
    ReliefRequestItem,
    ReliefRequestStatus,
)

KST = pytz.timezone("Asia/Seoul")


@dataclass
class ReliefRequestDetail:
    request: ReliefRequest
    items: list[ReliefRequestItem]
    outbound_mails: list[OutboundMail]


@dataclass
class RightsHolderMailSendResult:
    request_id: str
    attempted: int
    sent: int
    failed: int
    updated_status: ReliefRequestStatus


class ReliefRequestService:
    def __init__(
        self,
        repo: IReliefRequestRepository,
        rights_holder_directory: IRightsHolderDirectory,
        email_notifier: INotifier,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._repo = repo
        self._rights_holder_directory = rights_holder_directory
        self._email_notifier = email_notifier
        self._clock = clock or (lambda: datetime.now(KST))

    def list_requests(
        self,
        status: Optional[ReliefRequestStatus] = None,
    ) -> list[ReliefRequest]:
        return self._repo.list_requests(status=status)

    def get_request_detail(self, request_id: str) -> ReliefRequestDetail:
        request = self._repo.get_request(request_id)
        if request is None:
            raise ValueError(f"relief request not found: {request_id}")
        return ReliefRequestDetail(
            request=request,
            items=self._repo.list_request_items(request_id),
            outbound_mails=self._repo.list_outbound_mails(request_id),
        )

    def create_request(
        self,
        requester_channel_name: str,
        requester_email: str,
        work_items: list[dict[str, str]],
        requester_notes: str = "",
        submitted_via: str = "web",
    ) -> ReliefRequest:
        now = self._clock()
        request = ReliefRequest(
            request_id=f"relief-{uuid4().hex[:12]}",
            requester_channel_name=requester_channel_name,
            requester_email=requester_email,
            requester_notes=requester_notes,
            status=ReliefRequestStatus.PENDING,
            created_at=now,
            updated_at=now,
            submitted_via=submitted_via,
        )
        items = [
            ReliefRequestItem(
                request_id=request.request_id,
                work_id=item["work_id"],
                work_title=item["work_title"],
                rights_holder_name=item["rights_holder_name"],
                channel_folder_name=item.get("channel_folder_name", requester_channel_name),
            )
            for item in work_items
        ]
        self._repo.save_request(request)
        self._repo.replace_request_items(request.request_id, items)
        return request

    def send_rights_holder_mails(
        self,
        request_id: str,
        template_key: str = "rights_holder_request",
    ) -> RightsHolderMailSendResult:
        detail = self.get_request_detail(request_id)
        request = detail.request
        items = detail.items
        if not items:
            raise ValueError(f"relief request has no items: {request_id}")

        template = self._repo.get_mail_template(template_key)
        if template is None:
            raise ValueError(f"mail template not found: {template_key}")

        work_titles = [item.work_title for item in items]
        contacts = self._rights_holder_directory.resolve_contacts(work_titles)
        if not contacts:
            raise ValueError(f"no rights holder contacts found for request: {request_id}")

        sent = 0
        failed = 0
        for contact in contacts:
            contact_items = [
                item for item in items if item.work_title in set(contact.work_titles)
            ]
            if not contact_items:
                continue
            subject, body = self._render_mail(
                template=template,
                request=request,
                items=contact_items,
                holder_name=contact.holder_name,
            )
            ok = self._email_notifier.send(
                recipient=contact.recipient_email,
                message=body,
                subject=subject,
                html=template.is_html,
            )
            mail = OutboundMail(
                mail_id=f"mail-{uuid4().hex[:12]}",
                request_id=request.request_id,
                holder_name=contact.holder_name,
                recipient_email=contact.recipient_email,
                subject=subject,
                body=body,
                status=OutboundMailStatus.SENT if ok else OutboundMailStatus.FAILED,
                sent_at=self._clock() if ok else None,
                error_message="" if ok else "send returned false",
            )
            self._repo.save_outbound_mail(mail)
            if ok:
                sent += 1
            else:
                failed += 1

        request.status = (
            ReliefRequestStatus.MAIL_SENT
            if failed == 0 and sent > 0
            else ReliefRequestStatus.PENDING
        )
        request.updated_at = self._clock()
        self._repo.update_request(request)
        return RightsHolderMailSendResult(
            request_id=request_id,
            attempted=sent + failed,
            sent=sent,
            failed=failed,
            updated_status=request.status,
        )

    def _render_mail(
        self,
        template: MailTemplate,
        request: ReliefRequest,
        items: list[ReliefRequestItem],
        holder_name: str,
    ) -> tuple[str, str]:
        work_titles = [item.work_title for item in items]
        values = {
            "request_id": request.request_id,
            "requester_channel_name": request.requester_channel_name,
            "requester_email": request.requester_email,
            "requester_notes": request.requester_notes,
            "holder_name": holder_name,
            "work_titles": ", ".join(work_titles),
            "works_bullet_list": "\n".join(f"- {title}" for title in work_titles),
        }
        subject = Template(template.subject_template).safe_substitute(values)
        body = Template(template.body_template).safe_substitute(values)
        return subject, body
