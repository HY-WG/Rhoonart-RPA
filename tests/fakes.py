from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.models import NaverClipApplicant


class FakeNotifier:
    def __init__(self, *, send_result: bool = True) -> None:
        self.send_result = send_result
        self.sent: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

    def send(self, recipient: str, message: str, **kwargs: Any) -> bool:
        self.sent.append(
            {"recipient": recipient, "message": message, "kwargs": kwargs}
        )
        return self.send_result

    def send_error(
        self, task_id: str, error: Exception, context: dict[str, Any] | None = None
    ) -> bool:
        self.errors.append({"task_id": task_id, "error": error, "context": context})
        return True


class FakeSlackNotifier(FakeNotifier):
    def __init__(self, *, send_result: bool = True, reply_result: bool = True) -> None:
        super().__init__(send_result=send_result)
        self.reply_result = reply_result
        self.thread_replies: list[dict[str, str]] = []

    def reply_to_thread(self, channel: str, thread_ts: str, message: str) -> bool:
        self.thread_replies.append(
            {"channel": channel, "thread_ts": thread_ts, "message": message}
        )
        return self.reply_result


class FakeLogRepo:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    def write_log(self, entry: Any) -> None:
        self.entries.append(entry)


class FakeLeadRepo:
    def __init__(self, leads: list[Any] | None = None, upsert_result: int = 0) -> None:
        self.leads = list(leads or [])
        self.upsert_result = upsert_result
        self.upserted: list[Any] = []
        self.status_updates: list[tuple[str, str]] = []
        self.filters_seen: list[Any] = []

    def upsert_leads(self, leads: list[Any]) -> int:
        self.upserted.extend(leads)
        return self.upsert_result

    def get_leads_for_email(self, filters: Any) -> list[Any]:
        self.filters_seen.append(filters)
        result = []
        for lead in self.leads:
            if filters.genre and lead.genre != filters.genre:
                continue
            if lead.monthly_shorts_views < filters.min_monthly_views:
                continue
            if filters.email_sent_status and lead.email_sent_status != filters.email_sent_status:
                continue
            if filters.platform and lead.platform != filters.platform:
                continue
            result.append(lead)
        return result

    def update_lead_email_status(self, channel_id: str, status: str) -> None:
        self.status_updates.append((channel_id, status))


class FakeFormRepo:
    def __init__(self, applicants: list[NaverClipApplicant] | None = None) -> None:
        self.applicants = list(applicants or [])
        self.calls: list[tuple[int, int]] = []
        self.created: list[NaverClipApplicant] = []

    def create_applicant(self, applicant: NaverClipApplicant) -> NaverClipApplicant:
        self.created.append(applicant)
        self.applicants.append(applicant)
        return applicant

    def list_applicants(self) -> list[NaverClipApplicant]:
        return list(self.applicants)

    def get_applicants_by_month(self, year: int, month: int) -> list[NaverClipApplicant]:
        self.calls.append((year, month))
        return [
            applicant
            for applicant in self.applicants
            if applicant.submitted_at.year == year and applicant.submitted_at.month == month
        ]


@dataclass
class FakeRightsHolder:
    holder_id: str
    name: str
    email: str | None = None
    slack_channel: str | None = None
    dashboard_url: str | None = None
    channel_ids: list[str] | None = None


class FakePerformanceRepo:
    COL_IDENTIFIER = "identifier"
    COL_CONTENT_NAME = "content_name"

    def __init__(
        self,
        *,
        contents: list[tuple[str, str]] | None = None,
        rights_holders: list[Any] | None = None,
    ) -> None:
        self.contents = list(contents or [])
        self.rights_holders = list(rights_holders or [])
        self.upserted_stats: list[Any] = []

    def get_content_list(self) -> list[tuple[str, str]]:
        return list(self.contents)

    def upsert_channel_stats(self, stats: list[Any]) -> int:
        self.upserted_stats.extend(stats)
        return len(stats)

    def get_rights_holders(self) -> list[Any]:
        return list(self.rights_holders)


class FakeWorksheet:
    def __init__(self, headers: list[str], rows: list[list[str]]) -> None:
        self._headers = headers
        self._rows = [list(r) for r in rows]
        self.appended: list[list[Any]] = []

    def row_values(self, index: int) -> list[str]:
        if index != 1:
            raise IndexError(index)
        return list(self._headers)

    def get_all_values(self) -> list[list[str]]:
        return [list(self._headers), *[list(row) for row in self._rows]]

    def get_all_records(self) -> list[dict[str, Any]]:
        """헤더를 키로 사용하여 각 행을 dict로 반환."""
        result = []
        for row in self._rows:
            padded = row + [""] * (len(self._headers) - len(row))
            result.append(dict(zip(self._headers, padded)))
        return result

    def append_row(self, row: list[Any], **kwargs: Any) -> None:
        """행 추가 (테스트 검증용 appended 리스트에도 기록)."""
        self._rows.append(list(row))
        self.appended.append(list(row))


class FakeSpreadsheet:
    def __init__(self, worksheet: FakeWorksheet) -> None:
        self.sheet1 = worksheet


class FakeSheetsClient:
    def __init__(self, spreadsheets: dict[str, FakeSpreadsheet]) -> None:
        self._spreadsheets = spreadsheets

    def open_by_key(self, sheet_id: str) -> FakeSpreadsheet:
        return self._spreadsheets[sheet_id]


class FakeDriveService:
    def __init__(self, *, files: list[dict[str, str]] | None = None) -> None:
        self._files = list(files or [])
        self.permission_calls: list[dict[str, Any]] = []
        self.list_calls: list[dict[str, Any]] = []

    def files(self) -> "FakeDriveService":
        return self

    def permissions(self) -> "FakeDriveService":
        return self

    def list(self, **kwargs: Any) -> "FakeDriveRequest":
        self.list_calls.append(kwargs)
        return FakeDriveRequest({"files": list(self._files)})

    def create(self, **kwargs: Any) -> "FakeDriveRequest":
        self.permission_calls.append(kwargs)
        return FakeDriveRequest({"id": "permission-id"})


class FakeDriveRequest:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def execute(self) -> dict[str, Any]:
        return self._payload
