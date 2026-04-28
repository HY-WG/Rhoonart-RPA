"""RhoArtAgent — 동기 ReAct 루프 구현.

흐름:
  Observe → Think → (요승인?) Pause / Act → Reflect → 반복 or 완료

주요 설계 원칙:
  - LLM 클라이언트는 생성자 주입 (FakeLLMClient로 단위 테스트 가능)
  - 승인 필요 도구: checkpoint 저장 후 즉시 반환 (스레드 점유 없음)
  - resume_from_checkpoint(): ApprovalQueue가 재개 시 호출
  - MAX_STEPS 초과 시 FAILED 상태로 안전 종료
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Protocol

from .models import AgentState, AgentTrace, Thought

if TYPE_CHECKING:
    from ..approval.queue import ApprovalQueue
    from ..repository import IAgentTraceRepository
    from ..tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

MAX_STEPS = 15          # 루프 안전 상한
REFLECT_THRESHOLD = 0.5  # 확신도가 이 값 미만이면 추가 관찰 수행


# ── LLM 클라이언트 프로토콜 ──────────────────────────────────────────────
class ILLMClient(Protocol):
    """Anthropic 클라이언트 또는 FakeLLMClient가 구현해야 할 인터페이스."""
    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
    ) -> str: ...


class AnthropicLLMClient:
    """실제 Anthropic API 래퍼."""
    def __init__(self, api_key: str | None = None) -> None:
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
    ) -> str:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        return response.content[0].text


class FakeLLMClient:
    """테스트용 결정적(deterministic) LLM 클라이언트.

    responses 큐를 순서대로 반환. 비면 마지막 응답 반복.
    응답은 JSON 문자열 (Thought 스키마) 또는 임의 텍스트.
    """
    def __init__(self, responses: list[str]) -> None:
        self._queue = list(responses)

    def create_message(self, *, model: str, max_tokens: int,
                       system: str, messages: list[dict[str, Any]]) -> str:
        if self._queue:
            return self._queue.pop(0)
        return json.dumps({
            "reasoning": "기본 완료 응답",
            "selected_tool": "finish",
            "tool_input": {},
            "requires_approval": False,
            "risk_level": "low",
            "confidence": 1.0,
        })


# ── Agent ────────────────────────────────────────────────────────────────
class RhoArtAgent:
    """루나트 RPA 에이전트.

    Parameters
    ----------
    tool_registry:
        실행 가능한 도구 등록소.
    approval_queue:
        승인 대기열 (고위험 도구 Pause 용).
    trace_repo:
        실행 이력 저장소 (조회 / 감사).
    llm_client:
        LLM 클라이언트 (미지정 시 AnthropicLLMClient 자동 생성).
    model:
        사용할 Claude 모델 ID.
    dry_run_override:
        True면 모든 도구를 dry_run=True로 강제 실행.
    """

    def __init__(
        self,
        tool_registry: "ToolRegistry",
        approval_queue: "ApprovalQueue",
        trace_repo: "IAgentTraceRepository",
        llm_client: ILLMClient | None = None,
        model: str = "claude-3-5-haiku-20241022",
        dry_run_override: bool = False,
    ) -> None:
        self._tools = tool_registry
        self._approval_queue = approval_queue
        self._trace_repo = trace_repo
        self._model = model
        self._dry_run_override = dry_run_override

        if llm_client is None:
            self._llm = AnthropicLLMClient()
        else:
            self._llm = llm_client

    # ── Public API ───────────────────────────────────────────────────────

    def run(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """에이전트 메인 진입점.

        Parameters
        ----------
        envelope:
            TaskEnvelope 직렬화 딕셔너리.
            필수 키: task_id, envelope_id, instruction, context
        """
        task_id = envelope.get("task_id", "unknown")
        envelope_id = envelope.get("envelope_id", "unknown")

        trace = AgentTrace(task_id=task_id, envelope_id=envelope_id)
        logger.info("에이전트 시작: trace_id=%s task_id=%s", trace.trace_id, task_id)

        result = self._react_loop(envelope, trace)
        self._trace_repo.save(trace)
        return result

    def resume_from_checkpoint(
        self,
        pending_thought: Thought,
        trace: AgentTrace,
    ) -> dict[str, Any]:
        """ApprovalQueue.approve() 에서 호출 — checkpoint에서 Act 단계 재개."""
        # 승인이 완료된 thought로 즉시 Act 수행
        envelope_step = next(
            (s for s in reversed(trace.steps) if s.tool_input and "envelope_id" in (s.tool_input or {})),
            None,
        )
        # envelope 재구성 (checkpoint에서 전달받아야 하므로 trace 외부에서 처리)
        # — ApprovalQueue._resume_from_checkpoint 에서 envelope을 직접 주입하므로
        #   여기서는 pending_thought 기준으로 Act 재개만 수행
        logger.info(
            "체크포인트 재개: trace_id=%s tool=%s",
            trace.trace_id, pending_thought.selected_tool,
        )

        tool_output = self._act(pending_thought, trace)
        result = self._reflect(pending_thought, tool_output, trace)

        # resume 후 추가 루프가 필요한 경우 (도구 출력에 continue_loop 플래그)
        if result.get("continue_loop") and len(trace.steps) < MAX_STEPS:
            # envelope 없이 추가 루프는 제한적으로만 허용
            logger.info("재개 후 추가 루프 실행 불가 (envelope 없음) — 현재 결과 반환")

        trace.status = AgentState.COMPLETED
        trace.finished_at = datetime.now(timezone.utc)
        self._trace_repo.save(trace)
        return result

    # ── ReAct 루프 ───────────────────────────────────────────────────────

    def _react_loop(self, envelope: dict[str, Any], trace: AgentTrace) -> dict[str, Any]:
        """Observe → Think → Act → Reflect 반복."""
        observation = self._observe(envelope, trace)
        last_output: dict[str, Any] = {}

        for _ in range(MAX_STEPS):
            # ── THINK ──
            thought = self._think(envelope, observation, trace)

            # 완료 신호
            if thought.selected_tool == "finish":
                trace.status = AgentState.COMPLETED
                trace.finished_at = datetime.now(timezone.utc)
                return {
                    "status": "completed",
                    "trace_id": trace.trace_id,
                    "reasoning": thought.reasoning,
                    "last_output": last_output,
                }

            # ── 승인 필요 여부 판단 ──
            needs_approval = self._needs_approval(thought)
            if needs_approval:
                return self._pause_for_approval(envelope, thought, trace)

            # ── ACT ──
            tool_output = self._act(thought, trace)

            # ── REFLECT ──
            result = self._reflect(thought, tool_output, trace)

            if result.get("status") == "failed":
                trace.status = AgentState.FAILED
                trace.finished_at = datetime.now(timezone.utc)
                return result

            last_output = tool_output

            # 다음 루프를 위한 observation 갱신
            observation = {
                "previous_tool": thought.selected_tool,
                "previous_output": tool_output,
                "step_num": len(trace.steps),
            }

            if not result.get("continue_loop", True):
                trace.status = AgentState.COMPLETED
                trace.finished_at = datetime.now(timezone.utc)
                return {
                    "status": "completed",
                    "trace_id": trace.trace_id,
                    "last_output": last_output,
                }

        # MAX_STEPS 초과
        trace.record(AgentState.FAILED, error="MAX_STEPS 초과")
        trace.status = AgentState.FAILED
        trace.finished_at = datetime.now(timezone.utc)
        return {
            "status": "failed",
            "trace_id": trace.trace_id,
            "error": f"최대 스텝 수({MAX_STEPS})를 초과했습니다.",
        }

    # ── 단계별 메서드 ─────────────────────────────────────────────────────

    def _observe(self, envelope: dict[str, Any], trace: AgentTrace) -> dict[str, Any]:
        """Observe 단계: 현재 컨텍스트를 수집하여 observation 딕셔너리 반환."""
        trace.record(AgentState.OBSERVING)
        context = envelope.get("context", {})
        return {
            "instruction": envelope.get("instruction", ""),
            "task_id": envelope.get("task_id", ""),
            "context": context,
            "available_tools": self._tools.list_names(),
            "step_num": 0,
        }

    def _think(
        self,
        envelope: dict[str, Any],
        observation: dict[str, Any],
        trace: AgentTrace,
    ) -> Thought:
        """Think 단계: LLM에 프롬프트를 보내고 Thought를 파싱."""
        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(envelope, observation, trace)

        raw_response = self._llm.create_message(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        thought = self._parse_thought(raw_response)

        # dry_run 강제 적용
        if self._dry_run_override and "dry_run" in thought.tool_input:
            thought.tool_input["dry_run"] = True

        trace.record(AgentState.THINKING, thought=thought)
        logger.debug(
            "Think 완료: tool=%s confidence=%.2f",
            thought.selected_tool, thought.confidence,
        )
        return thought

    def _act(self, thought: Thought, trace: AgentTrace) -> dict[str, Any]:
        """Act 단계: 선택된 도구를 실행하고 결과를 반환."""
        tool_name = thought.selected_tool
        tool_input = thought.tool_input

        trace.record(
            AgentState.ACTING,
            thought=thought,
            tool_name=tool_name,
            tool_input=tool_input,
        )

        try:
            output = self._tools.call(tool_name, tool_input)
            trace.record(
                AgentState.REFLECTING,  # 결과 기록은 REFLECTING 직전 스텝에 붙임
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=output,
            )
            logger.info("도구 실행 성공: %s → status=%s", tool_name, output.get("status"))
            return output
        except Exception as exc:
            error_msg = str(exc)
            trace.record(
                AgentState.REFLECTING,
                tool_name=tool_name,
                tool_input=tool_input,
                error=error_msg,
            )
            logger.warning("도구 실행 실패: %s — %s", tool_name, error_msg)
            return {"status": "error", "error": error_msg}

    def _reflect(
        self,
        thought: Thought,
        tool_output: dict[str, Any],
        trace: AgentTrace,
    ) -> dict[str, Any]:
        """Reflect 단계: 도구 출력을 평가하여 계속 여부 결정."""
        trace.record(AgentState.REFLECTING, tool_output=tool_output)

        status = tool_output.get("status", "")
        if status == "error":
            return {
                "status": "failed",
                "trace_id": trace.trace_id,
                "error": tool_output.get("error", "알 수 없는 오류"),
                "continue_loop": False,
            }

        # dry_run이면 단일 도구 실행 후 완료
        if tool_output.get("dry_run"):
            return {"status": "completed", "dry_run": True, "continue_loop": False, **tool_output}

        # 도구 출력에 명시적 continue 플래그가 있으면 우선 적용
        if "continue_loop" in tool_output:
            return {**tool_output, "trace_id": trace.trace_id}

        # 기본: 단일 도구 실행 후 완료
        return {
            "status": "completed",
            "trace_id": trace.trace_id,
            "continue_loop": False,
            **tool_output,
        }

    def _pause_for_approval(
        self,
        envelope: dict[str, Any],
        thought: Thought,
        trace: AgentTrace,
    ) -> dict[str, Any]:
        """승인 대기: ApprovalQueue에 체크포인트 저장 후 즉시 반환."""
        from ..approval.models import ApprovalRequest

        trace.record(
            AgentState.AWAITING_APPROVAL,
            thought=thought,
            tool_name=thought.selected_tool,
            tool_input=thought.tool_input,
        )
        trace.status = AgentState.AWAITING_APPROVAL

        checkpoint = trace.to_checkpoint(envelope, thought)
        request = ApprovalRequest(
            trace_id=trace.trace_id,
            task_id=trace.task_id,
            summary=thought.reasoning,
            risk_level=thought.risk_level,
            preview=thought.tool_input,
            checkpoint=checkpoint,
        )
        approval_id = self._approval_queue.create(request)
        trace.finished_at = datetime.now(timezone.utc)
        self._trace_repo.save(trace)

        logger.info(
            "승인 대기: trace_id=%s approval_id=%s tool=%s",
            trace.trace_id, approval_id, thought.selected_tool,
        )
        return {
            "status": "awaiting_approval",
            "trace_id": trace.trace_id,
            "approval_id": approval_id,
            "tool": thought.selected_tool,
            "preview": thought.tool_input,
        }

    # ── 승인 필요 여부 판단 ───────────────────────────────────────────────

    def _needs_approval(self, thought: Thought) -> bool:
        """도구 스펙 + Thought 자체 판단을 결합하여 승인 필요 여부 결정."""
        # Thought 자체 플래그
        if thought.requires_approval:
            return True
        # dry_run 모드면 승인 불필요
        if thought.tool_input.get("dry_run"):
            return False
        # 등록된 도구 스펙 확인
        if thought.selected_tool in self._tools:
            spec = self._tools.get_spec(thought.selected_tool)
            return spec.requires_approval
        return False

    # ── 프롬프트 빌더 ─────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        tools_desc = json.dumps(self._tools.describe_all(), ensure_ascii=False, indent=2)
        return f"""당신은 루나르트(Rhoonart) 업무 자동화 에이전트입니다.
주어진 업무 지시(instruction)를 분석하여 적합한 도구를 선택하고 실행합니다.

## 사용 가능한 도구
{tools_desc}

## 응답 형식 (JSON 필수)
다음 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요:
{{
  "reasoning": "판단 근거 (한국어)",
  "selected_tool": "도구 이름 또는 'finish'",
  "tool_input": {{}},
  "requires_approval": false,
  "risk_level": "low|medium|high|critical",
  "confidence": 0.0~1.0
}}

## 규칙
1. 업무가 완료되었거나 더 이상 수행할 도구가 없으면 selected_tool을 "finish"로 설정하세요.
2. 고위험(high/critical) 작업 또는 데이터를 영구 변경하는 작업은 requires_approval을 true로 설정하세요.
3. 확실하지 않으면 dry_run=true로 먼저 테스트하세요.
4. 한 번에 하나의 도구만 선택하세요.
"""

    def _build_user_message(
        self,
        envelope: dict[str, Any],
        observation: dict[str, Any],
        trace: AgentTrace,
    ) -> str:
        recent_steps = [s.to_dict() for s in trace.steps[-5:]]  # 최근 5 스텝만
        return json.dumps({
            "instruction": envelope.get("instruction", ""),
            "context": envelope.get("context", {}),
            "observation": observation,
            "recent_steps": recent_steps,
        }, ensure_ascii=False, indent=2)

    # ── 파싱 ─────────────────────────────────────────────────────────────

    def _parse_thought(self, raw: str) -> Thought:
        """LLM 응답 텍스트에서 Thought 객체 파싱.

        JSON 블록이 있으면 추출, 없으면 기본 finish Thought 반환.
        """
        text = raw.strip()

        # ```json ... ``` 또는 ``` ... ``` 블록 추출
        if "```" in text:
            start = text.find("```")
            end = text.rfind("```")
            if start != end:
                inner = text[start + 3:end].strip()
                if inner.startswith("json"):
                    inner = inner[4:].strip()
                text = inner

        try:
            data = json.loads(text)
            return Thought.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Thought 파싱 실패 (%s) — finish로 폴백", exc)
            return Thought(
                reasoning=f"응답 파싱 실패: {raw[:200]}",
                selected_tool="finish",
                tool_input={},
                confidence=0.0,
            )
