"""BrowserExecutor — 브라우저 제어 기반 도구 실행기.

각 도구의 browser_supported=True 전환 시 이 클래스가 실제 실행을 담당한다.
현재는 STUB 상태 — 인터페이스와 실행 플로우만 정의.

설계 원칙:
  - ToolSpec.browser_supported=False → Lambda 직접 호출 (기존 방식)
  - ToolSpec.browser_supported=True  → BrowserExecutor.execute() 호출
  - 세션 만료 시 BrowserSessionExpiredError → 승인 요청으로 에스컬레이션
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..tools.registry import ToolRegistry
    from .session_manager import BrowserSessionManager
    from .self_healing_locator import SelfHealingLocator

logger = logging.getLogger(__name__)


class BrowserExecutor:
    """브라우저 제어 실행기.

    Parameters
    ----------
    session_manager:
        Playwright 세션 관리자.
    locator:
        SelfHealingLocator 인스턴스.
    tool_registry:
        도구 등록소 (browser_supported 여부 확인용).
    """

    def __init__(
        self,
        session_manager: "BrowserSessionManager",
        locator: "SelfHealingLocator",
        tool_registry: "ToolRegistry | None" = None,
    ) -> None:
        self._sessions = session_manager
        self._locator = locator
        self._tools = tool_registry

    def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """브라우저 기반으로 도구 실행.

        TODO: 각 tool_name별 browser action 구현
        현재는 NotImplementedError로 stub 명시.

        Raises
        ------
        BrowserSessionExpiredError:
            세션이 만료된 경우 (상위에서 ApprovalRequest로 전환).
        NotImplementedError:
            아직 구현되지 않은 도구.
        """
        logger.info("BrowserExecutor.execute: tool=%s (STUB)", tool_name)
        raise NotImplementedError(
            f"브라우저 제어 미구현: {tool_name}. "
            "Playwright 설치 및 각 도구 browser action 구현 후 활성화 필요."
        )

    # ── 도구별 브라우저 액션 (STUB, 순서대로 구현 예정) ───────────────────

    def _a2_work_approval_browser(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """A-2: Slack 메시지 확인 → Admin 패널에서 승인 처리 (STUB).

        TODO:
        1. session_manager.get_context("admin") 로 컨텍스트 획득
        2. Admin 패널 접속 → 작품사용신청 목록 페이지 이동
        3. SelfHealingLocator로 해당 신청 행 탐색
        4. 승인 버튼 클릭
        5. Google Drive 권한 부여 확인
        """
        raise NotImplementedError("A-2 브라우저 액션 미구현")

    def _b2_weekly_report_browser(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """B-2: 네이버 클립 채널 페이지 브라우저 크롤링 (STUB).

        TODO:
        1. session_manager.get_context("naver") 로 컨텍스트 획득
        2. https://clip.naver.com/hashtag/{식별코드} 접속
        3. SelfHealingLocator로 조회수 컨테이너 탐색
        4. 스크롤 후 데이터 수집
        """
        raise NotImplementedError("B-2 브라우저 액션 미구현")

    def _c1_lead_filter_browser(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """C-1: YouTube Shorts 채널 탐색 브라우저 크롤링 (STUB).

        NOTE: C-1은 YouTube Data API 기반으로 이미 구현됨.
        브라우저 방식은 API 할당량 소진 시 폴백으로만 사용 예정.
        """
        raise NotImplementedError("C-1 브라우저 액션 미구현 (API 방식 우선)")
