"""ReAct Agent 런타임 상태 모델.

AgentState  — 에이전트 FSM 상태
Thought     — Think 단계 출력 (LLM 판단 결과)
TraceStep   — 단일 루프 스텝 레코드 (직렬화 가능)
AgentTrace  — 전체 실행 이력 (체크포인트 포함)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class AgentState(str, Enum):
    OBSERVING = "observing"
    THINKING = "thinking"
    AWAITING_APPROVAL = "awaiting_approval"
    ACTING = "acting"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Thought:
    """LLM Think 단계의 구조화된 출력."""
    reasoning: str                        # 판단 근거 (자연어)
    selected_tool: str                    # 호출할 도구 이름
    tool_input: dict[str, Any]            # 도구 입력 파라미터
    requires_approval: bool = False       # 승인 필요 여부 (에이전트 자체 판단)
    risk_level: str = "medium"            # 자체 평가 위험도
    confidence: float = 0.8              # 0.0 ~ 1.0 확신도

    def to_dict(self) -> dict[str, Any]:
        return {
            "reasoning": self.reasoning,
            "selected_tool": self.selected_tool,
            "tool_input": self.tool_input,
            "requires_approval": self.requires_approval,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Thought":
        return cls(
            reasoning=data["reasoning"],
            selected_tool=data["selected_tool"],
            tool_input=data["tool_input"],
            requires_approval=data.get("requires_approval", False),
            risk_level=data.get("risk_level", "medium"),
            confidence=data.get("confidence", 0.8),
        )


@dataclass
class TraceStep:
    """단일 ReAct 루프 스텝 (직렬화 가능)."""
    step_num: int
    state: AgentState
    thought: dict[str, Any] | None = None    # Thought.to_dict()
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: dict[str, Any] | None = None
    error: str | None = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_num": self.step_num,
            "state": self.state.value,
            "thought": self.thought,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AgentTrace:
    """에이전트 실행 전체 이력.

    - steps: 누적된 TraceStep 목록 (직렬화 가능)
    - record(): 새 스텝 추가 편의 메서드
    - to_checkpoint(): 재개용 직렬화 스냅샷
    """
    trace_id: str = field(default_factory=lambda: f"trc-{uuid4().hex[:12]}")
    task_id: str = ""
    envelope_id: str = ""
    steps: list[TraceStep] = field(default_factory=list)
    status: AgentState = AgentState.OBSERVING
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    finished_at: datetime | None = None

    def record(
        self,
        state: AgentState,
        *,
        thought: Thought | None = None,
        tool_name: str | None = None,
        tool_input: dict[str, Any] | None = None,
        tool_output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> TraceStep:
        """새 TraceStep을 생성·저장하고 반환."""
        step = TraceStep(
            step_num=len(self.steps) + 1,
            state=state,
            thought=thought.to_dict() if thought else None,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            error=error,
        )
        self.steps.append(step)
        self.status = state
        return step

    def to_checkpoint(self, envelope: dict[str, Any], pending_thought: Thought) -> dict[str, Any]:
        """ApprovalQueue 재개용 체크포인트 딕셔너리."""
        return {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "envelope": envelope,
            "trace_steps": [s.to_dict() for s in self.steps],
            "pending_thought": pending_thought.to_dict(),
        }

    def summary(self) -> dict[str, Any]:
        """API 응답 / 저장소 인덱싱용 요약."""
        return {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "steps_count": len(self.steps),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
