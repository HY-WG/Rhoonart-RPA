"""Tool Registry 단위 테스트."""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from src.agents.tools.registry import RiskLevel, ToolRegistry, ToolSpec


# ── 픽스처 ────────────────────────────────────────────────────────────────

class EchoInput(BaseModel):
    message: str
    repeat: int = 1


class RiskyInput(BaseModel):
    target: str
    dry_run: bool = True


@pytest.fixture()
def registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.register(
        name="echo",
        description="메시지를 repeat 회 반복하는 테스트 도구",
        input_model=EchoInput,
        risk_level=RiskLevel.LOW,
        requires_approval=False,
        tags=["test"],
    )
    def _echo(inputs: EchoInput) -> dict:
        return {"result": inputs.message * inputs.repeat}

    @reg.register(
        name="risky_action",
        description="위험한 작업",
        input_model=RiskyInput,
        risk_level=RiskLevel.HIGH,
        requires_approval=True,
    )
    def _risky(inputs: RiskyInput) -> dict:
        return {"target": inputs.target, "dry_run": inputs.dry_run}

    return reg


# ── 기본 등록 / 조회 ───────────────────────────────────────────────────────

def test_register_and_list(registry: ToolRegistry) -> None:
    names = registry.list_names()
    assert "echo" in names
    assert "risky_action" in names


def test_contains(registry: ToolRegistry) -> None:
    assert "echo" in registry
    assert "unknown_tool" not in registry


def test_get_spec(registry: ToolRegistry) -> None:
    spec = registry.get_spec("echo")
    assert isinstance(spec, ToolSpec)
    assert spec.risk_level == RiskLevel.LOW
    assert spec.requires_approval is False
    assert "test" in spec.tags


def test_get_spec_unknown_raises(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match="등록되지 않은 도구"):
        registry.get_spec("no_such_tool")


# ── call — 정상 실행 ───────────────────────────────────────────────────────

def test_call_echo(registry: ToolRegistry) -> None:
    result = registry.call("echo", {"message": "hi", "repeat": 3})
    assert result == {"result": "hihihi"}


def test_call_echo_default(registry: ToolRegistry) -> None:
    result = registry.call("echo", {"message": "x"})
    assert result == {"result": "x"}


def test_call_risky_dry_run(registry: ToolRegistry) -> None:
    result = registry.call("risky_action", {"target": "prod-db", "dry_run": True})
    assert result["dry_run"] is True


# ── call — 검증 실패 ───────────────────────────────────────────────────────

def test_call_unknown_raises(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match="등록되지 않은 도구"):
        registry.call("ghost", {})


def test_call_type_error_raises(registry: ToolRegistry) -> None:
    with pytest.raises(ValidationError):
        registry.call("echo", {"message": 123, "repeat": "not_int"})


def test_call_missing_required_field(registry: ToolRegistry) -> None:
    with pytest.raises(ValidationError):
        registry.call("echo", {})  # message 필수


# ── describe_all ──────────────────────────────────────────────────────────

def test_describe_all(registry: ToolRegistry) -> None:
    descs = registry.describe_all()
    names = {d["name"] for d in descs}
    assert {"echo", "risky_action"} <= names

    echo_desc = next(d for d in descs if d["name"] == "echo")
    assert "input_schema" in echo_desc
    assert echo_desc["risk_level"] == "low"
    assert echo_desc["requires_approval"] is False


def test_describe_all_risky(registry: ToolRegistry) -> None:
    descs = registry.describe_all()
    risky_desc = next(d for d in descs if d["name"] == "risky_action")
    assert risky_desc["risk_level"] == "high"
    assert risky_desc["requires_approval"] is True


# ── 실제 definitions 임포트 스모크 테스트 ─────────────────────────────────

def test_import_definitions() -> None:
    """definitions.py가 오류 없이 임포트되고 도구가 등록되어 있는지 확인."""
    from src.agents.tools.definitions import tool_registry
    names = tool_registry.list_names()
    # 최소 9개 도구가 등록되어 있어야 함
    assert len(names) >= 9, f"등록된 도구 수가 부족합니다: {names}"
    assert "run_a2_work_approval" in names
    assert "run_c2_cold_email" in names
