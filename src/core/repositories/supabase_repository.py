"""Supabase repository implementations used by Lambda handlers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from ..interfaces.repository import (
    ICreatorRepository,
    ILeadRepository,
    ILogRepository,
    IPerformanceRepository,
    IWorkRequestRepository,
)
from ...models import (
    ChannelStat,
    Creator,
    Lead,
    LeadFilter,
    LogEntry,
    OnboardingStatus,
    RequestStatus,
    RightsHolder,
    WorkRequest,
)
from ...models.lead import EmailSentStatus, Genre


LEAD_TABLE = "lead_channels"
SEED_CHANNEL_TABLE = "seed_channel"
BLOCKLIST_TABLE = "channel_blocklist"
LOG_TABLE = "automation_runs"

_STATUS_TO_DB = {
    EmailSentStatus.NOT_SENT: "unsent",
    EmailSentStatus.SENT: "sent",
    EmailSentStatus.BOUNCED: "bounced",
    EmailSentStatus.REPLIED: "replied",
}
_DB_TO_STATUS = {value: key for key, value in _STATUS_TO_DB.items()}
_DB_TO_STATUS.update({
    EmailSentStatus.NOT_SENT.value: EmailSentStatus.NOT_SENT,
    EmailSentStatus.SENT.value: EmailSentStatus.SENT,
    EmailSentStatus.BOUNCED.value: EmailSentStatus.BOUNCED,
    EmailSentStatus.REPLIED.value: EmailSentStatus.REPLIED,
})


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
        if not leads:
            return 0
        rows = [self._lead_to_row(lead) for lead in leads]
        (
            self._client
            .table(LEAD_TABLE)
            .upsert(rows, on_conflict="channel_id")
            .execute()
        )
        return len(rows)

    def get_leads_for_email(self, filters: LeadFilter) -> list[Lead]:
        query = (
            self._client
            .table(LEAD_TABLE)
            .select("*")
            .order("monthly_views", desc=True)
        )
        if filters.genre:
            query = query.eq("genre", filters.genre.value)
        if filters.min_monthly_views:
            query = query.gte("monthly_views", filters.min_monthly_views)
        if filters.email_sent_status:
            query = query.eq("email_status", _status_to_db(filters.email_sent_status))
        if filters.platform:
            query = query.eq("platform", filters.platform)

        response = query.execute()
        return [self._row_to_lead(row) for row in (response.data or [])]

    def update_lead_email_status(self, channel_id: str, status: str) -> None:
        now = datetime.utcnow().isoformat()
        payload = {
            "email_status": _status_to_db(status),
            "last_contacted_at": now,
            "last_updated_at": now,
        }
        (
            self._client
            .table(LEAD_TABLE)
            .update(payload)
            .eq("channel_id", channel_id)
            .execute()
        )

    @staticmethod
    def _lead_to_row(lead: Lead) -> dict[str, Any]:
        return {
            "channel_id": lead.channel_id,
            "channel_name": lead.channel_name,
            "channel_url": lead.channel_url,
            "platform": lead.platform,
            "genre": lead.genre.value,
            "grade": lead.tier,
            "monthly_views": lead.monthly_shorts_views,
            "subscriber_count": lead.subscribers or 0,
            "email": lead.email,
            "email_status": _status_to_db(lead.email_sent_status),
            "discovered_at": lead.discovered_at.isoformat(),
            "last_contacted_at": (
                lead.last_contacted_at.isoformat()
                if lead.last_contacted_at else None
            ),
            "last_updated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _row_to_lead(row: dict[str, Any]) -> Lead:
        return Lead(
            channel_id=str(row.get("channel_id") or ""),
            channel_name=str(row.get("channel_name") or ""),
            channel_url=str(row.get("channel_url") or ""),
            platform=str(row.get("platform") or "youtube"),
            genre=_genre_from_value(row.get("genre")),
            monthly_shorts_views=int(row.get("monthly_views") or 0),
            tier=row.get("grade") or row.get("tier"),
            subscribers=int(row["subscriber_count"]) if row.get("subscriber_count") else None,
            email=row.get("email") or None,
            email_sent_status=_status_from_db(row.get("email_status")),
            discovered_at=_parse_datetime(row.get("discovered_at")),
            last_contacted_at=(
                _parse_datetime(row.get("last_contacted_at"))
                if row.get("last_contacted_at") else None
            ),
        )


class SupabaseSeedChannelRepository:
    def __init__(self, client) -> None:
        self._client = client

    def list_seed_channel_urls(self, *, platform: str = "youtube", limit: int = 1000) -> list[str]:
        response = (
            self._client
            .table(SEED_CHANNEL_TABLE)
            .select("*")
            .eq("platform", platform)
            .eq("active", True)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        urls: list[str] = []
        for row in response.data or []:
            url = str(row.get("channel_url") or row.get("url") or "").strip()
            if url.startswith("http"):
                urls.append(url)
        return urls

    def get_blocklist_channel_ids(self, *, platform: str = "youtube") -> set[str]:
        """Supabase channel_blocklist에서 차단된 channel_id 집합 반환.

        크롤러의 로컬 JSON 블록리스트와 병합하여 사용한다.
        """
        response = (
            self._client
            .table(BLOCKLIST_TABLE)
            .select("channel_id")
            .eq("platform", platform)
            .execute()
        )
        return {row["channel_id"] for row in (response.data or []) if row.get("channel_id")}


class SupabaseLogRepository(ILogRepository):
    def __init__(self, client) -> None:
        self._client = client

    def write_log(self, entry: LogEntry) -> None:
        now = datetime.utcnow().isoformat()
        self._client.table(LOG_TABLE).upsert({
            "run_id": entry.log_id,
            "task_id": entry.task_id,
            "title": entry.task_name,
            "payload": {
                "trigger_type": entry.trigger_type.value,
                "trigger_source": entry.trigger_source,
            },
            "status": entry.status.value,
            "execution_mode": entry.trigger_type.value,
            "started_at": entry.executed_at.isoformat(),
            "updated_at": now,
            "finished_at": now,
            "result": entry.result,
            "error": entry.error,
            "logs": [],
        }, on_conflict="run_id").execute()


def _status_to_db(status: EmailSentStatus | str) -> str:
    if isinstance(status, EmailSentStatus):
        return _STATUS_TO_DB[status]
    for enum_value, db_value in _STATUS_TO_DB.items():
        if status in {enum_value.value, db_value}:
            return db_value
    return str(status)


def _status_from_db(value: Any) -> EmailSentStatus:
    return _DB_TO_STATUS.get(str(value or "unsent"), EmailSentStatus.NOT_SENT)


def _genre_from_value(value: Any) -> Genre:
    raw = str(value or Genre.OTHER.value)
    for genre in Genre:
        if raw == genre.value or raw == genre.name:
            return genre
    return Genre.OTHER


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not value:
        return datetime.utcnow()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
