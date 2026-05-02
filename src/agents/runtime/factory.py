"""Factory helpers for wiring the agent runtime."""
from __future__ import annotations

from src.agents.approval.in_memory import InMemoryApprovalRepository
from src.agents.approval.queue import ApprovalQueue
from src.agents.repository import build_agent_trace_repository
from src.agents.runtime.agent import ILLMClient, RhoArtAgent
from src.agents.tools.definitions import tool_registry
from src.core.notifiers.null_notifier import NullNotifier


def build_rhoart_agent(
    *,
    llm_client: ILLMClient | None = None,
    dry_run_override: bool = False,
) -> RhoArtAgent:
    """Build a default RhoArtAgent with the shared tool registry."""
    approval_repo = InMemoryApprovalRepository()
    approval_queue = ApprovalQueue(
        repo=approval_repo,
        notifier=NullNotifier(),
        tool_registry=tool_registry,
    )
    return RhoArtAgent(
        tool_registry=tool_registry,
        approval_queue=approval_queue,
        trace_repo=build_agent_trace_repository(),
        llm_client=llm_client,
        dry_run_override=dry_run_override,
    )
