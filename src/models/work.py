# -*- coding: utf-8 -*-
"""C-3 신규 작품 등록 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Work:
    """신규 작품 등록 요청 모델.

    Admin 웹에서 "영상 등록" 버튼 클릭 후 채우는 상세 정보 필드와 1:1 대응.
    """

    work_title: str
    rights_holder_name: str             # 회사 선택 (권리사)
    release_year: Optional[int] = None  # 개봉년도
    description: str = ""               # 작품 소개
    director: str = ""                  # 감독
    cast: str = ""                      # 출연
    genre: str = ""                     # 장르 (드라마/영화/예능 등)
    video_type: str = ""                # 영상 타입
    country: str = ""                   # 개봉 국가
    platforms: list[str] = field(default_factory=list)  # 영상 공개 플랫폼
    platform_video_url: str = ""        # 플랫폼 영상 링크
    trailer_url: str = ""               # 영상 예고영상 링크
    source_download_url: str = ""       # 원본 다운로드 링크
    # ── 가이드라인 필드 (레이블리 어드민 '영상 등록' 화면) ─────────────────────────
    guideline_text: str = ""            # 숏츠 제작 가이드 (어드민 직접 입력용 텍스트)
    guideline_link: str = ""            # 가이드라인 링크 (노션 URL 등)
    # ── 시스템 필드 ────────────────────────────────────────────────────────────────
    work_id: Optional[str] = None       # Admin API에서 할당 (등록 후)
