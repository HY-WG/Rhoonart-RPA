from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import requests

from ...dashboard.models import ExecutionMode, IntegrationRun, IntegrationRunStatus
from ...dashboard.repository import IIntegrationDashboardRepository


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SupabaseIntegrationDashboardRepository(IIntegrationDashboardRepository):
    """Supabase REST-backed repository for dashboard run logs."""

    TABLE_NAME = "integration_runs"

    def __init__(
        self,
        *,
        supabase_url: str,
        supabase_key: str,
        timeout: float = 15.0,
    ) -> None:
        base_url = supabase_url.rstrip("/")
        self._endpoint = f"{base_url}/rest/v1/{self.TABLE_NAME}"
        self._headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def save_run(self, run: IntegrationRun) -> None:
        payload = self._run_to_row(run)
        self._request(
            "POST",
            "",
            json=payload,
            headers={"Prefer": "resolution=merge-duplicates"},
        )

    def get_run(self, run_id: str) -> IntegrationRun | None:
        response = self._request(
            "GET",
            f"?run_id=eq.{run_id}&select=*",
        )
        rows = response.json()
        if not rows:
            return None
        return self._row_to_run(rows[0])

    def list_runs(self, limit: int = 20) -> list[IntegrationRun]:
        response = self._request(
            "GET",
            f"?select=*&order=started_at.desc&limit={limit}",
        )
        rows = response.json()
        return [self._row_to_run(row) for row in rows]

    def append_log(self, run_id: str, message: str) -> None:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        run.logs.append(message)
        run.updated_at = datetime.now(UTC)
        self._update_run(run)

    def update_run_status(
        self,
        run_id: str,
        status: IntegrationRunStatus,
        *,
        result: dict | None = None,
        error: str = "",
    ) -> None:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        run.status = status
        run.updated_at = datetime.now(UTC)
        run.result = result
        run.error = error
        if status in (IntegrationRunStatus.SUCCEEDED, IntegrationRunStatus.FAILED):
            run.finished_at = datetime.now(UTC)
        self._update_run(run)

    def _update_run(self, run: IntegrationRun) -> None:
        payload = self._run_to_row(run)
        self._request(
            "PATCH",
            f"?run_id=eq.{run.run_id}",
            json=payload,
        )

    def _request(
        self,
        method: str,
        suffix: str,
        *,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        merged_headers = dict(self._headers)
        if headers:
            merged_headers.update(headers)
        response = requests.request(
            method=method,
            url=f"{self._endpoint}{suffix}",
            headers=merged_headers,
            json=json,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response

    @staticmethod
    def _run_to_row(run: IntegrationRun) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "task_id": run.task_id,
            "title": run.title,
            "payload": run.payload,
            "status": run.status.value,
            "execution_mode": run.execution_mode.value,
            "requires_approval": run.requires_approval,
            "approved": run.approved,
            "started_at": _iso(run.started_at),
            "updated_at": _iso(run.updated_at),
            "finished_at": _iso(run.finished_at),
            "result": run.result,
            "error": run.error,
            "logs": run.logs,
        }

    @staticmethod
    def _row_to_run(row: dict[str, Any]) -> IntegrationRun:
        return replace(
            IntegrationRun(
                run_id=row["run_id"],
                task_id=row["task_id"],
                title=row["title"],
                payload=row.get("payload") or {},
                status=IntegrationRunStatus(row["status"]),
                execution_mode=ExecutionMode(
                    row.get("execution_mode", ExecutionMode.DRY_RUN.value)
                ),
                requires_approval=bool(row.get("requires_approval", False)),
                approved=bool(row.get("approved", False)),
                started_at=_parse_datetime(row.get("started_at")) or datetime.now(UTC),
                updated_at=_parse_datetime(row.get("updated_at")) or datetime.now(UTC),
                finished_at=_parse_datetime(row.get("finished_at")),
                result=row.get("result"),
                error=row.get("error", ""),
                logs=list(row.get("logs") or []),
            ),
            logs=list(row.get("logs") or []),
        )
