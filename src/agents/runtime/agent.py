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
    """Anthropic 클라이언트 또는 FakeLLMClient가 구현해야 할 인터페이스.

    ``create_message`` 는 Anthropic native tool_use 응답 형식으로 반환한다::

        # 도구 호출
        {"type": "tool_use", "name": "run_c1_lead_discovery", "input": {...}}
        # 완료
        {"type": "tool_use", "name": "finish", "input": {"summary": "..."}}
        # 텍스트 전용 (폴백)
        {"type": "text", "text": "..."}
    """
    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...


class AnthropicLLMClient:
    """실제 Anthropic API 래퍼 — native tool_use 모드로 동작한다."""

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
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Anthropic API를 호출하고 첫 번째 tool_use 블록을 반환한다.

        ``tools`` 가 전달되면 native tool_use 모드로 API를 호출한다.
        응답 content 에서 ``tool_use`` 블록을 우선 반환하고, 없으면
        텍스트 블록을 ``{"type": "text", "text": "..."}`` 로 반환한다.
        """
        kwargs: dict[str, Any] = dict(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools

        response = self._client.messages.create(**kwargs)

        for block in response.content:
            if block.type == "tool_use":
                return {"type": "tool_use", "name": block.name, "input": block.input}

        text = next((b.text for b in response.content if hasattr(b, "text")), "")
        return {"type": "text", "text": text}


class FakeLLMClient:
    """테스트용 결정적(deterministic) LLM 클라이언트.

    ``responses`` 큐를 순서대로 반환한다. 큐가 비면
    ``{"type": "tool_use", "name": "finish", "input": {}}`` 를 반환한다.

    두 가지 입력 형식을 모두 지원한다:

    1. **dict** — ``{"type": "tool_use", "name": ..., "input": {...}}``
       그대로 반환 (새 형식).
    2. **str (구 Thought JSON)** — 하위 호환 변환::

           {"reasoning": ..., "selected_tool": "echo", "tool_input": {...}}
           →  {"type": "tool_use", "name": "echo", "input": {...}}

       JSON 파싱 실패 시 ``{"type": "text", "text": <원본 문자열>}`` 반환.
    """

    def __init__(self, responses: list[str | dict[str, Any]]) -> None:
        self._queue: list[str | dict[str, Any]] = list(responses)

    def create_message(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not self._queue:
            return {"type": "tool_use", "name": "finish", "input": {}}

        raw = self._queue.pop(0)

        # 이미 dict 형식 → 그대로 반환
        if isinstance(raw, dict):
            return raw

        # 문자열 → 구 Thought JSON 변환 시도 (하위 호환)
        try:
            data = json.loads(raw)
            tool_name: str = data.get("selected_tool", "finish")
            tool_input: dict[str, Any] = data.get("tool_input", {})
            return {"type": "tool_use", "name": tool_name, "input": tool_input}
        except (json.JSONDecodeError, AttributeError):
            return {"type": "text", "text": str(raw)}


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
        """Think 단계: Anthropic native tool_use API로 LLM을 호출하고 Thought를 반환한다.

        ``self._tools.to_anthropic_tools()`` 로 동적 JSON Schema 목록을 생성하여
        ``tools`` 파라미터로 전달한다. LLM이 반환한 tool_use 블록은
        :meth:`_parse_thought` 에서 :class:`Thought` 로 변환된다.
        """
        system_prompt = self._build_system_prompt()
        user_message = self._build_user_message(envelope, observation, trace)
        tools = self._tools.to_anthropic_tools()

        response = self._llm.create_message(
            model=self._model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=tools,
        )

        thought = self._parse_thought(response)

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
        """도구 스펙과 Thought를 결합하여 승인 필요 여부를 결정한다.

        판단 순서:

        1. ``dry_run=True`` 이면 위험도 무관하게 승인 불필요.
        2. ``thought.requires_approval`` (ToolSpec에서 파생된 플래그) 이 True 이면 승인 필요.
        3. 등록된 ToolSpec 의 ``requires_approval`` 을 최종 확인.
        """
        # dry_run 이면 항상 승인 면제 — 위험 작업도 미리보기 모드에서는 안전
        if thought.tool_input.get("dry_run"):
            return False
        # Thought 에 이미 ToolSpec 기반 플래그가 반영되어 있음
        if thought.requires_approval:
            return True
        # 방어 코드: 직접 ToolSpec 재확인
        if thought.selected_tool in self._tools:
            return self._tools.get_spec(thought.selected_tool).requires_approval
        return False

    # ── 프롬프트 빌더 ─────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """에이전트 시스템 프롬프트를 반환한다.

        Anthropic native tool_use API 를 사용하므로 도구 목록은 프롬프트에
        직접 삽입하지 않는다. ``messages.create(tools=...)`` 파라미터로 전달된
        JSON Schema 를 LLM이 직접 참조한다.
        """
        return (
            "당신은 루나르트(Rhoonart) 업무 자동화 에이전트입니다.\n"
            "주어진 업무 지시(instruction)를 분석하여 적합한 도구를 선택하고 실행합니다.\n"
            "\n"
            "## 규칙\n"
            "1. 업무가 완료되었거나 수행할 도구가 없으면 `finish` 도구를 호출하세요.\n"
            "2. 고위험(high/critical) 작업 또는 데이터를 영구 변경하는 작업은 신중히 검토하세요.\n"
            "3. 확실하지 않으면 dry_run=true 로 먼저 테스트하세요.\n"
            "4. 한 번에 하나의 도구만 선택하세요.\n"
        )

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

    def _parse_thought(self, response: dict[str, Any]) -> Thought:
        """LLM 응답 dict 에서 :class:`Thought` 를 생성한다.

        ``response`` 는 :class:`ILLMClient.create_message` 가 반환한 딕셔너리다.

        처리 규칙:

        * ``type == "tool_use"`` 이고 ``name == "finish"`` → 완료 Thought.
        * ``type == "tool_use"`` 이고 다른 이름 → ToolSpec 에서 위험도·승인 여부를
          읽어 Thought 를 구성한다 (LLM이 별도로 메타 필드를 출력할 필요 없음).
        * ``type == "text"`` 또는 알 수 없는 형식 → finish 폴백.

        Args:
            response: ``ILLMClient.create_message`` 반환값.

        Returns:
            구성된 :class:`Thought` 인스턴스.
        """
        if response.get("type") == "tool_use":
            tool_name: str = response.get("name", "finish")
            tool_input: dict[str, Any] = dict(response.get("input") or {})

            if tool_name == "finish":
                return Thought(
                    reasoning=tool_input.get("summary", "작업 완료"),
                    selected_tool="finish",
                    tool_input={},
                    confidence=1.0,
                )

            # ToolSpec 에서 위험도·승인 여부 파생 (LLM 출력에 의존하지 않음)
            risk_level = "medium"
            requires_approval = False
            if tool_name in self._tools:
                spec = self._tools.get_spec(tool_name)
                risk_level = spec.risk_level.value
                requires_approval = spec.requires_approval

            return Thought(
                reasoning=f"[tool_use] {tool_name}",
                selected_tool=tool_name,
                tool_input=tool_input,
                requires_approval=requires_approval,
                risk_level=risk_level,
                confidence=0.9,
            )

        # 텍스트 응답 또는 알 수 없는 형식 → finish 폴백
        text = response.get("text", "")
        logger.warning("텍스트 응답으로 finish 폴백: %s", text[:100])
        return Thought(
            reasoning=f"텍스트 응답 폴백: {text[:200]}",
            selected_tool="finish",
            tool_input={},
            confidence=0.0,
        )
