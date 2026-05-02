from __future__ import annotations

import json

from src.agents.approval.in_memory import InMemoryApprovalRepository
from src.agents.approval.queue import ApprovalQueue
from src.agents.gateway.classifier import classify_email_message
from src.agents.gateway.gateway import InputGateway
from src.agents.repository import InMemoryAgentTraceRepository
from src.agents.runtime.agent import FakeLLMClient, RhoArtAgent
from src.agents.tools.definitions import tool_registry
from src.core.notifiers.null_notifier import NullNotifier


def _build_test_gateway(response: dict) -> InputGateway:
    approval_repo = InMemoryApprovalRepository()
    approval_queue = ApprovalQueue(
        repo=approval_repo,
        notifier=NullNotifier(),
        tool_registry=tool_registry,
    )
    agent = RhoArtAgent(
        tool_registry=tool_registry,
        approval_queue=approval_queue,
        trace_repo=InMemoryAgentTraceRepository(),
        llm_client=FakeLLMClient([json.dumps(response, ensure_ascii=False)]),
    )
    return InputGateway(agent)


def test_email_classifier_detects_youtube_admin_invite() -> None:
    assert classify_email_message(
        "YouTube 채널 액세스를 위한 초대",
        "youtube-noreply@example.com",
    ) == "A-0"


def test_a0_email_gateway_runs_dry_run_preview() -> None:
    gateway = _build_test_gateway({
        "reasoning": "A-0 초대 메일이므로 승인 전 미리보기를 생성합니다.",
        "selected_tool": "run_a0_admin_channel_approval",
        "tool_input": {
            "subject": "YouTube 채널 액세스를 위한 초대",
            "sender": "youtube-noreply@example.com",
            "recipient": "admin@example.com",
            "accept_url": "https://accounts.google.com/invite",
            "snippet": "채널 초대 수락",
            "dry_run": True,
        },
        "requires_approval": False,
        "risk_level": "critical",
        "confidence": 0.95,
    })

    result = gateway.handle_email({
        "subject": "YouTube 채널 액세스를 위한 초대",
        "sender": "youtube-noreply@example.com",
        "recipient": "admin@example.com",
        "accept_url": "https://accounts.google.com/invite",
        "snippet": "채널 초대 수락",
    }, dry_run=True)

    assert result["status"] == "completed"
    assert result["last_output"]["task_id"] == "A-0"
    assert result["last_output"]["dry_run"] is True
    assert "before_invite_link_click" in result["last_output"]["required_checkpoints"]


def test_a0_real_run_pauses_for_approval() -> None:
    gateway = _build_test_gateway({
        "reasoning": "초대 링크 클릭 전 사람 승인이 필요합니다.",
        "selected_tool": "run_a0_admin_channel_approval",
        "tool_input": {
            "subject": "YouTube 채널 액세스를 위한 초대",
            "sender": "youtube-noreply@example.com",
            "recipient": "admin@example.com",
            "accept_url": "https://accounts.google.com/invite",
            "snippet": "채널 초대 수락",
            "dry_run": False,
        },
        "requires_approval": True,
        "risk_level": "critical",
        "confidence": 0.95,
    })

    result = gateway.handle_email({
        "subject": "YouTube 채널 액세스를 위한 초대",
        "sender": "youtube-noreply@example.com",
        "recipient": "admin@example.com",
        "accept_url": "https://accounts.google.com/invite",
        "snippet": "채널 초대 수락",
    }, dry_run=False)

    assert result["status"] == "awaiting_approval"
    assert result["tool"] == "run_a0_admin_channel_approval"
    assert result["approval_id"].startswith("apv-")
