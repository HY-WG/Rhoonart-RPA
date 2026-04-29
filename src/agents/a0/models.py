from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class AdminInviteMail:
    message_id: str
    subject: str
    sender: str
    recipient: str
    received_at: datetime
    accept_url: str
    snippet: str = ""

    def to_gateway_payload(self) -> dict[str, str]:
        return {
            "message_id": self.message_id,
            "subject": self.subject,
            "sender": self.sender,
            "recipient": self.recipient,
            "accept_url": self.accept_url,
            "snippet": self.snippet,
            "received_at": self.received_at.isoformat(),
        }


@dataclass(frozen=True)
class A0AutomationPlan:
    mail: AdminInviteMail
    envelope: dict[str, object]
    suggested_tool_name: str = "run_a0_admin_channel_approval"
    requires_human_approval: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, object]:
        return {
            "mail": self.mail.to_gateway_payload(),
            "envelope": self.envelope,
            "suggested_tool_name": self.suggested_tool_name,
            "requires_human_approval": self.requires_human_approval,
            "created_at": self.created_at.isoformat(),
            "tool_sequence": [
                "poll_admin_invite_mailbox",
                "open_invite_link_with_playwright",
                "sign_in_labelly_admin",
                "confirm_channel_access",
            ],
        }
