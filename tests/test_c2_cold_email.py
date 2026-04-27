from __future__ import annotations

from datetime import datetime

from src.handlers.c2_cold_email import run
from src.models.lead import EmailSentStatus, Genre, Lead
from tests.fakes import FakeLeadRepo, FakeLogRepo, FakeNotifier


def make_lead(
    channel_id: str,
    *,
    email: str | None,
    status: EmailSentStatus = EmailSentStatus.NOT_SENT,
    monthly_views: int = 25_000_000,
) -> Lead:
    return Lead(
        channel_id=channel_id,
        channel_name=f"Channel {channel_id}",
        channel_url=f"https://youtube.com/channel/{channel_id}",
        platform="youtube",
        genre=Genre.DRAMA_MOVIE,
        monthly_shorts_views=monthly_views,
        subscribers=1000,
        email=email,
        email_sent_status=status,
        discovered_at=datetime(2026, 4, 24),
    )


def test_c2_sends_updates_and_skips_missing_email() -> None:
    repo = FakeLeadRepo(
        [
            make_lead("one", email="one@example.com"),
            make_lead("two", email=None),
            make_lead("three", email="three@example.com"),
        ]
    )
    email_notifier = FakeNotifier(send_result=True)

    result = run(
        lead_repo=repo,
        log_repo=FakeLogRepo(),
        email_notifier=email_notifier,
        slack_notifier=FakeNotifier(send_result=True),
        sender_name="Rhoonart",
        batch_size=2,
        platform="youtube",
    )

    assert result == {
        "sent": 1,
        "bounced": 0,
        "skipped_no_email": 1,
        "skipped_by_filter": 1,
    }
    assert repo.status_updates == [("one", EmailSentStatus.SENT.value)]


def test_c2_marks_bounced_on_send_failure() -> None:
    repo = FakeLeadRepo([make_lead("one", email="one@example.com")])
    email_notifier = FakeNotifier(send_result=False)

    result = run(
        lead_repo=repo,
        log_repo=FakeLogRepo(),
        email_notifier=email_notifier,
        slack_notifier=FakeNotifier(send_result=True),
        sender_name="Rhoonart",
        batch_size=10,
        platform="youtube",
    )

    assert result["sent"] == 0
    assert result["bounced"] == 1
    assert repo.status_updates == [("one", EmailSentStatus.BOUNCED.value)]
