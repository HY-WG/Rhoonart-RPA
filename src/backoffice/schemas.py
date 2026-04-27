from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReliefRequestItemModel(BaseModel):
    work_id: str
    work_title: str
    rights_holder_name: str
    channel_folder_name: str = ""


class ReliefRequestCreateModel(BaseModel):
    requester_channel_name: str
    requester_email: str
    requester_notes: str = ""
    submitted_via: str = "web"
    items: list[ReliefRequestItemModel] = Field(default_factory=list)


class ReliefRequestSummaryModel(BaseModel):
    request_id: str
    requester_channel_name: str
    requester_email: str
    requester_notes: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    submitted_via: str


class OutboundMailModel(BaseModel):
    mail_id: str
    holder_name: str
    recipient_email: str
    subject: str
    status: str
    sent_at: Optional[datetime] = None
    error_message: str = ""


class ReliefRequestDetailModel(ReliefRequestSummaryModel):
    items: list[ReliefRequestItemModel] = Field(default_factory=list)
    outbound_mails: list[OutboundMailModel] = Field(default_factory=list)


class SendRightsHolderMailRequest(BaseModel):
    template_key: str = "rights_holder_request"


class SendRightsHolderMailResponse(BaseModel):
    request_id: str
    attempted: int
    sent: int
    failed: int
    updated_status: str
