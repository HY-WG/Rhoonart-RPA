from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import Lock

from .models import IntegrationRun, IntegrationRunStatus
from .repository import IIntegrationDashboardRepository


class InMemoryIntegrationDashboardRepository(IIntegrationDashboardRepository):
    def __init__(self) -> None:
        self._runs: dict[str, IntegrationRun] = {}
        self._lock = Lock()

    def save_run(self, run: IntegrationRun) -> None:
        with self._lock:
            self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> IntegrationRun | None:
        with self._lock:
            run = self._runs.get(run_id)
            return None if run is None else replace(run, logs=list(run.logs))

    def list_runs(self, limit: int = 20) -> list[IntegrationRun]:
        with self._lock:
            runs = sorted(
                self._runs.values(),
                key=lambda run: run.started_at,
                reverse=True,
            )
            return [replace(run, logs=list(run.logs)) for run in runs[:limit]]

    def append_log(self, run_id: str, message: str) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.logs.append(message)
            run.updated_at = datetime.now(UTC)

    def update_run_status(
        self,
        run_id: str,
        status: IntegrationRunStatus,
        *,
        result: dict | None = None,
        error: str = "",
    ) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.status = status
            run.updated_at = datetime.now(UTC)
            run.result = result
            run.error = error
            if status in (IntegrationRunStatus.SUCCEEDED, IntegrationRunStatus.FAILED):
                run.finished_at = datetime.now(UTC)
