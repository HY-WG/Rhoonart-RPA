"""Agent Trace Repository 인터페이스 + InMemory 구현체."""
from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any


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
