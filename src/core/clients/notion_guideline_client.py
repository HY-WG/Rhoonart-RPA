# -*- coding: utf-8 -*-
"""노션 가이드라인 페이지 생성 클라이언트.

'복잡한 가이드라인'(WorkGuideline.should_use_notion() == True)인 경우
Notion API를 호출하여 별도 페이지를 생성하고 공유 URL을 반환합니다.

필수 환경 변수:
  NOTION_API_KEY                  Notion integration 시크릿 토큰
                                  (https://www.notion.so/my-integrations에서 생성)
  NOTION_GUIDELINE_PARENT_PAGE_ID 가이드라인 페이지를 생성할 부모 페이지 ID
                                  (해당 페이지에 integration 접근 권한을 부여해야 함)

주의:
  - 생성된 페이지는 기본적으로 비공개입니다.
  - '가이드라인 링크' 칸에 삽입되는 URL은 내부 Notion URL입니다.
  - 외부 공개가 필요한 경우 담당자가 수동으로 '웹에 게시' 설정 후 링크 교체 필요.
    (Notion API는 Share-to-web 설정을 직접 지원하지 않음)
"""
from __future__ import annotations

import os
from typing import Optional

from ...core.logger import CoreLogger
from ...models.work_guideline import WorkGuideline

log = CoreLogger(__name__)


def create_guideline_page(
    guideline: WorkGuideline,
    work_title: str,
    notion_token: str = "",
    parent_page_id: str = "",
) -> Optional[str]:
    """노션 가이드라인 페이지를 생성하고 내부 URL을 반환합니다.

    Args:
        guideline:       WorkGuideline 모델 인스턴스
        work_title:      작품 제목 (페이지 제목에 사용)
        notion_token:    Notion integration 토큰 (미전달 시 환경 변수 사용)
        parent_page_id:  부모 페이지 ID (미전달 시 환경 변수 사용)

    Returns:
        Notion 페이지 내부 URL (str)  — 예: "https://www.notion.so/abcdef123456..."
        None                          — 생성 실패 시

    Raises:
        ImportError: notion-client 패키지 미설치 시
    """
    try:
        from notion_client import Client
        from notion_client.errors import APIResponseError
    except ImportError as exc:
        raise ImportError(
            "notion-client 패키지가 설치되지 않았습니다. "
            "pip install notion-client 로 설치하세요."
        ) from exc

    token     = notion_token or os.environ.get("NOTION_API_KEY", "")
    parent_id = parent_page_id or os.environ.get("NOTION_GUIDELINE_PARENT_PAGE_ID", "")

    if not token:
        log.error("[NotionGuideline] NOTION_API_KEY 미설정 — 페이지 생성 불가")
        return None
    if not parent_id:
        log.error("[NotionGuideline] NOTION_GUIDELINE_PARENT_PAGE_ID 미설정 — 페이지 생성 불가")
        return None

    client = Client(auth=token)
    page_title = f"{work_title} 제작 가이드라인"

    try:
        response = client.pages.create(
            parent={"page_id": parent_id},
            properties={
                "title": {
                    "title": [{"type": "text", "text": {"content": page_title}}]
                }
            },
            children=guideline.to_notion_blocks(work_title),
        )

        page_id  = response["id"].replace("-", "")
        page_url = f"https://www.notion.so/{page_id}"

        log.info(
            "[NotionGuideline] 페이지 생성 완료: '%s' -> %s", page_title, page_url
        )
        return page_url

    except APIResponseError as e:
        log.error(
            "[NotionGuideline] Notion API 오류 (%s): %s",
            getattr(e, "code", "unknown"), e,
        )
        return None
    except Exception as e:
        log.error("[NotionGuideline] 페이지 생성 실패: %s", e)
        return None
