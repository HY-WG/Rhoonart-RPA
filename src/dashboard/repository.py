from __future__ import annotations

from abc import ABC, abstractmethod

from .models import IntegrationRun, IntegrationRunStatus


class IIntegrationDashboardRepository(ABC):
    @abstractmethod
    def save_run(self, run: IntegrationRun) -> None: ...

    @abstractmethod
    def get_run(self, run_id: str) -> IntegrationRun | None: ...

    @abstractmethod
    def list_runs(self, limit: int = 20) -> list[IntegrationRun]: ...

    @abstractmethod
    def append_log(self, run_id: str, message: str) -> None: ...

    @abstractmethod
    def update_run_status(
        self,
        run_id: str,
        status: IntegrationRunStatus,
        *,
        result: dict | None = None,
        error: str = "",
    ) -> None: ...
