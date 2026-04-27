# -*- coding: utf-8 -*-
"""C-3. 신규 작품 등록 핸들러.

== 업무 개요 ==

레이블리 어드민에 새로운 영상(작품)을 등록할 때 실행합니다.

프로세스:
  STEP 1 (기본정보)  작품 제목 기반으로 기본 정보(제목/출연/장르 등)를 등록합니다.
                     - admin_client.register_work(work) -> work_id 반환
                     - 향후: 작품 제목으로 외부 DB(영화진흥위원회 등) 자동 크롤링 예정

  STEP 2 (가이드라인) 권리사 요청사항을 기반으로 작품 가이드라인을 등록합니다.
                     - WorkGuideline.should_use_notion() == True
                       -> 노션 페이지 자동 생성 후 '가이드라인 링크' 칸에 URL 삽입
                     - WorkGuideline.should_use_notion() == False
                       -> 텍스트 생성 후 '숏츠 제작 가이드' 칸에 직접 입력

== 미결 사항 ==
  - 권리사 이메일 파싱 자동화 (Q2 답변: 이메일로 정보 수신)
    -> 향후 이메일 본문 -> WorkGuideline 변환 로직 추가 예정
  - 작품 기본정보 자동 크롤링 (외부 DB 검색)
    -> 별도 크롤러 모듈로 구현 예정

== AdminAPIClient 교체 방법 ==
  .env의 ADMIN_API_BASE_URL에 값을 입력하면 HttpAdminAPIClient로 자동 전환됩니다.
  Stub -> 실 API 교체 시 코드 수정 불필요.

== 수익 쉐어 ==
  정산팀 협의 완료 전까지 WorkGuideline.revenue_share_note 고정 문구 사용.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..core.logger import CoreLogger
from ..core.clients.admin_api_client import AdminAPIClient, StubAdminAPIClient
from ..core.clients.notion_guideline_client import create_guideline_page
from ..models.work import Work
from ..models.work_guideline import WorkGuideline

log = CoreLogger(__name__)

TASK_ID   = "C-3"
TASK_NAME = "신규 작품 등록"


# ── 결과 모델 ─────────────────────────────────────────────────────────────────────

@dataclass
class WorkRegisterResult:
    work_title:          str
    rights_holder_name:  str
    work_id:             Optional[str]
    guideline_method:    str             # "admin_text" | "notion_page" | "none" | "skipped"
    guideline_ref:       str             # 어드민 텍스트(일부) 또는 노션 URL
    success:             bool
    message:             str

    def to_dict(self) -> dict:
        return {
            "work_title":         self.work_title,
            "rights_holder_name": self.rights_holder_name,
            "work_id":            self.work_id,
            "guideline_method":   self.guideline_method,
            "guideline_ref":      self.guideline_ref,
            "success":            self.success,
            "message":            self.message,
        }


# ── 공개 진입점 ───────────────────────────────────────────────────────────────────

def run(
    work: Work,
    guideline: Optional[WorkGuideline] = None,
    admin_client: Optional[AdminAPIClient] = None,
    notion_token: str = "",
    notion_parent_page_id: str = "",
    dry_run: bool = False,
) -> dict:
    """C-3 신규 작품 등록 실행.

    Args:
        work:                  등록할 작품 기본정보 (Work 모델)
        guideline:             작품 가이드라인 (WorkGuideline 모델).
                               None이면 가이드라인 등록을 건너뜁니다.
        admin_client:          AdminAPIClient 구현체.
                               None이면 StubAdminAPIClient 자동 사용.
        notion_token:          Notion integration 토큰.
                               미전달 시 환경 변수 NOTION_API_KEY 사용.
        notion_parent_page_id: 가이드라인 페이지를 생성할 부모 페이지 ID.
                               미전달 시 환경 변수 NOTION_GUIDELINE_PARENT_PAGE_ID 사용.
        dry_run:               True이면 실제 API를 호출하지 않고 결과만 시뮬레이션.

    Returns:
        WorkRegisterResult.to_dict()
    """
    client = admin_client or StubAdminAPIClient()

    log.info(
        "[C-3] 작품 등록 시작: '%s' (권리사: %s, dry_run=%s)",
        work.work_title, work.rights_holder_name, dry_run,
    )

    # ── STEP 1: 작품 기본정보 등록 ─────────────────────────────────────────────
    if dry_run:
        log.info("[C-3][dry_run] register_work 건너뜀")
        work_id = "dry-run-work-id"
    else:
        work_id = client.register_work(work)

    if not work_id:
        msg = "작품 기본정보 등록 실패 — 로그 확인"
        log.error("[C-3] %s", msg)
        return WorkRegisterResult(
            work_title=work.work_title,
            rights_holder_name=work.rights_holder_name,
            work_id=None,
            guideline_method="none",
            guideline_ref="",
            success=False,
            message=msg,
        ).to_dict()

    log.info("[C-3] STEP 1 완료: work_id=%s", work_id)

    # ── STEP 2: 가이드라인 등록 ──────────────────────────────────────────────────
    if guideline is None or guideline.is_empty():
        log.info("[C-3] 가이드라인 없음 — STEP 2 건너뜀")
        return WorkRegisterResult(
            work_title=work.work_title,
            rights_holder_name=work.rights_holder_name,
            work_id=work_id,
            guideline_method="skipped",
            guideline_ref="",
            success=True,
            message="등록 완료 (가이드라인 없음)",
        ).to_dict()

    if guideline.should_use_notion():
        result = _register_guideline_notion(
            work_id=work_id,
            work_title=work.work_title,
            guideline=guideline,
            client=client,
            notion_token=notion_token,
            notion_parent_page_id=notion_parent_page_id,
            dry_run=dry_run,
        )
    else:
        result = _register_guideline_text(
            work_id=work_id,
            work_title=work.work_title,
            guideline=guideline,
            client=client,
            dry_run=dry_run,
        )

    log.info("[C-3] 처리 완료: %s", result)
    return result.to_dict()


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────────

def _register_guideline_text(
    work_id: str,
    work_title: str,
    guideline: WorkGuideline,
    client: AdminAPIClient,
    dry_run: bool,
) -> WorkRegisterResult:
    """어드민 '숏츠 제작 가이드' 칸에 텍스트 직접 입력."""
    text = guideline.to_admin_text()
    log.info(
        "[C-3] 가이드라인 방식: admin_text (글자수=%d)", len(text)
    )

    if dry_run:
        log.info("[C-3][dry_run] update_guideline(text) 건너뜀")
        ok = True
    else:
        ok = client.update_guideline(work_id, guideline_text=text)

    preview = text[:60].replace("\n", " ")
    return WorkRegisterResult(
        work_title=work_title,
        rights_holder_name="",
        work_id=work_id,
        guideline_method="admin_text",
        guideline_ref=f"{preview}...",
        success=ok,
        message="가이드라인(텍스트) 등록 완료" if ok else "가이드라인 텍스트 업데이트 실패",
    )


def _register_guideline_notion(
    work_id: str,
    work_title: str,
    guideline: WorkGuideline,
    client: AdminAPIClient,
    notion_token: str,
    notion_parent_page_id: str,
    dry_run: bool,
) -> WorkRegisterResult:
    """노션 페이지 생성 후 어드민 '가이드라인 링크' 칸에 URL 삽입."""
    log.info("[C-3] 가이드라인 방식: notion_page")

    if dry_run:
        log.info("[C-3][dry_run] create_guideline_page 건너뜀")
        page_url = "https://www.notion.so/dry-run-page-id"
        ok       = True
    else:
        page_url = create_guideline_page(
            guideline=guideline,
            work_title=work_title,
            notion_token=notion_token,
            parent_page_id=notion_parent_page_id,
        )

        if not page_url:
            msg = (
                "노션 페이지 생성 실패 — NOTION_API_KEY / "
                "NOTION_GUIDELINE_PARENT_PAGE_ID 환경 변수 확인"
            )
            log.error("[C-3] %s", msg)
            return WorkRegisterResult(
                work_title=work_title,
                rights_holder_name="",
                work_id=work_id,
                guideline_method="notion_page",
                guideline_ref="",
                success=False,
                message=msg,
            )

        ok = client.update_guideline(work_id, guideline_link=page_url)

    return WorkRegisterResult(
        work_title=work_title,
        rights_holder_name="",
        work_id=work_id,
        guideline_method="notion_page",
        guideline_ref=page_url,
        success=ok,
        message="가이드라인(노션 페이지) 등록 완료" if ok else "노션 URL 업데이트 실패",
    )
