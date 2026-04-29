"""Input Gateway — 외부 이벤트를 받아 에이전트를 실행하는 단일 진입점.

사용 예:
    gateway = InputGateway(agent=my_agent)
    result = gateway.handle_slack(event, channel_name="작품사용신청-알림")
    result = gateway.handle_http(path="/b2/weekly-report", body={})
    result = gateway.handle_manual("A-2", "작품 사용 신청 처리", dry_run=True)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .classifier import classify_email_message, classify_http_request, classify_slack_event
from .models import TaskEnvelope
from .parsers import (
    parse_cold_email,
    parse_email_admin_channel_invite,
    parse_http_weekly_report,
    parse_lead_filter,
    parse_manual,
    parse_slack_work_approval,
)

if TYPE_CHECKING:
    from ..runtime.agent import RhoArtAgent

logger = logging.getLogger(__name__)

# task_id → 파서 함수 매핑 (슬랙 전용)
_SLACK_PARSERS = {
    "A-2": parse_slack_work_approval,
}

# task_id → 파서 함수 매핑 (HTTP 전용)
_HTTP_PARSERS = {
    "B-2": parse_http_weekly_report,
    "C-1": parse_lead_filter,
    "C-2": parse_cold_email,
}

_EMAIL_PARSERS = {
    "A-0": parse_email_admin_channel_invite,
}


class InputGateway:
    """에이전트 입력 게이트웨이.

    분류 → 파싱 → 에이전트 실행을 조율한다.
    파싱 오류는 상위로 전파하되, 분류 실패는 명시적 에러 딕셔너리를 반환한다.
    """

    def __init__(self, agent: "RhoArtAgent") -> None:
        self._agent = agent

    # ── Slack ────────────────────────────────────────────────────────────

    def handle_slack(
        self,
        event: dict[str, Any],
        channel_name: str = "",
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Slack Event API 페이로드를 처리."""
        task_id = classify_slack_event(event, channel_name)
        if task_id is None:
            logger.warning("Slack 이벤트 분류 실패: channel=%s", channel_name)
            return {"status": "ignored", "reason": "분류 불가 Slack 이벤트"}

        parser = _SLACK_PARSERS.get(task_id)
        if parser is None:
            return {"status": "error", "reason": f"task_id={task_id} 슬랙 파서 없음"}

        envelope = parser(event, dry_run=dry_run)
        return self._run(envelope)

    # ── HTTP ─────────────────────────────────────────────────────────────

    def handle_http(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """HTTP POST 요청을 처리."""
        body = body or {}
        # body 안에 dry_run 플래그가 있으면 우선 적용
        dry_run = body.pop("dry_run", dry_run)

        task_id = classify_http_request(path, body)
        if task_id is None:
            return {"status": "error", "reason": f"인식할 수 없는 경로: {path}"}

        parser = _HTTP_PARSERS.get(task_id)
        if parser is None:
            # 범용 수동 파서로 폴백
            envelope = parse_manual(task_id, f"{task_id} 업무 수행", body, dry_run=dry_run)
        else:
            envelope = parser(body, dry_run=dry_run)

        return self._run(envelope)

    def handle_email(
        self,
        message: dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Email inbox event processing."""
        task_id = classify_email_message(
            str(message.get("subject", "")),
            str(message.get("sender", "")),
        )
        if task_id is None:
            return {"status": "ignored", "reason": "분류 불가 email event"}

        parser = _EMAIL_PARSERS.get(task_id)
        if parser is None:
            return {"status": "error", "reason": f"task_id={task_id} email parser 없음"}

        envelope = parser(message, dry_run=dry_run)
        return self._run(envelope)

    # ── Manual ───────────────────────────────────────────────────────────

    def handle_manual(
        self,
        task_id: str,
        instruction: str,
        context: dict[str, Any] | None = None,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """대시보드·스크립트 수동 호출."""
        envelope = parse_manual(task_id, instruction, context, dry_run=dry_run)
        return self._run(envelope)

    # ── Envelope 직접 주입 (테스트용) ────────────────────────────────────

    def handle_envelope(self, envelope: TaskEnvelope) -> dict[str, Any]:
        """이미 생성된 TaskEnvelope를 직접 실행 (테스트 / 재시도 용)."""
        return self._run(envelope)

    # ── 내부 ─────────────────────────────────────────────────────────────

    def _run(self, envelope: TaskEnvelope) -> dict[str, Any]:
        """에이전트 실행 후 결과 반환."""
        logger.info(
            "게이트웨이 실행: task_id=%s envelope_id=%s dry_run=%s",
            envelope.task_id, envelope.envelope_id, envelope.dry_run,
        )
        return self._agent.run(envelope.to_dict())
