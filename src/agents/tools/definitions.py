"""Rhoonart RPA tool definitions for the agent runtime.

The agent decides which tool to call, but the deterministic Lambda handlers and
service modules still perform the business work.
"""
from __future__ import annotations

import importlib
import json
from typing import Any

from pydantic import BaseModel, Field

from .registry import RiskLevel, ToolRegistry

tool_registry = ToolRegistry()


def _call_lambda(module_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    mod = importlib.import_module(module_name)
    raw = mod.handler(payload, None)
    if isinstance(raw, dict) and "statusCode" in raw and "body" in raw:
        body = raw.get("body")
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"statusCode": raw.get("statusCode"), "raw_body": body}
        return body or {}
    return raw if isinstance(raw, dict) else {"result": str(raw)}


class A0AdminChannelApprovalInput(BaseModel):
    subject: str = Field(description="Invite email subject")
    sender: str = Field(default="", description="Invite email sender")
    recipient: str = Field(default="", description="Admin recipient email")
    accept_url: str = Field(description="Invite accept URL")
    snippet: str = Field(default="", description="Email body preview")
    dry_run: bool = Field(default=True)
    approval_stage: str = Field(
        default="mail_review",
        description="mail_review | before_link_open | before_final_confirm",
    )


@tool_registry.register(
    name="run_a0_admin_channel_approval",
    description="Review a YouTube admin channel invite and prepare the approval-gated browser flow.",
    input_model=A0AdminChannelApprovalInput,
    risk_level=RiskLevel.CRITICAL,
    requires_approval=True,
    supports_dry_run=True,
    browser_supported=True,
    tags=["a0", "email", "browser", "approval"],
)
def run_a0_admin_channel_approval(inp: A0AdminChannelApprovalInput) -> dict[str, Any]:
    checkpoints = [
        "mail_body_review",
        "before_invite_link_click",
        "before_labelly_final_confirm",
    ]
    return {
        "status": "preview" if inp.dry_run else "awaiting_approval",
        "dry_run": inp.dry_run,
        "task_id": "A-0",
        "subject": inp.subject,
        "sender": inp.sender,
        "recipient": inp.recipient,
        "accept_url": inp.accept_url,
        "approval_stage": inp.approval_stage,
        "required_checkpoints": checkpoints,
        "planned_tool_sequence": [
            "poll_admin_invite_mailbox",
            "open_invite_link_with_playwright",
            "sign_in_labelly_admin",
            "confirm_channel_access",
        ],
        "note": (
            "A-0 is intentionally approval-gated. Browser execution should resume "
            "only after an operator approves the current checkpoint."
        ),
    }


class A2WorkApprovalInput(BaseModel):
    channel_name: str
    work_title: str
    slack_channel_id: str = ""
    slack_message_ts: str = ""
    dry_run: bool = True


@tool_registry.register(
    name="run_a2_work_approval",
    description="Process a work usage approval request from Slack.",
    input_model=A2WorkApprovalInput,
    risk_level=RiskLevel.HIGH,
    requires_approval=True,
    tags=["a2", "approval", "drive", "email", "slack"],
)
def run_a2_work_approval(inp: A2WorkApprovalInput) -> dict[str, Any]:
    if inp.dry_run:
        return {
            "status": "preview",
            "dry_run": True,
            "channel_name": inp.channel_name,
            "work_title": inp.work_title,
            "note": "No Drive permission or email is sent in dry-run.",
        }
    event = {
        "body": json.dumps({
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel": inp.slack_channel_id,
                "ts": inp.slack_message_ts,
                "text": f'채널: "{inp.channel_name}" 신규 영상 사용 요청이 있습니다.\n{inp.work_title}',
            },
        }, ensure_ascii=False),
    }
    return _call_lambda("lambda.a2_work_approval_handler", event)


class A3NaverClipMonthlyInput(BaseModel):
    mode: str = "confirm"
    dry_run: bool = True


@tool_registry.register(
    name="run_a3_naver_clip_monthly",
    description="Collect monthly Naver Clip applicants and optionally send the monthly report.",
    input_model=A3NaverClipMonthlyInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["a3", "naver", "email", "sheets"],
)
def run_a3_naver_clip_monthly(inp: A3NaverClipMonthlyInput) -> dict[str, Any]:
    mode = "confirm" if inp.dry_run else inp.mode
    return _call_lambda("lambda.a3_naver_clip_monthly_handler", {"mode": mode})


class B2WeeklyReportInput(BaseModel):
    source: str = "agent"
    send_notifications: bool = False
    dry_run: bool = True


@tool_registry.register(
    name="run_b2_weekly_report",
    description="Run the Naver Clip performance report workflow.",
    input_model=B2WeeklyReportInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["naver", "report", "email"],
)
def run_b2_weekly_report(inp: B2WeeklyReportInput) -> dict[str, Any]:
    if inp.dry_run:
        return {
            "status": "preview",
            "dry_run": True,
            "source": inp.source,
            "send_notifications": inp.send_notifications,
        }
    return _call_lambda(
        "lambda.b2_weekly_report_handler",
        {"source": inp.source, "send_notifications": inp.send_notifications},
    )


class C1LeadDiscoveryInput(BaseModel):
    source: str = "agent"
    work_title: str | None = None
    dry_run: bool = True


@tool_registry.register(
    name="run_c1_lead_discovery",
    description="Discover YouTube Shorts lead channels and upsert them into lead_channels.",
    input_model=C1LeadDiscoveryInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["c1", "leads", "youtube", "supabase"],
)
def run_c1_lead_discovery(inp: C1LeadDiscoveryInput) -> dict[str, Any]:
    if inp.dry_run:
        return {"status": "preview", "dry_run": True, "source": inp.source}
    payload: dict[str, Any] = {"source": inp.source}
    if inp.work_title:
        payload.update({"source": "work_threshold", "work_title": inp.work_title})
    return _call_lambda("lambda.c1_lead_filter_handler", payload)


class C2ColdEmailInput(BaseModel):
    batch_size: int = Field(default=10, ge=1, le=200)
    genre: str | None = None
    min_monthly_views: int = Field(default=0, ge=0)
    platform: str | None = None
    dry_run: bool = True


@tool_registry.register(
    name="run_c2_cold_email",
    description="Send or preview cold emails to lead channels.",
    input_model=C2ColdEmailInput,
    risk_level=RiskLevel.HIGH,
    requires_approval=True,
    tags=["c2", "email", "leads"],
)
def run_c2_cold_email(inp: C2ColdEmailInput) -> dict[str, Any]:
    return _call_lambda("lambda.c2_cold_email_handler", inp.model_dump())


class C3WorkRegisterInput(BaseModel):
    work_title: str
    rights_holder_name: str
    release_year: int = Field(default=2026, ge=1900, le=2100)
    description: str = ""
    director: str = ""
    cast: str = ""
    genre: str = "Drama"
    video_type: str = "Drama"
    country: str = "Korea"
    platforms: list[str] = Field(default_factory=list)
    dry_run: bool = True


@tool_registry.register(
    name="run_c3_work_register",
    description="Register work metadata through the admin API and guideline flow.",
    input_model=C3WorkRegisterInput,
    risk_level=RiskLevel.HIGH,
    requires_approval=True,
    tags=["c3", "admin_api", "notion"],
)
def run_c3_work_register(inp: C3WorkRegisterInput) -> dict[str, Any]:
    return _call_lambda("lambda.c3_work_register_handler", inp.model_dump())


class C4CouponNotificationInput(BaseModel):
    source: str = "slack"
    creator_name: str = ""
    text: str = ""
    dry_run: bool = True


@tool_registry.register(
    name="run_c4_coupon_notification",
    description="Process a coupon request notification.",
    input_model=C4CouponNotificationInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["c4", "coupon", "slack"],
)
def run_c4_coupon_notification(inp: C4CouponNotificationInput) -> dict[str, Any]:
    return _call_lambda("lambda.c4_coupon_notification_handler", inp.model_dump())


class D2ReliefRequestInput(BaseModel):
    requester_channel_name: str
    requester_email: str
    requester_notes: str = ""
    submitted_via: str = "agent"
    auto_send_mails: bool = False
    items: list[dict[str, Any]] = Field(default_factory=list)
    dry_run: bool = True


@tool_registry.register(
    name="run_d2_relief_request",
    description="Create a rights-relief request and optionally send rights-holder emails.",
    input_model=D2ReliefRequestInput,
    risk_level=RiskLevel.HIGH,
    requires_approval=True,
    tags=["d2", "relief", "email"],
)
def run_d2_relief_request(inp: D2ReliefRequestInput) -> dict[str, Any]:
    return _call_lambda("lambda.d2_relief_request_handler", inp.model_dump())


class D3KakaoOnboardingInput(BaseModel):
    dry_run: bool = True


@tool_registry.register(
    name="run_d3_kakao_onboarding",
    description="Process Kakao creator onboarding sheets.",
    input_model=D3KakaoOnboardingInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["d3", "kakao", "sheets"],
)
def run_d3_kakao_onboarding(inp: D3KakaoOnboardingInput) -> dict[str, Any]:
    return _call_lambda("lambda.d3_kakao_creator_onboarding_handler", inp.model_dump())
