"""Pydantic request/response models for the RPA Control Server API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.models import RepresentativeChannelPlatform


class GenericTriggerRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class A3ApplicantCreateRequest(BaseModel):
    name: str
    phone_number: str
    naver_id: str
    naver_clip_profile_name: str
    naver_clip_profile_id: str
    representative_channel_name: str
    representative_channel_platform: RepresentativeChannelPlatform
    channel_url: str


class A3ApplicantResponse(BaseModel):
    applicant_id: str
    name: str
    phone_number: str
    naver_id: str
    naver_clip_profile_name: str
    naver_clip_profile_id: str
    representative_channel_name: str
    representative_channel_platform: RepresentativeChannelPlatform
    channel_url: str
    submitted_at: datetime


class KakaoCreatorCreateRequest(BaseModel):
    creator_name: str = Field(min_length=1)
    kakao_channel: str = ""
    contact_email: str = ""
    phone_number: str = ""
    note: str = ""


class PortalActionRequest(BaseModel):
    channel_id: str | None = None
    video_id: str | None = None
    platform: str | None = None
    channel_name: str | None = None
    contact_email: str | None = None
    work_title: str | None = None
    rights_holder_name: str | None = None
    note: str = ""


class A2ManualRequestStub(BaseModel):
    channel_name: str
    work_title: str


class B2AdminRunRequest(BaseModel):
    send_notifications: bool = False
    source: str = "admin_page"


class B2SupabaseCollectRequest(BaseModel):
    triggered_by: str = Field(default="manual", pattern="^(manual|schedule|api)$")
    max_clips_per_identifier: int = Field(default=2000, ge=1, le=5000)


class MetabaseReportSendRequest(BaseModel):
    rights_holder_name: str


class NaverReportScheduleUpdateRequest(BaseModel):
    enabled: bool
    days_of_week: list[int] = Field(min_length=1)
    send_time: str
    timezone: str = "Asia/Seoul"
    recipient_emails: list[str] = Field(default_factory=list)
    include_work_ids: list[int] = Field(default_factory=list)


class NaverWorkReportEnabledUpdateRequest(BaseModel):
    naver_report_enabled: bool


class NaverWorkCreateRequest(BaseModel):
    content_name: str = Field(min_length=1)
    identifier: str = Field(min_length=1)
    rights_holder_name: str = Field(min_length=1)
    status: str = "Active"
    naver_report_enabled: bool = True


class NaverMonthlyManagerUpdateRequest(BaseModel):
    manager_name: str = Field(min_length=1)
    manager_email: str = Field(min_length=1)


class LeadPromoteRequest(BaseModel):
    promoted_by: str = "admin"


class LeadBlockRequest(BaseModel):
    reason: str = ""
    blocked_by: str = "admin"


class LeadSendEmailRequest(BaseModel):
    dry_run: bool = False
    sent_by: str = "admin"


class OfficialDocumentSaveRequest(BaseModel):
    content_body: dict[str, Any] = Field(default_factory=dict)
    work_id: str | None = None


class WorkCreateSupabaseRequest(BaseModel):
    work_title: str = Field(min_length=1)
    rights_holder_name: str = ""
    release_year: int | str | None = None
    description: str = ""
    director: str = ""
    cast: str = ""
    genre: str = ""
    video_type: str = ""
    country: str = ""
    platforms: list[str] = Field(default_factory=list)
    platform_video_url: str = ""
    trailer_url: str = ""
    thumbnail_url: str = ""
    source_download_url: str = ""


class WorkRequestDecisionRequest(BaseModel):
    decided_by: str = "admin"
    note: str = ""


class B2AnalyticsQuery(BaseModel):
    checked_from: str | None = None
    checked_to: str | None = None
    uploaded_from: str | None = None
    uploaded_to: str | None = None
    channel_name: str | None = None
    clip_title: str | None = None
    work_title: str | None = None
    rights_holder_name: str | None = None
    platform: str | None = None
    group_by: str = "clip"
    limit: int = 100
