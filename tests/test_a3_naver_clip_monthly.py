from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook

from src.handlers.a3_naver_clip_monthly import RunMode, run
from tests.fakes import FakeFormRepo, FakeLogRepo, FakeNotifier


def test_a3_confirm_no_applicants_sends_slack_notice() -> None:
    form_repo = FakeFormRepo([])
    slack_notifier = FakeNotifier(send_result=True)
    email_notifier = FakeNotifier(send_result=True)

    result = run(
        form_repo=form_repo,
        log_repo=FakeLogRepo(),
        slack_notifier=slack_notifier,
        email_notifier=email_notifier,
        mode=RunMode.CONFIRM,
        manager_email="manager@example.com",
        target_year=2026,
        target_month=4,
        slack_channel="#naver-clip",
    )

    assert result == {
        "mode": "confirm",
        "applicant_count": 0,
        "action": "no_applicants_notified",
    }
    assert slack_notifier.sent[0]["recipient"] == "#naver-clip"


def test_a3_send_builds_excel_and_emails_attachment() -> None:
    applicants = [
        {
            "channel_name": "Channel A",
            "channel_url": "https://example.com/a",
            "genre": "Drama",
            "manager_name": "Alice",
            "manager_email": "alice@example.com",
            "timestamp": "2026-04-20T10:00:00+09:00",
        }
    ]
    form_repo = FakeFormRepo(applicants)
    email_notifier = FakeNotifier(send_result=True)

    result = run(
        form_repo=form_repo,
        log_repo=FakeLogRepo(),
        slack_notifier=FakeNotifier(send_result=True),
        email_notifier=email_notifier,
        mode=RunMode.SEND,
        manager_email="manager@example.com",
        target_year=2026,
        target_month=4,
    )

    assert result["mode"] == "send"
    assert result["applicant_count"] == 1
    assert result["action"] == "email_sent"
    sent = email_notifier.sent[0]
    assert sent["recipient"] == "manager@example.com"
    attachments = sent["kwargs"]["attachments"]
    assert len(attachments) == 1

    filename, payload = attachments[0]
    assert filename.endswith(".xlsx")

    workbook = load_workbook(BytesIO(payload))
    ws = workbook.active
    assert ws["B2"].value == "Channel A"
    assert ws["C2"].value == "https://example.com/a"
    assert ws["F2"].value == "alice@example.com"
