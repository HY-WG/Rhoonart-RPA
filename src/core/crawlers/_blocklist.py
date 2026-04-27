# -*- coding: utf-8 -*-
"""YouTube Shorts 크롤러 — 블록리스트 관리 (C-1 내부 모듈).

이 모듈은 youtube_shorts_crawler.py 에서만 임포트합니다.
block_channels / unblock_channels 는 스크립트에서 직접 호출할 수 있습니다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))
_BLOCKLIST_PATH = Path("scripts/yt_shorts_blocklist.json")


def load_blocklist() -> set[str]:
    """블록리스트 파일에서 차단된 channel_id 집합 반환."""
    if not _BLOCKLIST_PATH.exists():
        return set()
    with open(_BLOCKLIST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.keys())


def block_channels(entries: list[dict], *, reason: str = "") -> None:
    """채널을 블록리스트에 영구 등록.

    Example::

        from src.core.crawlers._blocklist import block_channels
        block_channels([
            {"channel_id": "UC-X9afa4j1s8o3K-pOeVkNQ", "name": "드라마톡톡"},
        ], reason="드라마 썰 채널 — 판권 영상 아님")
    """
    _BLOCKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, dict] = {}
    if _BLOCKLIST_PATH.exists():
        with open(_BLOCKLIST_PATH, encoding="utf-8") as f:
            data = json.load(f)

    now = datetime.now(KST).isoformat()
    added = 0
    for entry in entries:
        cid = entry.get("channel_id", "")
        if not cid:
            continue
        if cid not in data:
            data[cid] = {
                "name":       entry.get("name", ""),
                "reason":     entry.get("reason", reason),
                "blocked_at": now,
            }
            added += 1
        elif reason:
            data[cid]["reason"] = reason

    with open(_BLOCKLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def unblock_channels(channel_ids: list[str]) -> None:
    """블록리스트에서 특정 채널 제거."""
    if not _BLOCKLIST_PATH.exists():
        return
    with open(_BLOCKLIST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for cid in channel_ids:
        data.pop(cid, None)
    with open(_BLOCKLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
