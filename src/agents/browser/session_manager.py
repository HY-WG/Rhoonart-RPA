"""Browser Session Manager — Playwright 세션 영속성 관리.

서비스별로 로그인 상태를 JSON 파일에 저장하고 재사용한다.
browser_supported=False 도구가 True로 전환될 때 이 매니저를 주입받는다.

현재 상태: STUB — 실제 Playwright 의존성 없이 인터페이스만 정의.
Playwright가 설치되면 각 메서드의 # TODO 구현체를 활성화한다.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 세션 파일 기본 저장 경로
DEFAULT_SESSION_DIR = Path(".browser_sessions")


class BrowserSessionExpiredError(Exception):
    """세션이 만료되어 재로그인이 필요한 경우 발생."""
    def __init__(self, service: str) -> None:
        super().__init__(f"브라우저 세션 만료: {service}")
        self.service = service


class BrowserSessionManager:
    """서비스별 Playwright 브라우저 컨텍스트 관리자.

    Parameters
    ----------
    session_dir:
        storage_state JSON 파일을 저장할 디렉토리.
    headless:
        True면 헤드리스 모드로 브라우저 실행.
    """

    def __init__(
        self,
        session_dir: Path | str = DEFAULT_SESSION_DIR,
        headless: bool = True,
    ) -> None:
        self._session_dir = Path(session_dir)
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._headless = headless
        self._contexts: dict[str, Any] = {}   # service → BrowserContext (런타임)

    # ── 세션 경로 ─────────────────────────────────────────────────────────

    def session_path(self, service: str) -> Path:
        """서비스별 storage_state JSON 파일 경로."""
        return self._session_dir / f"{service}.json"

    def has_session(self, service: str) -> bool:
        """저장된 세션 파일이 존재하는지 확인."""
        return self.session_path(service).exists()

    # ── 저장 / 로드 ──────────────────────────────────────────────────────

    def save_session(self, service: str, storage_state: dict[str, Any]) -> None:
        """storage_state 딕셔너리를 파일로 저장."""
        path = self.session_path(service)
        path.write_text(json.dumps(storage_state, ensure_ascii=False, indent=2))
        logger.info("세션 저장: %s → %s", service, path)

    def load_session(self, service: str) -> dict[str, Any]:
        """저장된 storage_state 파일 로드.

        Raises
        ------
        BrowserSessionExpiredError:
            세션 파일이 없을 때.
        """
        path = self.session_path(service)
        if not path.exists():
            raise BrowserSessionExpiredError(service)
        data = json.loads(path.read_text())
        logger.info("세션 로드: %s ← %s", service, path)
        return data

    def delete_session(self, service: str) -> None:
        """세션 파일 삭제 (로그아웃 처리)."""
        path = self.session_path(service)
        if path.exists():
            path.unlink()
            logger.info("세션 삭제: %s", service)

    # ── Playwright 컨텍스트 (STUB) ────────────────────────────────────────

    def get_context(self, service: str) -> Any:
        """서비스에 해당하는 BrowserContext 반환 (또는 신규 생성).

        TODO: Playwright 설치 후 구현
        - playwright.chromium.launch(headless=self._headless)
        - browser.new_context(storage_state=self.load_session(service))
        - self._contexts[service] = context
        """
        raise NotImplementedError(
            f"BrowserSessionManager.get_context() — Playwright 미설치 (service={service}). "
            "pip install playwright && playwright install chromium 후 구현 활성화 필요."
        )

    def close_all(self) -> None:
        """열린 모든 컨텍스트 종료.

        TODO: Playwright 설치 후 구현
        - for ctx in self._contexts.values(): await ctx.close()
        """
        self._contexts.clear()
        logger.info("모든 브라우저 컨텍스트 종료 (stub)")
