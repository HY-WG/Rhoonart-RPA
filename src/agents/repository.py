"""Agent Trace Repository 인터페이스 + InMemory/Supabase 구현체."""
from __future__ import annotations

import copy
import json
import logging
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any

import requests

logger = logging.getLogger(__name__)


class IAgentTraceRepository(ABC):
    @abstractmethod
    def save(self, trace: "AgentTrace") -> None: ...  # type: ignore[name-defined]

    @abstractmethod
    def get(self, trace_id: str) -> "AgentTrace | None": ...  # type: ignore[name-defined]

    @abstractmethod
    def get_recent(self, task_id: str, limit: int = 3) -> list[dict[str, Any]]: ...


class InMemoryAgentTraceRepository(IAgentTraceRepository):
    """테스트 및 개발용 인메모리 구현."""

    def __init__(self) -> None:
        self._traces: dict[str, Any] = {}
        self._lock = Lock()

    def save(self, trace: Any) -> None:
        with self._lock:
            self._traces[trace.trace_id] = copy.deepcopy(trace)

    def get(self, trace_id: str) -> Any | None:
        with self._lock:
            t = self._traces.get(trace_id)
            return copy.deepcopy(t) if t else None

    def get_recent(self, task_id: str, limit: int = 3) -> list[dict[str, Any]]:
        with self._lock:
            matching = [
                t for t in self._traces.values()
                if t.task_id == task_id
            ]
            matching.sort(key=lambda t: t.started_at, reverse=True)
            return [
                {
                    "trace_id": t.trace_id,
                    "task_id": t.task_id,
                    "status": t.status,
                    "started_at": t.started_at.isoformat(),
                    "steps_count": len(t.steps),
                }
                for t in matching[:limit]
            ]


class SupabaseAgentTraceRepository(IAgentTraceRepository):
    """Supabase `integration_runs` 테이블을 이용한 AgentTrace 영속화 구현체.

    AgentTrace를 IntegrationRun 레코드로 매핑하여 /dashboard 실시간 표시.
    - trace_id  → run_id
    - task_id   → task_id
    - status    → status  (observing/thinking/… → queued/running/succeeded/failed)
    - steps     → logs (JSON 직렬화 문자열 배열)
    - result    → result (마지막 tool_output)
    """

    _STATUS_MAP = {
        "observing": "running",
        "thinking": "running",
        "acting": "running",
        "reflecting": "running",
        "awaiting_approval": "running",
        "completed": "succeeded",
        "failed": "failed",
    }

    def __init__(
        self,
        *,
        supabase_url: str,
        supabase_key: str,
        timeout: float = 15.0,
    ) -> None:
        base_url = supabase_url.rstrip("/")
        self._endpoint = f"{base_url}/rest/v1/integration_runs"
        self._headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    # ── IAgentTraceRepository ──────────────────────────────────────────────

    def save(self, trace: Any) -> None:  # trace: AgentTrace
        row = self._trace_to_row(trace)
        try:
            self._request(
                "POST",
                "",
                json=row,
                extra_headers={"Prefer": "resolution=merge-duplicates"},
            )
        except Exception as exc:
            logger.warning("AgentTrace 저장 실패 (trace_id=%s): %s", trace.trace_id, exc)

    def get(self, trace_id: str) -> Any | None:
        try:
            resp = self._request("GET", f"?run_id=eq.{trace_id}&select=*")
            rows = resp.json()
        except Exception as exc:
            logger.warning("AgentTrace 조회 실패 (trace_id=%s): %s", trace_id, exc)
            return None
        if not rows:
            return None
        return self._row_to_summary(rows[0])

    def get_recent(self, task_id: str, limit: int = 3) -> list[dict[str, Any]]:
        try:
            resp = self._request(
                "GET",
                f"?task_id=eq.{task_id}&select=run_id,task_id,status,started_at,logs"
                f"&order=started_at.desc&limit={limit}",
            )
            rows = resp.json()
        except Exception as exc:
            logger.warning("AgentTrace 최근 조회 실패 (task_id=%s): %s", task_id, exc)
            return []
        return [
            {
                "trace_id": r["run_id"],
                "task_id": r["task_id"],
                "status": r["status"],
                "started_at": r.get("started_at", ""),
                "steps_count": len(r.get("logs") or []),
            }
            for r in rows
        ]

    # ── 내부 유틸 ──────────────────────────────────────────────────────────

    def _trace_to_row(self, trace: Any) -> dict[str, Any]:
        from datetime import datetime, timezone

        status_str = trace.status.value if hasattr(trace.status, "value") else str(trace.status)
        run_status = self._STATUS_MAP.get(status_str, "running")

        # steps를 로그 문자열 목록으로 직렬화
        logs: list[str] = []
        last_output: dict[str, Any] | None = None
        for step in trace.steps:
            s = step.to_dict() if hasattr(step, "to_dict") else step
            logs.append(json.dumps(s, ensure_ascii=False))
            if s.get("tool_output"):
                last_output = s["tool_output"]

        finished_at = trace.finished_at.isoformat() if trace.finished_at else None

        return {
            "run_id": trace.trace_id,
            "task_id": trace.task_id,
            "title": f"{trace.task_id} Agent",
            "payload": {"envelope_id": trace.envelope_id},
            "status": run_status,
            "execution_mode": "real_run",
            "requires_approval": False,
            "approved": True,
            "started_at": trace.started_at.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": finished_at,
            "result": last_output,
            "error": "",
            "logs": logs,
        }

    @staticmethod
    def _row_to_summary(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "trace_id": row["run_id"],
            "task_id": row["task_id"],
            "status": row["status"],
            "started_at": row.get("started_at", ""),
            "steps_count": len(row.get("logs") or []),
        }

    def _request(
        self,
        method: str,
        suffix: str,
        *,
        json: Any | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> requests.Response:
        headers = dict(self._headers)
        if extra_headers:
            headers.update(extra_headers)
        resp = requests.request(
            method=method,
            url=f"{self._endpoint}{suffix}",
            headers=headers,
            json=json,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp


def build_agent_trace_repository() -> IAgentTraceRepository:
    """환경변수에 따라 Supabase 또는 InMemory 트레이스 저장소 반환."""
    import os
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    db_type = os.getenv("INTEGRATION_DASHBOARD_DB_TYPE", "memory")
    if db_type == "supabase" and supabase_url and supabase_key:
        return SupabaseAgentTraceRepository(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
        )
    return InMemoryAgentTraceRepository()
