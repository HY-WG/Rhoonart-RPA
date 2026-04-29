"""Input Gateway 파서 & 분류기 단위 테스트."""
from __future__ import annotations

import pytest

from src.agents.gateway.classifier import (
    classify_http_request,
    classify_slack_event,
)
from src.agents.gateway.models import TaskEnvelope, TriggerType
from src.agents.gateway.parsers import (
    parse_cold_email,
    parse_http_weekly_report,
    parse_lead_filter,
    parse_manual,
    parse_slack_work_approval,
)


# ── A-2 슬랙 파서 ─────────────────────────────────────────────────────────

A2_VALID_TEXT = '채널: "유호영" 의 신규 영상 사용 요청이 있습니다.\n21세기 대군부인'
A2_VALID_TEXT_SINGLE = "채널: 유호영 의 신규 영상 사용 요청이 있습니다.\n21세기 대군부인"

A2_SLACK_EVENT = {
    "type": "message",
    "text": A2_VALID_TEXT,
    "channel": "C작품사용신청",
    "ts": "1714000000.000001",
}


def test_parse_slack_a2_channel_name() -> None:
    envelope = parse_slack_work_approval(A2_SLACK_EVENT)
    assert envelope.context["channel_name"] == "유호영"


def test_parse_slack_a2_work_title() -> None:
    envelope = parse_slack_work_approval(A2_SLACK_EVENT)
    assert envelope.context["work_title"] == "21세기 대군부인"


def test_parse_slack_a2_task_id() -> None:
    envelope = parse_slack_work_approval(A2_SLACK_EVENT)
    assert envelope.task_id == "A-2"


def test_parse_slack_a2_trigger_type() -> None:
    envelope = parse_slack_work_approval(A2_SLACK_EVENT)
    assert envelope.trigger_type == TriggerType.SLACK


def test_parse_slack_a2_slack_ids() -> None:
    envelope = parse_slack_work_approval(A2_SLACK_EVENT)
    assert envelope.context["slack_channel_id"] == "C작품사용신청"
    assert envelope.context["slack_message_ts"] == "1714000000.000001"


def test_parse_slack_a2_without_quotes() -> None:
    """따옴표 없는 채널명도 파싱돼야 한다."""
    event = {**A2_SLACK_EVENT, "text": A2_VALID_TEXT_SINGLE}
    envelope = parse_slack_work_approval(event)
    assert envelope.context["channel_name"] == "유호영"


def test_parse_slack_a2_dry_run_flag() -> None:
    envelope = parse_slack_work_approval(A2_SLACK_EVENT, dry_run=True)
    assert envelope.dry_run is True
    assert envelope.context["dry_run"] is True


def test_parse_slack_a2_too_few_lines_raises() -> None:
    bad_event = {**A2_SLACK_EVENT, "text": "줄이 하나뿐입니다."}
    with pytest.raises(ValueError, match="줄 수 부족"):
        parse_slack_work_approval(bad_event)


def test_parse_slack_a2_bad_format_raises() -> None:
    bad_event = {**A2_SLACK_EVENT, "text": "전혀 다른 형식의 메시지\n작품명"}
    with pytest.raises(ValueError, match="채널명 파싱 실패"):
        parse_slack_work_approval(bad_event)


# ── B-2 HTTP 파서 ─────────────────────────────────────────────────────────

def test_parse_http_b2_task_id() -> None:
    envelope = parse_http_weekly_report({})
    assert envelope.task_id == "B-2"


def test_parse_http_b2_trigger_type() -> None:
    envelope = parse_http_weekly_report({})
    assert envelope.trigger_type == TriggerType.HTTP


def test_parse_http_b2_rights_holders() -> None:
    envelope = parse_http_weekly_report({"rights_holders": ["웨이브", "판씨네마"]})
    assert envelope.context["rights_holders"] == ["웨이브", "판씨네마"]


# ── C-1 파서 ─────────────────────────────────────────────────────────────

def test_parse_lead_filter_task_id() -> None:
    envelope = parse_lead_filter({})
    assert envelope.task_id == "C-1"


def test_parse_lead_filter_cron_trigger() -> None:
    """바디가 비면 CRON 트리거로 인식."""
    envelope = parse_lead_filter({})
    assert envelope.trigger_type == TriggerType.CRON


def test_parse_lead_filter_http_trigger() -> None:
    """바디가 있으면 HTTP 트리거로 인식."""
    envelope = parse_lead_filter({"source": "manual"})
    assert envelope.trigger_type == TriggerType.HTTP


# ── C-2 파서 ─────────────────────────────────────────────────────────────

def test_parse_cold_email_task_id() -> None:
    envelope = parse_cold_email({})
    assert envelope.task_id == "C-2"


def test_parse_cold_email_default_batch_size() -> None:
    envelope = parse_cold_email({})
    assert envelope.context["batch_size"] == 10


def test_parse_cold_email_custom_batch() -> None:
    envelope = parse_cold_email({"batch_size": 50})
    assert envelope.context["batch_size"] == 50


# ── 범용 수동 파서 ────────────────────────────────────────────────────────

def test_parse_manual_fields() -> None:
    envelope = parse_manual("X-1", "테스트 지시", {"key": "val"}, dry_run=True)
    assert envelope.task_id == "X-1"
    assert envelope.instruction == "테스트 지시"
    assert envelope.context["key"] == "val"
    assert envelope.dry_run is True
    assert envelope.trigger_type == TriggerType.MANUAL


def test_parse_manual_empty_context() -> None:
    envelope = parse_manual("X-2", "지시")
    assert envelope.context == {}


# ── Classifier — Slack ────────────────────────────────────────────────────

def test_classify_slack_by_channel_name() -> None:
    assert classify_slack_event({}, "작품사용신청-알림") == "A-2"
    assert classify_slack_event({}, "작품사용신청") == "A-2"


def test_classify_slack_by_text() -> None:
    event = {"text": "신규 영상 사용 요청이 있습니다."}
    assert classify_slack_event(event, "") == "A-2"


def test_classify_slack_unknown_returns_none() -> None:
    assert classify_slack_event({"text": "안녕하세요"}, "general") is None


# ── Classifier — HTTP ─────────────────────────────────────────────────────

@pytest.mark.parametrize("path,expected", [
    ("/a2/work-approval", "A-2"),
    ("/api/a2/trigger", "A-2"),
    ("/b2/weekly-report", "B-2"),
    ("/api/b2/trigger", "B-2"),
    ("/c1/lead-filter", "C-1"),
    ("/c2/cold-email", "C-2"),
    ("/naver-clip", "A-3"),
])
def test_classify_http_paths(path: str, expected: str) -> None:
    assert classify_http_request(path) == expected


def test_classify_http_unknown_returns_none() -> None:
    assert classify_http_request("/unknown/path") is None


def test_classify_http_body_task_id_override() -> None:
    result = classify_http_request("/unknown", {"task_id": "D-3"})
    assert result == "D-3"


# ── TaskEnvelope serialization ────────────────────────────────────────────

def test_envelope_to_dict_roundtrip() -> None:
    envelope = parse_slack_work_approval(A2_SLACK_EVENT)
    d = envelope.to_dict()
    assert d["task_id"] == "A-2"
    assert d["trigger_type"] == "slack"
    assert "envelope_id" in d
    assert "created_at" in d


def test_envelope_has_unique_id() -> None:
    e1 = parse_manual("A-2", "지시 1")
    e2 = parse_manual("A-2", "지시 2")
    assert e1.envelope_id != e2.envelope_id
