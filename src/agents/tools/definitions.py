"""9개 업무 Tool 등록.

각 Tool은:
- Input Pydantic 모델로 인자 스키마 정의
- dry_run=True 이면 사이드이펙트 없이 미리보기 반환
- dry_run=False 이면 기존 lambda handler 실행

향후 browser_supported=True 전환 시 browser_handler를 별도로 등록한다.
"""
from __future__ import annotations

import importlib
import json
from typing import Any

from pydantic import BaseModel, Field

from .registry import RiskLevel, ToolRegistry

# 전역 레지스트리 인스턴스 (rpa_server, agent 등에서 import하여 사용)
tool_registry = ToolRegistry()


# ─────────────────────────────────────────────
# 공통 유틸
# ─────────────────────────────────────────────

def _call_lambda(module_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """lambda/*.py handler(event, context) 호출."""
    mod = importlib.import_module(module_name)
    raw = mod.handler(payload, None)
    # Lambda 응답이 {"statusCode": 200, "body": "..."} 형식이면 언래핑
    if isinstance(raw, dict) and "statusCode" in raw and "body" in raw:
        body = raw.get("body")
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"raw_body": body, "statusCode": raw.get("statusCode")}
        return body or {}
    return raw if isinstance(raw, dict) else {"result": str(raw)}


# ─────────────────────────────────────────────
# A-2 작품사용신청 승인
# ─────────────────────────────────────────────

class A2WorkApprovalInput(BaseModel):
    """A-2: Slack 메시지에서 채널명/작품명 파싱 후 Drive 권한 부여 + 이메일 발송."""
    channel_name: str = Field(description="크리에이터 채널명")
    work_title: str = Field(description="사용 요청된 작품명")
    slack_channel_id: str = Field(default="", description="Slack 채널 ID")
    slack_message_ts: str = Field(default="", description="Slack 메시지 타임스탬프")
    dry_run: bool = Field(default=True, description="True면 파싱만, False면 실제 처리")


@tool_registry.register(
    name="run_a2_work_approval",
    description="Slack 작품사용신청 메시지를 파싱하여 Drive 열람 권한 부여 및 승인 이메일을 발송합니다.",
    input_model=A2WorkApprovalInput,
    risk_level=RiskLevel.HIGH,
    requires_approval=True,
    tags=["approval", "drive", "email", "slack"],
)
def run_a2_work_approval(inp: A2WorkApprovalInput) -> dict:
    if inp.dry_run:
        return {
            "preview_only": True,
            "channel_name": inp.channel_name,
            "work_title": inp.work_title,
            "note": "dry_run: Drive 권한 미부여, 이메일 미발송",
        }
    event = {
        "body": json.dumps({
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel": inp.slack_channel_id,
                "ts": inp.slack_message_ts,
                "text": (
                    f'채널: "{inp.channel_name}" 신규 영상 사용 요청이 있습니다.\n'
                    f'{inp.work_title}'
                ),
            },
        }, ensure_ascii=False),
    }
    return _call_lambda("lambda.a2_work_approval_handler", event)


# ─────────────────────────────────────────────
# A-3 네이버 클립 월별 집계
# ─────────────────────────────────────────────

class A3NaverClipMonthlyInput(BaseModel):
    """A-3: 네이버 클립 신청 월별 확인(confirm) 또는 발송(send)."""
    mode: str = Field(default="confirm", description="'confirm' 또는 'send'")
    dry_run: bool = Field(default=True)


@tool_registry.register(
    name="run_a3_naver_clip_monthly",
    description="네이버 클립 신청 데이터를 월별로 취합하고 엑셀을 생성하여 이메일로 발송합니다.",
    input_model=A3NaverClipMonthlyInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["naver_clip", "email", "sheets"],
)
def run_a3_naver_clip_monthly(inp: A3NaverClipMonthlyInput) -> dict:
    mode = "confirm" if inp.dry_run else inp.mode
    return _call_lambda("lambda.a3_naver_clip_monthly_handler", {"mode": mode})


# ─────────────────────────────────────────────
# B-2 주간 성과 보고
# ─────────────────────────────────────────────

class B2WeeklyReportInput(BaseModel):
    """B-2: 네이버 클립 채널 성과 크롤링 후 권리사 이메일 발송."""
    source: str = Field(default="agent", description="트리거 소스")
    dry_run: bool = Field(default=True)


@tool_registry.register(
    name="run_b2_weekly_report",
    description="네이버 클립 채널 성과를 크롤링하여 시트에 저장하고 권리사에게 주간 보고서를 발송합니다.",
    input_model=B2WeeklyReportInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["report", "naver_clip", "email", "sheets"],
)
def run_b2_weekly_report(inp: B2WeeklyReportInput) -> dict:
    if inp.dry_run:
        return {"preview_only": True, "note": "dry_run: 크롤링/발송 미실행"}
    return _call_lambda("lambda.b2_weekly_report_handler", {"source": inp.source})


# ─────────────────────────────────────────────
# C-1 리드 발굴
# ─────────────────────────────────────────────

class C1LeadDiscoveryInput(BaseModel):
    """C-1: YouTube Shorts 채널 탐색 후 리드 시트에 업서트."""
    trigger_source: str = Field(default="agent")
    dry_run: bool = Field(default=True)


@tool_registry.register(
    name="run_c1_lead_discovery",
    description="YouTube Data API로 드라마·영화 클립 채널을 탐색하여 리드 시트에 저장합니다.",
    input_model=C1LeadDiscoveryInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["leads", "youtube", "sheets"],
)
def run_c1_lead_discovery(inp: C1LeadDiscoveryInput) -> dict:
    if inp.dry_run:
        return {"preview_only": True, "note": "dry_run: 리드 시트 업서트 미실행"}
    return _call_lambda("lambda.c1_lead_filter_handler", {"_trigger_source": inp.trigger_source})


# ─────────────────────────────────────────────
# C-2 콜드메일 발송
# ─────────────────────────────────────────────

class C2ColdEmailInput(BaseModel):
    """C-2: 리드 시트에서 조건에 맞는 채널을 조회하여 콜드메일 발송."""
    batch_size: int = Field(default=10, ge=1, le=200, description="발송 건수 (최대 200)")
    genre: str | None = Field(default=None, description="장르 필터 (예: 드라마)")
    min_monthly_views: int = Field(default=0, ge=0, description="최소 월간 조회수")
    platform: str | None = Field(default=None, description="플랫폼 필터")
    dry_run: bool = Field(default=True, description="True면 대상 목록만 반환, 실제 발송 없음")


@tool_registry.register(
    name="run_c2_cold_email",
    description="리드 시트에서 조건에 맞는 YouTube 채널을 조회하고 개인화 콜드메일을 발송합니다.",
    input_model=C2ColdEmailInput,
    risk_level=RiskLevel.HIGH,
    requires_approval=True,
    tags=["email", "leads", "cold_email"],
)
def run_c2_cold_email(inp: C2ColdEmailInput) -> dict:
    payload = inp.model_dump()
    return _call_lambda("lambda.c2_cold_email_handler", payload)


# ─────────────────────────────────────────────
# C-3 작품 등록
# ─────────────────────────────────────────────

class C3WorkRegisterInput(BaseModel):
    """C-3: Admin API + Notion에 작품 메타데이터 등록."""
    work_title: str = Field(description="작품명")
    rights_holder_name: str = Field(description="권리사명")
    release_year: int = Field(default=2025, ge=1900, le=2100)
    description: str = Field(default="")
    director: str = Field(default="")
    cast: str = Field(default="")
    genre: str = Field(default="Drama")
    video_type: str = Field(default="Drama")
    country: str = Field(default="Korea")
    platforms: list[str] = Field(default_factory=lambda: ["wavve"])
    dry_run: bool = Field(default=True)


@tool_registry.register(
    name="run_c3_work_register",
    description="Admin API와 Notion에 작품 메타데이터를 등록하고 가이드라인 페이지를 생성합니다.",
    input_model=C3WorkRegisterInput,
    risk_level=RiskLevel.HIGH,
    requires_approval=True,
    tags=["admin_api", "notion", "work_register"],
)
def run_c3_work_register(inp: C3WorkRegisterInput) -> dict:
    payload = inp.model_dump()
    return _call_lambda("lambda.c3_work_register_handler", payload)


# ─────────────────────────────────────────────
# C-4 쿠폰 알림
# ─────────────────────────────────────────────

class C4CouponNotificationInput(BaseModel):
    """C-4: 쿠폰 요청 감지 후 시트 기록 + Slack DM 발송."""
    source: str = Field(default="slack", description="이벤트 소스")
    creator_name: str = Field(default="", description="크리에이터명")
    text: str = Field(default="", description="쿠폰 요청 메시지 원문")
    dry_run: bool = Field(default=True)


@tool_registry.register(
    name="run_c4_coupon_notification",
    description="Slack 메시지에서 쿠폰 요청을 감지하여 쿠폰 시트에 기록하고 Slack DM을 발송합니다.",
    input_model=C4CouponNotificationInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["coupon", "slack", "sheets"],
)
def run_c4_coupon_notification(inp: C4CouponNotificationInput) -> dict:
    payload = inp.model_dump()
    return _call_lambda("lambda.c4_coupon_notification_handler", payload)


# ─────────────────────────────────────────────
# D-2 정산 요청 백오피스
# ─────────────────────────────────────────────

class D2ReliefRequestInput(BaseModel):
    """D-2: 정산 요청 생성 및 권리사 이메일 발송."""
    requester_channel_name: str = Field(description="신청자 채널명")
    requester_email: str = Field(description="신청자 이메일")
    requester_notes: str = Field(default="")
    submitted_via: str = Field(default="agent")
    auto_send_mails: bool = Field(default=False, description="True면 권리사 메일 즉시 발송")
    items: list[dict[str, Any]] = Field(
        default_factory=lambda: [{"work_id": "work-1", "work_title": "Sample", "rights_holder_name": "Rights A", "channel_folder_name": ""}],
        description="정산 요청 작품 목록",
    )
    dry_run: bool = Field(default=True)


@tool_registry.register(
    name="run_d2_relief_request",
    description="정산 요청을 생성하고 옵션에 따라 권리사에게 이메일을 발송합니다.",
    input_model=D2ReliefRequestInput,
    risk_level=RiskLevel.HIGH,
    requires_approval=True,
    tags=["relief", "email", "rights_holder"],
)
def run_d2_relief_request(inp: D2ReliefRequestInput) -> dict:
    payload = inp.model_dump()
    return _call_lambda("lambda.d2_relief_request_handler", payload)


# ─────────────────────────────────────────────
# D-3 카카오 크리에이터 온보딩
# ─────────────────────────────────────────────

class D3KakaoOnboardingInput(BaseModel):
    """D-3: 카카오폼 응답을 취합하여 최종 리스트 시트 생성."""
    dry_run: bool = Field(default=True)


@tool_registry.register(
    name="run_d3_kakao_onboarding",
    description="카카오폼 응답 시트를 파싱하여 최종 온보딩 리스트 시트를 생성합니다.",
    input_model=D3KakaoOnboardingInput,
    risk_level=RiskLevel.MEDIUM,
    tags=["kakao", "sheets", "onboarding"],
)
def run_d3_kakao_onboarding(inp: D3KakaoOnboardingInput) -> dict:
    return _call_lambda("lambda.d3_kakao_creator_onboarding_handler", {"dry_run": inp.dry_run})
