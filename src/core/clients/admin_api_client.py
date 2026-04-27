# -*- coding: utf-8 -*-
"""레이블리 어드민 API 클라이언트 서비스 레이어.

실제 API(HttpAdminAPIClient)와 Stub(StubAdminAPIClient)을 동일한 인터페이스로
제공하여, API 엔드포인트 확보 전후 교체가 단 한 줄(build_admin_client 팩토리)로
이루어지도록 설계합니다.

현재 상태:
  - ADMIN_API_BASE_URL 미설정 or 비어 있으면 → StubAdminAPIClient 자동 선택
  - ADMIN_API_BASE_URL 설정 시 → HttpAdminAPIClient 선택

추후 API 엔드포인트 확보 시:
  1. HttpAdminAPIClient.register_work()  의 TODO 제거 후 실제 endpoint 기입
  2. HttpAdminAPIClient.update_guideline() 의 TODO 제거 후 실제 endpoint 기입
  3. .env ADMIN_API_BASE_URL 에 값 입력 → 자동으로 실 API 사용

등록 엔드포인트 (추정, 확보 후 수정):
  POST   {base}/api/works                     — 작품 기본정보 등록
  PATCH  {base}/api/works/{work_id}/guideline — 가이드라인 업데이트

인증 방식:
  Supabase Edge Function 전용 헤더 (session 있을 때):
    X-Intern-Session: {session}
    X-Intern-Token:   {token}
  표준 Bearer (session 없을 때):
    Authorization: Bearer {token}
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import requests as http_requests

from ...core.logger import CoreLogger
from ...models.work import Work

log = CoreLogger(__name__)

# ── 추정 엔드포인트 경로 — 확보 후 수정 ──────────────────────────────────────────
_PATH_REGISTER_WORK = "/api/works"
_PATH_UPDATE_GUIDE  = "/api/works/{work_id}/guideline"


# ── 추상 인터페이스 ────────────────────────────────────────────────────────────────

class AdminAPIClient(ABC):
    """레이블리 어드민 API 추상 클라이언트.

    모든 구현체가 동일한 메서드 시그니처를 제공해야 합니다.
    """

    @abstractmethod
    def register_work(self, work: Work) -> Optional[str]:
        """작품 기본정보 등록.

        Args:
            work: 등록할 작품 정보 (Work 모델)

        Returns:
            work_id (str) — 등록 성공 시 어드민에서 부여된 ID
            None           — 등록 실패
        """

    @abstractmethod
    def update_guideline(
        self,
        work_id: str,
        guideline_text: Optional[str] = None,
        guideline_link: Optional[str] = None,
    ) -> bool:
        """작품 가이드라인 업데이트.

        두 필드 중 하나 이상을 전달합니다.

        Args:
            work_id:        register_work()에서 반환된 작품 ID
            guideline_text: '숏츠 제작 가이드' 칸에 입력할 텍스트
            guideline_link: '가이드라인 링크' 칸에 입력할 노션 URL

        Returns:
            True  — 업데이트 성공
            False — 업데이트 실패
        """


# ── Stub 구현 (API 미확보 시 사용) ────────────────────────────────────────────────

class StubAdminAPIClient(AdminAPIClient):
    """Stub 구현 — 실제 API 없이 로그만 출력합니다.

    개발/테스트 환경 또는 ADMIN_API_BASE_URL 미설정 시 자동 선택됩니다.
    실제 API 확보 후에도 단위 테스트에서 계속 사용합니다.
    """

    def register_work(self, work: Work) -> Optional[str]:
        stub_id = f"stub-{abs(hash(work.work_title)) % 100_000:05d}"
        log.info(
            "[AdminAPI][Stub] register_work: title=%s rights=%s -> work_id=%s",
            work.work_title, work.rights_holder_name, stub_id,
        )
        return stub_id

    def update_guideline(
        self,
        work_id: str,
        guideline_text: Optional[str] = None,
        guideline_link: Optional[str] = None,
    ) -> bool:
        log.info(
            "[AdminAPI][Stub] update_guideline: work_id=%s has_text=%s has_link=%s",
            work_id, bool(guideline_text), bool(guideline_link),
        )
        if guideline_text:
            preview = guideline_text[:80].replace("\n", " ")
            log.debug("[AdminAPI][Stub] guideline_text preview: %s...", preview)
        if guideline_link:
            log.debug("[AdminAPI][Stub] guideline_link: %s", guideline_link)
        return True


# ── HTTP 구현 (실제 API 확보 후 사용) ────────────────────────────────────────────

class HttpAdminAPIClient(AdminAPIClient):
    """HTTP 실제 구현 — 레이블리 어드민 API와 통신합니다.

    TODO: 개발팀으로부터 실제 엔드포인트 경로와 페이로드 스펙을 수령한 후
          register_work()와 update_guideline()의 TODO 블록을 채워 넣어야 합니다.
    """

    def __init__(self, base_url: str, token: str, session: str = "") -> None:
        self._base    = base_url.rstrip("/")
        self._headers = self._build_headers(token, session)

    @staticmethod
    def _build_headers(token: str, session: str) -> dict:
        if session:
            return {
                "X-Intern-Session": session,
                "X-Intern-Token":   token,
                "Content-Type":     "application/json",
            }
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }

    def register_work(self, work: Work) -> Optional[str]:
        """작품 기본정보 등록 (POST /api/works).

        TODO: 개발팀 API 명세 수령 후 아래 payload 키를 실제 필드명으로 수정할 것.
        """
        endpoint = f"{self._base}{_PATH_REGISTER_WORK}"
        payload = {
            # TODO: 실제 API 필드명으로 교체
            "title":               work.work_title,
            "rights_holder":       work.rights_holder_name,
            "release_year":        work.release_year,
            "description":         work.description,
            "director":            work.director,
            "cast":                work.cast,
            "genre":               work.genre,
            "video_type":          work.video_type,
            "country":             work.country,
            "platforms":           work.platforms,
            "platform_video_url":  work.platform_video_url,
            "trailer_url":         work.trailer_url,
            "source_download_url": work.source_download_url,
        }
        try:
            resp = http_requests.post(
                endpoint, json=payload, headers=self._headers, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()
            work_id = str(data.get("id") or data.get("work_id") or "")
            log.info("[AdminAPI] register_work 완료: work_id=%s", work_id)
            return work_id or None
        except Exception as e:
            log.error("[AdminAPI] register_work 실패 (%s): %s", endpoint, e)
            return None

    def update_guideline(
        self,
        work_id: str,
        guideline_text: Optional[str] = None,
        guideline_link: Optional[str] = None,
    ) -> bool:
        """가이드라인 업데이트 (PATCH /api/works/{work_id}/guideline).

        TODO: 개발팀 API 명세 수령 후 아래 payload 키와 HTTP 메서드를 확인할 것.
              엔드포인트 경로(_PATH_UPDATE_GUIDE)도 실제 경로로 교체 필요.
        """
        if not guideline_text and not guideline_link:
            return True  # 업데이트할 내용 없음

        endpoint = f"{self._base}{_PATH_UPDATE_GUIDE.format(work_id=work_id)}"
        payload: dict = {}
        if guideline_text is not None:
            # TODO: 실제 API 필드명으로 교체 (예: shorts_guide, guide_text 등)
            payload["shorts_guide"] = guideline_text
        if guideline_link is not None:
            # TODO: 실제 API 필드명으로 교체 (예: guideline_url, guide_link 등)
            payload["guideline_link"] = guideline_link

        try:
            resp = http_requests.patch(
                endpoint, json=payload, headers=self._headers, timeout=15
            )
            resp.raise_for_status()
            log.info("[AdminAPI] update_guideline 완료: work_id=%s", work_id)
            return True
        except Exception as e:
            log.error("[AdminAPI] update_guideline 실패 (work_id=%s): %s", work_id, e)
            return False


# ── 팩토리 ────────────────────────────────────────────────────────────────────────

def build_admin_client(
    base_url: str = "",
    token: str = "",
    session: str = "",
) -> AdminAPIClient:
    """환경에 따라 적절한 AdminAPIClient 구현체를 반환합니다.

    - base_url이 비어 있거나 미설정 → StubAdminAPIClient
    - base_url이 설정되어 있음      → HttpAdminAPIClient

    사용 예:
        from src.core.clients.admin_api_client import build_admin_client
        client = build_admin_client(
            base_url=os.environ.get("ADMIN_API_BASE_URL", ""),
            token=os.environ.get("ADMIN_API_TOKEN", ""),
            session=os.environ.get("X_INTERN_SESSION", ""),
        )
    """
    if not base_url:
        log.info("[AdminAPI] ADMIN_API_BASE_URL 미설정 -> StubAdminAPIClient 사용")
        return StubAdminAPIClient()

    log.info("[AdminAPI] HttpAdminAPIClient 사용: %s", base_url)
    return HttpAdminAPIClient(base_url, token, session)
