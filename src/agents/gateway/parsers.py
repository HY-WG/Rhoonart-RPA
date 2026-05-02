"""Raw trigger payload parsers for the agent Input Gateway."""
from __future__ import annotations

import re
from typing import Any

from .models import TaskEnvelope, TriggerType

_A2_CHANNEL_RE = re.compile(r'채널:\s*["“”]?([^"“”\n]+)["“”]?.*영상\s*사용\s*요청')


def parse_slack_work_approval(
    slack_event: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    text = str(slack_event.get("text", ""))
    channel_id = str(slack_event.get("channel", ""))
    message_ts = str(slack_event.get("ts", ""))

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError(f"A-2 Slack message parse failed: expected at least 2 lines, got {len(lines)}")

    match = _A2_CHANNEL_RE.search(lines[0])
    if not match:
        raise ValueError(f"A-2 channel name parse failed: {lines[0]!r}")

    channel_name = match.group(1).strip()
    work_title = lines[1].strip()
    return TaskEnvelope(
        task_id="A-2",
        instruction=f"{channel_name} 채널의 {work_title} 작품 사용 요청을 처리합니다.",
        context={
            "channel_name": channel_name,
            "work_title": work_title,
            "slack_channel_id": channel_id,
            "slack_message_ts": message_ts,
            "dry_run": dry_run,
        },
        trigger_type=TriggerType.SLACK,
        trigger_source=channel_id,
        dry_run=dry_run,
    )


def parse_http_weekly_report(
    body: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="B-2",
        instruction="Naver Clip 주간 성과보고를 실행합니다.",
        context={"rights_holders": body.get("rights_holders", []), "dry_run": dry_run},
        trigger_type=TriggerType.HTTP,
        trigger_source=str(body.get("source", "api")),
        dry_run=dry_run,
    )


def parse_lead_filter(
    body: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="C-1",
        instruction="YouTube Shorts 리드 발굴을 실행합니다.",
        context={"dry_run": dry_run, **{k: v for k, v in body.items() if k != "dry_run"}},
        trigger_type=TriggerType.HTTP if body else TriggerType.CRON,
        trigger_source=str(body.get("source", "cron")),
        dry_run=dry_run,
    )


def parse_cold_email(
    body: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="C-2",
        instruction="조건에 맞는 리드 채널에 콜드메일을 발송하거나 미리보기합니다.",
        context={
            "batch_size": body.get("batch_size", 10),
            "genre": body.get("genre"),
            "min_monthly_views": body.get("min_monthly_views", 0),
            "platform": body.get("platform"),
            "dry_run": dry_run,
        },
        trigger_type=TriggerType.HTTP,
        trigger_source=str(body.get("source", "api")),
        dry_run=dry_run,
    )


def parse_manual(
    task_id: str,
    instruction: str,
    context: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        instruction=instruction,
        context=context or {},
        trigger_type=TriggerType.MANUAL,
        trigger_source="dashboard",
        dry_run=dry_run,
    )


def parse_email_admin_channel_invite(
    message: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    subject = str(message.get("subject", "")).strip()
    recipient = str(message.get("recipient", "")).strip()
    accept_url = str(message.get("accept_url", "")).strip()
    sender = str(message.get("sender", "")).strip()
    snippet = str(message.get("snippet", "")).strip()

    if not subject:
        raise ValueError("A-0 email parse failed: subject is required")
    if not accept_url:
        raise ValueError("A-0 email parse failed: accept_url is required")

    return TaskEnvelope(
        task_id="A-0",
        instruction=(
            f"관리자 메일함에서 '{subject}' 메일을 감지했습니다. "
            "초대 수락 링크를 열기 전 사람 승인 체크포인트를 생성합니다."
        ),
        context={
            "recipient": recipient,
            "sender": sender,
            "subject": subject,
            "accept_url": accept_url,
            "snippet": snippet,
            "dry_run": dry_run,
        },
        trigger_type=TriggerType.EMAIL,
        trigger_source=sender or "mailbox",
        dry_run=dry_run,
    )
