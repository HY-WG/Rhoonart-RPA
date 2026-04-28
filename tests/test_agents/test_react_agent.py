"""RhoArtAgent ReAct 루프 단위 테스트."""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from src.agents.approval.in_memory import InMemoryApprovalRepository
from src.agents.approval.queue import ApprovalQueue
from src.agents.repository import InMemoryAgentTraceRepository
from src.agents.runtime.agent import FakeLLMClient, RhoArtAgent
from src.agents.runtime.models import AgentState
from src.agents.tools.registry import RiskLevel, ToolRegistry


# ── 픽스처 ────────────────────────────────────────────────────────────────

class EchoInput(BaseModel):
    message: str = "hello"
    dry_run: bool = False


class RiskyInput(BaseModel):
    target: str
    dry_run: bool = True


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    @registry.register(
        name="echo",
        description="메시지 에코",
        input_model=EchoInput,
        risk_level=RiskLevel.LOW,
        requires_approval=False,
    )
    def _echo(inp: EchoInput) -> dict:
        return {"status": "ok", "result": inp.message, "dry_run": inp.dry_run}

    @registry.register(
        name="risky_delete",
        description="위험한 삭제 작업",
        input_model=RiskyInput,
        risk_level=RiskLevel.HIGH,
        requires_approval=True,
    )
    def _risky(inp: RiskyInput) -> dict:
        return {"status": "ok", "target": inp.target}

    return registry


def _make_agent(
    llm_responses: list[str],
    *,
    dry_run_override: bool = False,
    registry: ToolRegistry | None = None,
) -> tuple[RhoArtAgent, InMemoryApprovalRepository, InMemoryAgentTraceRepository]:
    reg = registry or _build_registry()
    approval_repo = InMemoryApprovalRepository()

    class _FakeNotifier:
        def send(self, **kwargs): pass

    approval_queue = ApprovalQueue(
        repo=approval_repo,
        notifier=_FakeNotifier(),
        tool_registry=reg,
    )
    trace_repo = InMemoryAgentTraceRepository()
    agent = RhoArtAgent(
        tool_registry=reg,
        approval_queue=approval_queue,
        trace_repo=trace_repo,
        llm_client=FakeLLMClient(llm_responses),
        dry_run_override=dry_run_override,
    )
    return agent, approval_repo, trace_repo


def _thought_json(tool: str, inputs: dict, *, requires_approval: bool = False, risk: str = "low") -> str:
    return json.dumps({
        "reasoning": f"{tool} 실행",
        "selected_tool": tool,
        "tool_input": inputs,
        "requires_approval": requires_approval,
        "risk_level": risk,
        "confidence": 0.9,
    })


# ── 기본 완료 흐름 ─────────────────────────────────────────────────────────

def test_agent_run_finish_immediately() -> None:
    """LLM이 첫 응답에서 finish를 선택하면 즉시 completed 반환."""
    finish_response = _thought_json("finish", {})
    agent, _, trace_repo = _make_agent([finish_response])
    result = agent.run({
        "task_id": "test",
        "envelope_id": "env-001",
        "instruction": "아무것도 하지 마",
        "context": {},
    })
    assert result["status"] == "completed"


def test_agent_run_single_tool_then_finish() -> None:
    """도구 1개 실행 → finish 흐름."""
    echo_response = _thought_json("echo", {"message": "테스트", "dry_run": False})
    # reflect 후 continue_loop=False이므로 finish 없이 완료
    agent, _, _ = _make_agent([echo_response])
    result = agent.run({
        "task_id": "test",
        "envelope_id": "env-002",
        "instruction": "에코 실행",
        "context": {},
    })
    assert result["status"] == "completed"
    # 도구 출력은 last_output 안에 들어 있음
    assert result["last_output"].get("result") == "테스트"


def test_agent_saves_trace(trace_repo: InMemoryAgentTraceRepository | None = None) -> None:
    """실행 후 trace_repo에 저장되어야 한다."""
    finish = _thought_json("finish", {})
    agent, _, t_repo = _make_agent([finish])
    agent.run({"task_id": "T-1", "envelope_id": "e-1", "instruction": "테스트", "context": {}})
    recent = t_repo.get_recent("T-1", limit=5)
    assert len(recent) == 1
    assert recent[0]["status"] == AgentState.COMPLETED.value


# ── dry_run_override ──────────────────────────────────────────────────────

def test_dry_run_override_forces_dry_run() -> None:
    """dry_run_override=True면 tool_input.dry_run이 True로 강제된다."""
    echo_response = _thought_json("echo", {"message": "hi", "dry_run": False})
    agent, _, _ = _make_agent([echo_response], dry_run_override=True)
    result = agent.run({
        "task_id": "test",
        "envelope_id": "e-dry",
        "instruction": "테스트",
        "context": {},
    })
    # dry_run=True이면 도구 출력에 dry_run=True 포함 (last_output 안)
    assert result["last_output"].get("dry_run") is True


# ── 승인 흐름 ─────────────────────────────────────────────────────────────

def test_agent_pauses_for_high_risk_tool() -> None:
    """requires_approval=True 도구 선택 시 awaiting_approval 반환."""
    risky_response = _thought_json(
        "risky_delete",
        {"target": "prod", "dry_run": False},
        requires_approval=True,
        risk="high",
    )
    agent, approval_repo, _ = _make_agent([risky_response])
    result = agent.run({
        "task_id": "test",
        "envelope_id": "e-risky",
        "instruction": "삭제 실행",
        "context": {},
    })
    assert result["status"] == "awaiting_approval"
    assert "approval_id" in result
    # approval_repo에 저장됐는지 확인
    pending = approval_repo.list_pending()
    assert len(pending) == 1


def test_agent_no_approval_when_dry_run() -> None:
    """dry_run=True면 high-risk 도구도 승인 없이 실행."""
    risky_dry = _thought_json(
        "risky_delete",
        {"target": "prod", "dry_run": True},
        requires_approval=False,
        risk="high",
    )
    # risky_delete는 requires_approval=True이지만 dry_run=True면 통과
    agent, approval_repo, _ = _make_agent([risky_dry])
    result = agent.run({
        "task_id": "test",
        "envelope_id": "e-dry-risky",
        "instruction": "테스트",
        "context": {},
    })
    # dry_run이므로 승인 없이 completed
    assert result["status"] != "awaiting_approval"
    assert approval_repo.list_pending() == []


# ── 오류 처리 ─────────────────────────────────────────────────────────────

def test_agent_handles_unknown_tool() -> None:
    """미등록 도구 호출 시 failed 상태 반환."""
    unknown_response = _thought_json("nonexistent_tool", {})
    agent, _, _ = _make_agent([unknown_response])
    result = agent.run({
        "task_id": "test",
        "envelope_id": "e-err",
        "instruction": "없는 도구",
        "context": {},
    })
    assert result["status"] == "failed"
    assert "error" in result


def test_agent_handles_invalid_llm_json() -> None:
    """LLM이 파싱 불가 응답을 반환하면 finish로 폴백."""
    agent, _, _ = _make_agent(["이것은 JSON이 아닙니다 !!!"])
    result = agent.run({
        "task_id": "test",
        "envelope_id": "e-parse",
        "instruction": "테스트",
        "context": {},
    })
    # 파싱 실패 → finish로 폴백 → completed
    assert result["status"] == "completed"


# ── FakeLLMClient ─────────────────────────────────────────────────────────

def test_fake_llm_queue_exhausted_returns_finish() -> None:
    """응답 큐가 빈 경우 기본 finish JSON 반환."""
    fake = FakeLLMClient([])
    resp = fake.create_message(model="x", max_tokens=100, system="s", messages=[])
    data = json.loads(resp)
    assert data["selected_tool"] == "finish"


def test_fake_llm_pops_in_order() -> None:
    responses = [
        _thought_json("echo", {"message": "first"}),
        _thought_json("echo", {"message": "second"}),
    ]
    fake = FakeLLMClient(responses)
    r1 = json.loads(fake.create_message(model="x", max_tokens=100, system="s", messages=[]))
    r2 = json.loads(fake.create_message(model="x", max_tokens=100, system="s", messages=[]))
    assert r1["tool_input"]["message"] == "first"
    assert r2["tool_input"]["message"] == "second"
