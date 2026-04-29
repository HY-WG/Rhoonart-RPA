"""Task Classifier — raw 이벤트를 task_id로 분류.

rule-based 분류: Slack 채널명, HTTP 경로, 이벤트 필드 기반.
LLM 없이 결정적으로 동작하여 오류 내성이 높다.
"""
from __future__ import annotations

import re
from typing import Any


# Slack 채널명 → task_id 매핑
_SLACK_CHANNEL_TASK_MAP: dict[str, str] = {
    "작품사용신청-알림": "A-2",
    "작품사용신청":      "A-2",
    "work-approval":     "A-2",
}

# HTTP 경로 패턴 → task_id 매핑
_HTTP_PATH_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"/a2|/work.?approval", re.I), "A-2"),
    (re.compile(r"/a3|/naver.?clip", re.I),    "A-3"),
    (re.compile(r"/b2|/weekly.?report", re.I), "B-2"),
    (re.compile(r"/c1|/lead.?filter", re.I),   "C-1"),
    (re.compile(r"/c2|/cold.?email", re.I),    "C-2"),
]


def classify_slack_event(event: dict[str, Any], channel_name: str = "") -> str | None:
    """Slack 이벤트를 task_id로 분류. 인식 불가면 None."""
    # 채널 이름 기반
    for key, task_id in _SLACK_CHANNEL_TASK_MAP.items():
        if key in channel_name:
            return task_id
    # 텍스트 패턴 기반 (A-2 시그니처)
    text = event.get("text", "")
    if "신규 영상 사용 요청" in text or "작품사용신청" in text:
        return "A-2"
    return None


def classify_http_request(path: str, body: dict[str, Any] | None = None) -> str | None:
    """HTTP 경로 + 바디를 task_id로 분류."""
    for pattern, task_id in _HTTP_PATH_PATTERNS:
        if pattern.search(path):
            return task_id
    # 바디에 명시적 task_id가 있으면 그대로 사용
    if body and "task_id" in body:
        return body["task_id"]
    return None


def classify_email_message(subject: str, sender: str = "") -> str | None:
    """Incoming email subject/body based routing."""
    normalized_subject = subject or ""
    if "YouTube 채널 액세스를 위한 초대" in normalized_subject:
        return "A-0"
    if sender and "youtube" in sender.lower() and "초대" in normalized_subject:
        return "A-0"
    return None


def classify_cron_event(source: str) -> str | None:
    """크론 이벤트 소스 이름을 task_id로 분류."""
    mapping = {
        "a3-monthly-end": "A-3",
        "a3-monthly-start": "A-3",
        "b2-weekly": "B-2",
        "c1-monthly": "C-1",
    }
    return mapping.get(source)
