from __future__ import annotations

from typing import Any

from src.agents.gateway.parsers import parse_email_admin_channel_invite
from src.config import settings
from src.core.interfaces.notifier import INotifier

from .models import A0AutomationPlan
from .repository import IAdminInviteInboxRepository


class A0AdminChannelApprovalPlanner:
    def __init__(
        self,
        inbox_repo: IAdminInviteInboxRepository,
        mail_notifier: INotifier,
        *,
        admin_email: str | None = None,
        subject_query: str = "YouTube 채널 액세스를 위한 초대",
    ) -> None:
        self._repo = inbox_repo
        self._notifier = mail_notifier
        self._admin_email = admin_email or settings.CONFIG_ADMIN_EMAIL
        self._subject_query = subject_query

    def poll_and_plan(self, *, dry_run: bool = True) -> list[A0AutomationPlan]:
        invites = self._repo.list_pending_invites(
            admin_email=self._admin_email,
            subject_query=self._subject_query,
        )
        plans: list[A0AutomationPlan] = []
        for invite in invites:
            envelope = parse_email_admin_channel_invite(
                invite.to_gateway_payload(),
                dry_run=dry_run,
            )
            plans.append(A0AutomationPlan(mail=invite, envelope=envelope.to_dict()))
            self._notifier.send(
                self._admin_email,
                (
                    f"[A-0] 채널 초대 메일 감지\n"
                    f"- 제목: {invite.subject}\n"
                    f"- 수신시각: {invite.received_at.isoformat()}\n"
                    f"- 수락 링크: {invite.accept_url}"
                ),
                subject="[A-0] YouTube 채널 초대 감지",
            )
        return plans

    def design_review(self) -> dict[str, Any]:
        return {
            "input_gateway": {
                "type": "email",
                "polling_target": self._admin_email,
                "subject_query": self._subject_query,
                "normalized_intent": "approve_admin_channel_invite",
            },
            "tool_registry": [
                "poll_admin_invite_mailbox",
                "open_invite_link_with_playwright",
                "sign_in_labelly_admin",
                "confirm_channel_access",
            ],
            "requires_human_approval": [
                "메일 본문 검토",
                "실제 초대 수락 링크 클릭 직전",
                "최종 레이블리 승인 직전",
            ],
            "env_keys": ["CONFIG_ADMIN_EMAIL"],
        }
