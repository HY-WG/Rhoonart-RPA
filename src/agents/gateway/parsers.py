"""Input parsers — 각 트리거 소스별 raw 입력 → TaskEnvelope 변환.

각 파서는 parse(raw) → TaskEnvelope 를 구현한다.
파서는 순수 함수 스타일로 작성하여 단위 테스트가 쉽다.
"""
from __future__ import annotations

import re
from typing import Any

from .models import TaskEnvelope, TriggerType

# ── A-2 슬랙 메시지 파서 ────────────────────────────────────────────────
# 포맷:
#   채널: "유호영" 의 신규 영상 사용 요청이 있습니다.
#   21세기 대군부인

_A2_CHANNEL_RE = re.compile(
    r'채널:\s*["“”]?([^\"“”\n]+)["“”]?\s*의\s*신규\s*영상\s*사용\s*요청'
)


def parse_slack_work_approval(
    slack_event: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    """Slack Event API 페이로드 → A-2 작품사용신청 TaskEnvelope.

    Parameters
    ----------
    slack_event:
        Slack Event API `event` 딕셔너리.
        필수 키: text, channel, ts
    dry_run:
        True면 실제 권한 부여·메일 발송 없이 시뮬레이션.

    Raises
    ------
    ValueError:
        메시지 파싱 실패 또는 필수 필드 누락 시.
    """
    text: str = slack_event.get("text", "")
    channel_id: str = slack_event.get("channel", "")
    message_ts: str = slack_event.get("ts", "")

    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError(f"A-2 메시지 파싱 실패: 줄 수 부족 ({len(lines)}줄)")

    match = _A2_CHANNEL_RE.search(lines[0])
    if not match:
        raise ValueError(f"A-2 채널명 파싱 실패: {lines[0]!r}")

    channel_name = match.group(1).strip()
    work_title = lines[1]

    return TaskEnvelope(
        task_id="A-2",
        instruction=(
            f"작품사용신청 처리: 크리에이터 '{channel_name}'이(가) "
            f"'{work_title}' 작품의 사용을 신청했습니다. "
            f"이메일 조회, Drive 파일 검색, 뷰어 권한 부여, 승인 메일 발송을 순서대로 수행하세요."
        ),
        context={
            "channel_name": channel_name,
            "work_title": work_title,
            "slack_channel_id": channel_id,
            "slack_message_ts": message_ts,
            "dry_run": dry_run,
        },
        trigger_type=TriggerType.SLACK,
        trigger_source=channel_id,
        dry_run=dry_run,
    )


# ── B-2 HTTP 요청 파서 ──────────────────────────────────────────────────

def parse_http_weekly_report(
    body: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    """HTTP POST 바디 → B-2 주간성과보고 TaskEnvelope."""
    rights_holders = body.get("rights_holders", [])
    return TaskEnvelope(
        task_id="B-2",
        instruction=(
            "주간 성과 보고서를 생성하세요. "
            "네이버 클립 조회수를 크롤링하고, Looker 대시보드 링크와 함께 "
            "권리사별 보고 메일을 발송하세요."
        ),
        context={
            "rights_holders": rights_holders,
            "dry_run": dry_run,
        },
        trigger_type=TriggerType.HTTP,
        trigger_source="api",
        dry_run=dry_run,
    )


# ── C-1 크론/HTTP 파서 ──────────────────────────────────────────────────

def parse_lead_filter(
    body: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    """HTTP 바디 또는 크론 이벤트 → C-1 리드발굴 TaskEnvelope."""
    return TaskEnvelope(
        task_id="C-1",
        instruction=(
            "YouTube Shorts 채널 탐색을 실행하세요. "
            "드라마·영화 클립 채널을 발굴하고 등급별로 분류하여 리드 시트에 저장하세요."
        ),
        context={
            "dry_run": dry_run,
            **{k: v for k, v in body.items() if k != "dry_run"},
        },
        trigger_type=TriggerType.HTTP if body else TriggerType.CRON,
        trigger_source=body.get("source", "cron"),
        dry_run=dry_run,
    )


# ── C-2 수동/크론 파서 ──────────────────────────────────────────────────

def parse_cold_email(
    body: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    """HTTP 바디 → C-2 콜드메일 TaskEnvelope."""
    return TaskEnvelope(
        task_id="C-2",
        instruction=(
            "콜드메일 발송을 실행하세요. "
            "리드 시트에서 발송 대상을 조회하고 개인화 메일을 발송하세요."
        ),
        context={
            "batch_size": body.get("batch_size", 10),
            "genre": body.get("genre"),
            "min_monthly_views": body.get("min_monthly_views"),
            "platform": body.get("platform"),
            "dry_run": dry_run,
        },
        trigger_type=TriggerType.HTTP,
        trigger_source="api",
        dry_run=dry_run,
    )


# ── 범용 수동 파서 ──────────────────────────────────────────────────────

def parse_manual(
    task_id: str,
    instruction: str,
    context: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    """대시보드 수동 실행용 범용 파서."""
    return TaskEnvelope(
        task_id=task_id,
        instruction=instruction,
        context=context or {},
        trigger_type=TriggerType.MANUAL,
        trigger_source="dashboard",
        dry_run=dry_run,
    )


def parse_email_admin_channel_invite(
    message: dict[str, Any],
    *,
    dry_run: bool = False,
) -> TaskEnvelope:
    """Normalize an admin invite email into an A-0 envelope."""
    subject = str(message.get("subject", "")).strip()
    recipient = str(message.get("recipient", "")).strip()
    accept_url = str(message.get("accept_url", "")).strip()
    sender = str(message.get("sender", "")).strip()
    snippet = str(message.get("snippet", "")).strip()

    if not subject:
        raise ValueError("A-0 email parse failed: subject is required")
    if not accept_url:
        raise ValueError("A-0 email parse failed: accept_url is required")

    return TaskEnvelope(
        task_id="A-0",
        instruction=(
            f"관리자 메일함에서 '{subject}' 메일이 감지되었습니다. "
            "초대 수락 링크를 Playwright로 열고 레이블리 어드민 승인 절차를 진행하기 전에 "
            "사람 승인 체크포인트를 통과해야 합니다."
        ),
        context={
            "recipient": recipient,
            "sender": sender,
            "subject": subject,
            "accept_url": accept_url,
            "snippet": snippet,
            "dry_run": dry_run,
        },
        trigger_type=TriggerType.EMAIL,
        trigger_source=sender or "mailbox",
        dry_run=dry_run,
    )
