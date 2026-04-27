# -*- coding: utf-8 -*-
"""C-3 작품 가이드라인 데이터 모델 (Pydantic).

레이블리 어드민 '영상 등록' 화면의 가이드라인 관련 7개 항목을 구조화합니다.
권리사의 요청 사항을 이 모델로 파싱한 뒤, 등록 방식(어드민 직접 기입 vs 노션 페이지)을
자동으로 판단하여 처리합니다.

복잡도 판단 기준 (should_use_notion):
  - 텍스트 필드 합산 300자 초과
  - 단일 필드 줄바꿈 2회 이상 (멀티라인 → 가독성상 노션 권장)
  - URL 포함 (http:// or https://)
  - format_guide 단독 50자 초과 (포맷 요구사항이 상세한 경우)
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

# ── 복잡도 임계값 (노션 페이지 생성 전환 기준) ─────────────────────────────────
NOTION_TOTAL_CHAR_THRESHOLD  = 300   # 텍스트 필드 합산 글자 수
NOTION_NEWLINE_THRESHOLD     = 2     # 단일 필드 내 줄바꿈 수
NOTION_FORMAT_GUIDE_THRESHOLD = 50   # format_guide 단독 글자 수
_URL_RE = re.compile(r"https?://")


class WorkGuideline(BaseModel):
    """작품 가이드라인 — 7개 항목 (권리사 요청 기반).

    모든 항목은 Optional: 권리사가 별도 요청하지 않은 항목은 생략 가능.
    """

    # 1. 작품 소스 제공일
    source_provided_date: Optional[date] = Field(
        default=None,
        description="영상 권리사 측에서 작품 소스를 제공하는 날짜",
    )

    # 2. 영상 업로드 가능일
    upload_available_date: Optional[date] = Field(
        default=None,
        description="영상 제작 완료 후 채널에 게시 가능한 날짜",
    )

    # 3. 작품 관련 가이드 (주의사항)
    usage_notes: Optional[str] = Field(
        default=None,
        description="작품 사용 시 주의해야 하는 사항 (자유 텍스트)",
    )

    # 4. 영상 포맷 가이드
    format_guide: Optional[str] = Field(
        default=None,
        description="영상 제목/설명란에 들어가야 하는 문구 또는 해시태그",
    )

    # 5. 타 플랫폼 업로드 가능 여부
    other_platforms: Optional[str] = Field(
        default=None,
        description=(
            "유튜브 외 타 플랫폼(네이버 클립/카카오톡 숏폼) 업로드 가능 여부. "
            "예: '네이버 클립 가능 / 카카오 숏폼 불가'"
        ),
    )

    # 6. 작품 로고·자막 제공 여부
    logo_subtitle_provided: Optional[bool] = Field(
        default=None,
        description="True=제공 / False=미제공",
    )

    # 7. 업로드 전 검수 진행 여부
    review_required: Optional[bool] = Field(
        default=None,
        description="True=검수 필요 / False=검수 불필요",
    )

    # 수익 쉐어 — 정산팀 협의 완료 전까지 고정 문구 사용
    revenue_share_note: str = Field(
        default="수익 배분 비율은 정산팀과 협의 중입니다.",
        description="수익 쉐어 안내 문구 (정산팀 협의 보류 중)",
    )

    # ── 유틸리티 메서드 ──────────────────────────────────────────────────────────

    def is_empty(self) -> bool:
        """가이드라인 7개 항목이 모두 비어 있는지 확인."""
        return all(v is None for v in [
            self.source_provided_date,
            self.upload_available_date,
            self.usage_notes,
            self.format_guide,
            self.other_platforms,
            self.logo_subtitle_provided,
            self.review_required,
        ])

    def should_use_notion(self) -> bool:
        """복잡도 기준으로 노션 페이지 생성 여부를 반환.

        Returns:
            True  → 노션 페이지 생성 후 '가이드라인 링크' 칸에 URL 삽입
            False → 어드민 '숏츠 제작 가이드' 칸에 텍스트 직접 입력
        """
        text_fields = [
            self.usage_notes or "",
            self.format_guide or "",
            self.other_platforms or "",
        ]

        # 조건 1: 텍스트 합산 300자 초과
        if sum(len(t) for t in text_fields) > NOTION_TOTAL_CHAR_THRESHOLD:
            return True

        # 조건 2: 단일 필드 줄바꿈 2회 이상
        if any(t.count("\n") >= NOTION_NEWLINE_THRESHOLD for t in text_fields):
            return True

        # 조건 3: URL 포함
        if any(_URL_RE.search(t) for t in text_fields):
            return True

        # 조건 4: format_guide 단독 50자 초과
        if len(self.format_guide or "") > NOTION_FORMAT_GUIDE_THRESHOLD:
            return True

        return False

    def to_admin_text(self) -> str:
        """레이블리 어드민 '숏츠 제작 가이드' 칸에 입력할 플레인 텍스트 생성.

        should_use_notion()가 False일 때 사용.
        포함된 항목만 출력하며, 빈 항목은 생략.
        """
        lines: list[str] = []

        if self.source_provided_date:
            lines.append(f"[소스 제공일] {self.source_provided_date.strftime('%Y.%m.%d')}")

        if self.upload_available_date:
            lines.append(f"[업로드 가능일] {self.upload_available_date.strftime('%Y.%m.%d')}")

        if self.usage_notes:
            lines.append(f"[작품 가이드]\n{self.usage_notes}")

        if self.format_guide:
            lines.append(f"[포맷 가이드]\n{self.format_guide}")

        if self.other_platforms is not None:
            lines.append(f"[타 플랫폼 업로드] {self.other_platforms}")

        if self.logo_subtitle_provided is not None:
            val = "제공" if self.logo_subtitle_provided else "미제공"
            lines.append(f"[로고/자막] {val}")

        if self.review_required is not None:
            val = "검수 필요" if self.review_required else "검수 불필요"
            lines.append(f"[업로드 전 검수] {val}")

        lines.append(f"[수익 배분] {self.revenue_share_note}")

        return "\n\n".join(lines)

    def to_notion_blocks(self, work_title: str) -> list[dict]:
        """노션 페이지 본문 블록 리스트 생성 (Notion API children 형식).

        create_guideline_page()에서 내부적으로 사용.
        """
        def heading(text: str) -> dict:
            return {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            }

        def paragraph(text: str) -> dict:
            return {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            }

        def divider() -> dict:
            return {"object": "block", "type": "divider", "divider": {}}

        blocks: list[dict] = [
            heading(f"{work_title} 제작 가이드라인"),
            divider(),
        ]

        if self.source_provided_date:
            blocks += [
                heading("소스 제공일"),
                paragraph(self.source_provided_date.strftime("%Y년 %m월 %d일")),
            ]

        if self.upload_available_date:
            blocks += [
                heading("영상 업로드 가능일"),
                paragraph(self.upload_available_date.strftime("%Y년 %m월 %d일")),
            ]

        if self.usage_notes:
            blocks += [heading("작품 관련 가이드"), paragraph(self.usage_notes)]

        if self.format_guide:
            blocks += [heading("영상 포맷 가이드"), paragraph(self.format_guide)]

        if self.other_platforms is not None:
            blocks += [
                heading("타 플랫폼 업로드 가능 여부"),
                paragraph(self.other_platforms),
            ]

        if self.logo_subtitle_provided is not None:
            val = "제공" if self.logo_subtitle_provided else "미제공"
            blocks += [heading("로고 / 자막"), paragraph(val)]

        if self.review_required is not None:
            val = "업로드 전 검수 필요" if self.review_required else "업로드 전 검수 불필요"
            blocks += [heading("검수 여부"), paragraph(val)]

        blocks += [
            divider(),
            heading("수익 배분"),
            paragraph(self.revenue_share_note),
        ]

        return blocks
