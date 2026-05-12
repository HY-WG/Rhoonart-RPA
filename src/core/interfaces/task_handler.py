"""ITaskHandler — common interface for all RPA task handlers.

Every task (A-2, A-3, B-2, …) is a class that implements this interface.
The interface separates three concerns:

  1. build_event()   — transform the API payload into the Lambda event dict.
                       (pure; no I/O)
  2. post_invoke()   — optional side effects after Lambda invocation
                       (Supabase writes, audit logging, …).
  3. execute()       — orchestrates: build_event → invoker → post_invoke.
                       The ``invoker`` callable is injected by the caller
                       so that tests can substitute a mock without patching
                       module globals.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class TaskMeta:
    """Static metadata that every task must declare."""
    task_id: str       # e.g. "A-2"
    task_name: str     # e.g. "작품 사용요청 승인 자동화"
    lambda_module: str  # e.g. "lambda.a2_work_approval_handler"


class ITaskHandler(ABC):
    """Abstract base for all RPA task handlers.

    Concrete subclasses MUST implement ``meta``.
    Override ``build_event`` and/or ``post_invoke`` for task-specific logic.
    """

    @property
    @abstractmethod
    def meta(self) -> TaskMeta:
        """Return static task metadata."""
        ...

    # ------------------------------------------------------------------
    # Extension points — override in subclasses as needed
    # ------------------------------------------------------------------

    def build_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Transform API payload into the Lambda event dict.

        Default behaviour: return payload unchanged (passthrough).
        """
        return payload

    def post_invoke(
        self,
        result: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Optional side effects after Lambda invocation.

        Default behaviour: return result unchanged.
        Subclasses may augment ``result`` (e.g. attach DB-write status).
        """
        return result

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def execute(
        self,
        payload: dict[str, Any],
        *,
        invoker: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Run the full handler pipeline.

        Args:
            payload:  Raw request payload from the API route.
            invoker:  Callable(module_name, event) → result dict.
                      Production code passes ``invoke_lambda`` from
                      ``src.api.dependencies``; tests pass a mock.

        Returns:
            Final result dict (post-processed by ``post_invoke``).
        """
        event = self.build_event(payload)
        result = invoker(self.meta.lambda_module, event)
        return self.post_invoke(result, payload)
