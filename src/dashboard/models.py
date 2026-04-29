from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IntegrationRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExecutionMode(str, Enum):
    DRY_RUN = "dry_run"
    REAL_RUN = "real_run"


@dataclass(frozen=True)
class IntegrationTaskSpec:
    task_id: str
    title: str
    description: str
    default_payload: dict[str, Any]
    targets: list[str] = field(default_factory=list)
    trigger_mode: str = "manual"
    requires_approval: bool = False
    supports_dry_run: bool = True
    real_run_warning: str = ""
    sheet_links: dict[str, str] = field(default_factory=dict)
    # 탭 그룹: "ops_admin" | "homepage_auto"
    tab_group: str = "ops_admin"


@dataclass
class IntegrationRun:
    run_id: str
    task_id: str
    title: str
    payload: dict[str, Any]
    status: IntegrationRunStatus
    started_at: datetime
    updated_at: datetime
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    requires_approval: bool = False
    approved: bool = False
    finished_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: str = ""
    logs: list[str] = field(default_factory=list)
