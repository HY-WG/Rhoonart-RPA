"""SelfHealingLocator — 3단계 폴백 UI 요소 탐색기.

Level 1: 기본 CSS 셀렉터
Level 2: 폴백 셀렉터 목록 (aria-label, text, role 등)
Level 3: Claude Vision — 스크린샷 분석 후 좌표 직접 클릭

현재 상태: STUB — Playwright 컨텍스트 없이 인터페이스만 정의.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LocatorResult:
    """요소 탐색 결과."""
    found: bool
    selector: str = ""          # 성공한 셀렉터
    level: int = 0              # 성공 레벨 (1/2/3)
    element: Any = None         # Playwright ElementHandle (런타임)
    fallback_used: bool = False
    vision_used: bool = False


@dataclass
class LocatorSpec:
    """요소 탐색 명세."""
    primary: str                          # Level 1 셀렉터
    fallbacks: list[str] = field(default_factory=list)  # Level 2 셀렉터 목록
    description: str = ""                 # Level 3 Vision 프롬프트용 설명
    timeout_ms: int = 5_000              # 탐색 타임아웃 (ms)


class SelfHealingLocator:
    """3단계 폴백 로케이터.

    Parameters
    ----------
    llm_client:
        Level 3 Vision 분석에 사용할 LLM 클라이언트.
        미지정 시 Level 2까지만 시도.
    """

    def __init__(self, llm_client: Any = None) -> None:
        self._llm = llm_client

    def find(self, page: Any, spec: LocatorSpec) -> LocatorResult:
        """주어진 페이지에서 LocatorSpec에 따라 요소를 탐색.

        TODO: Playwright 설치 후 구현
        - Level 1: page.locator(spec.primary).first
        - Level 2: for sel in spec.fallbacks: page.locator(sel).first
        - Level 3: screenshot → Claude Vision API → (x, y) → page.mouse.click(x, y)
        """
        raise NotImplementedError(
            "SelfHealingLocator.find() — Playwright 미설치. "
            "pip install playwright && playwright install chromium 후 구현 활성화 필요."
        )

    def _try_primary(self, page: Any, spec: LocatorSpec) -> LocatorResult:
        """Level 1: 기본 CSS 셀렉터 시도 (STUB)."""
        # TODO: page.locator(spec.primary).wait_for(timeout=spec.timeout_ms)
        return LocatorResult(found=False)

    def _try_fallbacks(self, page: Any, spec: LocatorSpec) -> LocatorResult:
        """Level 2: 폴백 셀렉터 목록 순회 (STUB)."""
        # TODO: for sel in spec.fallbacks: try page.locator(sel)...
        return LocatorResult(found=False)

    def _try_vision(self, page: Any, spec: LocatorSpec) -> LocatorResult:
        """Level 3: Claude Vision 스크린샷 분석 (STUB).

        TODO:
        - screenshot_bytes = page.screenshot()
        - 이미지를 base64로 인코딩
        - LLM에 "이 화면에서 {spec.description}의 위치를 JSON {x, y}로 반환" 요청
        - page.mouse.click(x, y)
        """
        return LocatorResult(found=False)
