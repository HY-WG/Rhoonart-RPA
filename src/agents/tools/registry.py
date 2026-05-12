"""Tool Registry — Pydantic 기반 자기 기술(self-describing) 도구 등록소.

각 Tool은 Input Pydantic 모델로 자신의 인자 스키마를 기술한다.
에이전트는 describe_all()로 전체 도구 목록을 LLM 프롬프트에 주입한다.
실행 시 Pydantic model_validate()로 자동 유효성 검사가 수행된다.
"""
from __future__ import annotations

import functools
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolSpec(BaseModel):
    name: str
    description: str
    input_model: type[BaseModel]
    risk_level: RiskLevel = RiskLevel.MEDIUM
    requires_approval: bool = False
    supports_dry_run: bool = True
    # 브라우저 제어 모드 지원 여부 (향후 True로 전환)
    browser_supported: bool = False
    tags: list[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def to_llm_description(self) -> dict[str, Any]:
        """LLM 프롬프트 텍스트에 삽입할 도구 설명 딕셔너리 (레거시 / 디버그용).

        Anthropic native tool_use API 를 사용할 때는 :meth:`to_anthropic_tool` 을
        사용하고, 이 메서드는 로깅·디버그 목적으로만 유지한다.
        """
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "requires_approval": self.requires_approval,
            "supports_dry_run": self.supports_dry_run,
            "browser_supported": self.browser_supported,
            "input_schema": self.input_model.model_json_schema(),
        }

    def to_anthropic_tool(self) -> dict[str, Any]:
        """Anthropic ``tools`` 파라미터 형식으로 변환한다.

        Pydantic ``model_json_schema()`` 가 생성한 스키마에서 ``properties`` /
        ``required`` / ``$defs`` 를 추출하여 Anthropic API 가 요구하는
        ``input_schema`` 구조로 정규화한다.

        Returns:
            ``{"name": ..., "description": ..., "input_schema": {...}}``
            형식의 딕셔너리.  ``input_schema.type`` 은 항상 ``"object"`` 다.
        """
        schema = self.input_model.model_json_schema()
        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": schema.get("properties", {}),
        }
        if "required" in schema:
            input_schema["required"] = schema["required"]
        # 중첩 모델이 있을 때 Pydantic 이 생성하는 $defs 를 그대로 전달
        if "$defs" in schema:
            input_schema["$defs"] = schema["$defs"]
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": input_schema,
        }


class ToolRegistry:
    """도구 등록소.

    @registry.register(...) 데코레이터 또는 register_fn()으로 도구를 등록한다.
    등록된 함수는 Pydantic validated wrapper로 감싸진다.
    """

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}
        self._fns: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        input_model: type[BaseModel],
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        requires_approval: bool = False,
        supports_dry_run: bool = True,
        browser_supported: bool = False,
        tags: list[str] | None = None,
    ) -> Callable:
        """데코레이터 팩토리. 함수를 validated wrapper로 감싸 등록한다."""
        def decorator(fn: Callable) -> Callable:
            self._specs[name] = ToolSpec(
                name=name,
                description=description,
                input_model=input_model,
                risk_level=risk_level,
                requires_approval=requires_approval,
                supports_dry_run=supports_dry_run,
                browser_supported=browser_supported,
                tags=tags or [],
            )

            @functools.wraps(fn)
            def validated_fn(raw_input: dict[str, Any]) -> dict[str, Any]:
                # Pydantic 유효성 검사 — 타입 오류 시 ValidationError 발생
                validated = input_model.model_validate(raw_input)
                return fn(validated)

            self._fns[name] = validated_fn
            return validated_fn

        return decorator

    def call(self, name: str, raw_input: dict[str, Any]) -> dict[str, Any]:
        """이름으로 도구를 조회하여 실행. 미등록 도구는 ValueError."""
        if name not in self._fns:
            raise ValueError(f"등록되지 않은 도구: {name!r}")
        return self._fns[name](raw_input)

    def get_spec(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise ValueError(f"등록되지 않은 도구: {name!r}")
        return self._specs[name]

    def list_names(self) -> list[str]:
        return list(self._specs.keys())

    def describe_all(self) -> list[dict[str, Any]]:
        """전체 도구의 LLM 설명 목록 (로깅·디버그용 레거시 메서드).

        Anthropic native tool_use API 를 사용할 때는 :meth:`to_anthropic_tools` 를
        사용하라.
        """
        return [spec.to_llm_description() for spec in self._specs.values()]

    def to_anthropic_tools(self, *, include_finish: bool = True) -> list[dict[str, Any]]:
        """Anthropic ``messages.create(tools=...)`` 파라미터용 도구 목록을 반환한다.

        각 항목은 :meth:`ToolSpec.to_anthropic_tool` 형식이며, ``include_finish=True``
        (기본값) 일 때 LLM 이 작업 완료를 신호할 수 있도록 ``finish`` 가상 도구를
        목록 끝에 추가한다.

        Args:
            include_finish: ``True`` 면 ``finish`` 가상 도구를 목록에 포함한다.

        Returns:
            ``[{"name": ..., "description": ..., "input_schema": {...}}, ...]``
        """
        tools = [spec.to_anthropic_tool() for spec in self._specs.values()]
        if include_finish:
            tools.append({
                "name": "finish",
                "description": (
                    "모든 업무가 완료됐을 때 호출한다. "
                    "완료 요약을 summary 필드에 담아 반환한다."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "완료 내용 한 줄 요약 (한국어)",
                        },
                    },
                    "required": [],
                },
            })
        return tools

    def __contains__(self, name: str) -> bool:
        return name in self._specs
