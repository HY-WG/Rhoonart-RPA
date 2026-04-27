# -*- coding: utf-8 -*-
"""날짜·시간 파싱 공통 유틸리티.

프로젝트 전체에서 반복되는 타임스탬프 파싱 패턴을 한 곳에 모읍니다.

Functions:
    parse_form_timestamp  — 구글폼 타임스탬프 (오전/오후 한국어 포함) 파싱
    parse_iso_datetime    — ISO 8601 / YouTube API Z-suffix 타임스탬프 파싱
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional


def parse_form_timestamp(ts: str) -> datetime:
    """구글폼 타임스탬프 파싱.

    지원 형식:
        - ``"2024/04/01 오후 3:05:00"``
        - ``"2024/04/01 오전 9:00:00"``
        - ``"2024-04-01T15:05:00"``
        - ``"2024-04-01 15:05:00"``
        - ``"2024. 4. 1 오후 3:05:00"``

    Returns:
        파싱된 naive datetime (timezone 없음)

    Raises:
        ValueError: 지원하지 않는 형식인 경우
    """
    # 오전/오후 → AM/PM (strptime 호환)
    ts = ts.replace("오전", "AM").replace("오후", "PM")
    ts = re.sub(r"\s+", " ", ts).strip()

    _FORMATS = [
        "%Y/%m/%d %p %I:%M:%S",
        "%Y/%m/%d %I:%M:%S %p",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y. %m. %d %p %I:%M:%S",
        "%Y. %m. %d %I:%M:%S %p",
    ]
    for fmt in _FORMATS:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    raise ValueError(f"알 수 없는 타임스탬프 형식: {ts!r}")


def parse_iso_datetime(s: str) -> Optional[datetime]:
    """ISO 8601 타임스탬프 파싱.

    YouTube Data API의 ``"Z"`` suffix(UTC 표시)를 포함한 형식도 지원합니다.

    Examples:
        - ``"2024-04-01T15:05:00+09:00"``  → timezone-aware KST
        - ``"2024-04-01T06:05:00Z"``        → timezone-aware UTC
        - ``"2024-04-01T15:05:00"``         → naive (timezone 없음)

    Returns:
        파싱된 datetime, 또는 파싱 실패 시 None
    """
    if not s:
        return None
    try:
        # Python 3.10 이하에서 "Z"를 직접 처리하지 못하므로 치환
        normalized = s.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None
