from __future__ import annotations

from datetime import datetime, timezone

from src.agents.a0.models import AdminInviteMail
from src.agents.a0.service import A0AdminChannelApprovalPlanner


class FakeMailNotifier:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    def send(self, recipient: str, message: str, **kwargs: str) -> bool:
        self.sent.append(
            {
                "recipient": recipient,
                "message": message,
                "subject": kwargs.get("subject", ""),
            }
        )
        return True

    def send_error(self, task_id: str, error: Exception, context: dict | None = None) -> bool:
        return True


class FakeInboxRepository:
    def __init__(self, invites: list[AdminInviteMail]) -> None:
        self.invites = list(invites)
        self.marked: list[str] = []
        self.calls: list[tuple[str, str]] = []

    def list_pending_invites(
        self,
        *,
        admin_email: str,
        subject_query: str,
    ) -> list[AdminInviteMail]:
        self.calls.append((admin_email, subject_query))
        return [
            invite
            for invite in self.invites
            if invite.recipient == admin_email and subject_query in invite.subject
        ]

    def mark_processed(self, message_id: str) -> None:
        self.marked.append(message_id)


def test_planner_creates_a0_envelope_and_notifies() -> None:
    invite = AdminInviteMail(
        message_id="msg-001",
        subject="YouTube 채널 액세스를 위한 초대",
        sender="youtube-noreply@google.com",
        recipient="hoyoungy2@gmail.com",
        received_at=datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc),
        accept_url="https://accounts.google.com/accept-invite",
        snippet="채널 액세스를 수락하세요.",
    )
    inbox = FakeInboxRepository([invite])
    notifier = FakeMailNotifier()
    planner = A0AdminChannelApprovalPlanner(
        inbox,
        notifier,
        admin_email="hoyoungy2@gmail.com",
    )

    plans = planner.poll_and_plan(dry_run=True)

    assert len(plans) == 1
    assert plans[0].mail.message_id == "msg-001"
    assert plans[0].envelope["task_id"] == "A-0"
    assert plans[0].envelope["trigger_type"] == "email"
    assert plans[0].envelope["context"]["accept_url"] == "https://accounts.google.com/accept-invite"
    assert notifier.sent[0]["recipient"] == "hoyoungy2@gmail.com"
    assert "[A-0]" in notifier.sent[0]["subject"]


def test_design_review_mentions_input_gateway_and_env_key() -> None:
    planner = A0AdminChannelApprovalPlanner(
        FakeInboxRepository([]),
        FakeMailNotifier(),
        admin_email="hoyoungy2@gmail.com",
    )

    review = planner.design_review()

    assert review["input_gateway"]["type"] == "email"
    assert "CONFIG_ADMIN_EMAIL" in review["env_keys"]
    assert "open_invite_link_with_playwright" in review["tool_registry"]
