from __future__ import annotations

from datetime import datetime

import pytest

from src.handlers.a2_work_approval import parse_slack_message, run
from tests.fakes import (
    FakeDriveService,
    FakeNotifier,
    FakeSheetsClient,
    FakeSlackNotifier,
    FakeSpreadsheet,
    FakeWorksheet,
)


SHEET_ID = "creator-sheet"
CHANNEL_NAME = "\uc815\ud638\uc601"
WORK_TITLE = "21\uc138\uae30 \ub300\uad70\ubd80\uc778"


def test_parse_slack_message_extracts_channel_and_work_title() -> None:
    text = (
        '\ucc44\ub110: "\uc815\ud638\uc601" \ub2d8\uc758 \uc2e0\uaddc \uc601\uc0c1 \uc0ac\uc6a9 '
        '\uc694\uccad\uc774 \uc788\uc2b5\ub2c8\ub2e4.\n'
        "21\uc138\uae30 \ub300\uad70\ubd80\uc778"
    )

    assert parse_slack_message(text) == (CHANNEL_NAME, WORK_TITLE)


def test_parse_slack_message_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError):
        parse_slack_message("invalid")


def test_a2_run_happy_path() -> None:
    sheets_client = FakeSheetsClient(
        {
            SHEET_ID: FakeSpreadsheet(
                FakeWorksheet(
                    headers=["\ucc44\ub110\uba85", "\uc774\uba54\uc77c"],
                    rows=[[CHANNEL_NAME, "creator@example.com"]],
                )
            )
        }
    )
    drive_service = FakeDriveService(
        files=[
            {
                "id": "file-123",
                "name": WORK_TITLE,
                "webViewLink": "https://drive.google.com/file-123",
            }
        ]
    )
    email_notifier = FakeNotifier(send_result=True)
    slack_notifier = FakeSlackNotifier(send_result=True, reply_result=True)

    result = run(
        slack_channel_id="C123",
        slack_message_ts="1714000000.000001",
        slack_message_text=(
            f'\ucc44\ub110: "{CHANNEL_NAME}" \ub2d8\uc758 \uc2e0\uaddc \uc601\uc0c1 '
            f"\uc0ac\uc6a9 \uc694\uccad\uc774 \uc788\uc2b5\ub2c8\ub2e4.\n{WORK_TITLE}"
        ),
        sheets_client=sheets_client,
        drive_service=drive_service,
        email_notifier=email_notifier,
        slack_notifier=slack_notifier,
        creator_sheet_id=SHEET_ID,
        drive_folder_id="folder-123",
        sender_email="sender@example.com",
        admin_api_base_url="",
        requested_at=datetime(2026, 4, 24),
    )

    assert result["channel_name"] == CHANNEL_NAME
    assert result["work_title"] == WORK_TITLE
    assert result["applicant_email"] == "creator@example.com"
    assert result["drive_file_id"] == "file-123"
    assert result["email_sent"] is True
    assert result["slack_replied"] is True
    assert result["admin_api_updated"] is False
    assert drive_service.permission_calls[0]["fileId"] == "file-123"
    assert email_notifier.sent[0]["recipient"] == "creator@example.com"
    assert slack_notifier.thread_replies[0]["channel"] == "C123"
