# -*- coding: utf-8 -*-
"""YouTube Shorts 크롤러 — 공통 유틸리티 (C-1 내부 모듈).

이 모듈은 youtube_shorts_crawler.py 에서만 임포트합니다.
load_seed_urls_from_sheet 는 스크립트·테스트에서 직접 호출할 수 있습니다.
"""
from __future__ import annotations

import os
import re
from typing import Optional

# ── 이메일 추출 정규식 ────────────────────────────────────────────────────
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
_EMAIL_SKIP_DOMAINS = {"youtube.com", "googlemail.com", "google.com", "youtu.be"}


def extract_email_from_description(description: str) -> Optional[str]:
    """채널 설명(description)에서 첫 번째 비즈니스 이메일 주소를 추출.

    YouTube 자체 도메인(@youtube.com, @googlemail.com 등)은 제외합니다.

    Args:
        description: 채널 snippet.description 문자열

    Returns:
        추출된 이메일 주소 또는 None
    """
    if not description:
        return None
    for m in _EMAIL_RE.finditer(description):
        addr = m.group(0).lower()
        domain = addr.split("@", 1)[1]
        if domain not in _EMAIL_SKIP_DOMAINS:
            return addr
    return None


def chunks(lst: list, n: int):
    """리스트를 n개씩 분할하는 제너레이터."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def parse_iso8601_duration(iso: str) -> int:
    """ISO 8601 duration → 초.  ``PT1M30S`` → 90."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def extract_channel_ids_from_search(data: dict) -> list[str]:
    """search.list 응답에서 중복 없는 channelId 목록 추출."""
    seen: set[str] = set()
    result: list[str] = []
    for item in data.get("items", []):
        cid = item.get("snippet", {}).get("channelId", "")
        if cid and cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result


def load_seed_urls_from_sheet(
    sheet_id: str = os.environ.get("SEED_CHANNEL_SHEET_ID", ""),
    gid: str = os.environ.get("SEED_CHANNEL_GID", ""),
) -> list[str]:
    """Google Sheets CSV export에서 URL 열(idx=4) 읽기.

    시드 채널 URL 목록을 구글 시트에서 로드합니다.
    SEED_CHANNEL_SHEET_ID / SEED_CHANNEL_GID 환경 변수가 설정돼 있어야 합니다.
    """
    import csv, io, requests as _req  # noqa: E402
    url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )
    try:
        resp = _req.get(url, timeout=10)
        resp.raise_for_status()
        reader = csv.reader(io.StringIO(resp.text))
        urls: list[str] = []
        for i, row in enumerate(reader):
            if i == 0:
                continue  # 헤더 스킵
            if len(row) > 4 and row[4].strip().startswith("http"):
                urls.append(row[4].strip())
        return urls
    except Exception:
        return []
