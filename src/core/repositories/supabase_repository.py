"""Supabase Repository 스텁.

Google Sheets → Supabase 전환 시 이 파일을 채워 넣고
의존성 주입 지점(lambda/xxx_handler.py)에서 SheetXxx → SupabaseXxx 로 교체한다.
"""
from datetime import datetime
from typing import Optional

from ..interfaces.repository import (
    ICreatorRepository,
    IWorkRequestRepository,
    IPerformanceRepository,
    ILeadRepository,
    ILogRepository,
)
from ...models import (
    Creator, OnboardingStatus,
    WorkRequest, RequestStatus,
    ChannelStat, RightsHolder,
    Lead, LeadFilter,
    LogEntry,
)


class SupabaseCreatorRepository(ICreatorRepository):
    def __init__(self, client) -> None:
        self._client = client

    def get_new_contracts(self, since: datetime) -> list[Creator]:
        raise NotImplementedError

    def update_onboarding_status(self, creator_id: str, status: OnboardingStatus) -> None:
        raise NotImplementedError


class SupabaseWorkRequestRepository(IWorkRequestRepository):
    def __init__(self, client) -> None:
        self._client = client

    def get_request_by_message_ts(self, message_ts: str) -> Optional[WorkRequest]:
        raise NotImplementedError

    def save_request(self, request: WorkRequest) -> None:
        raise NotImplementedError

    def update_request_status(self, request_id: str, status: RequestStatus) -> None:
        raise NotImplementedError


class SupabasePerformanceRepository(IPerformanceRepository):
    def __init__(self, client) -> None:
        self._client = client

    def upsert_channel_stats(self, stats: list[ChannelStat]) -> int:
        raise NotImplementedError

    def get_rights_holders(self) -> list[RightsHolder]:
        raise NotImplementedError


class SupabaseLeadRepository(ILeadRepository):
    def __init__(self, client) -> None:
        self._client = client

    def upsert_leads(self, leads: list[Lead]) -> int:
        raise NotImplementedError

    def get_leads_for_email(self, filters: LeadFilter) -> list[Lead]:
        raise NotImplementedError

    def update_lead_email_status(self, channel_id: str, status: str) -> None:
        raise NotImplementedError


class SupabaseLogRepository(ILogRepository):
    def __init__(self, client) -> None:
        self._client = client

    def write_log(self, entry: LogEntry) -> None:
        raise NotImplementedError
