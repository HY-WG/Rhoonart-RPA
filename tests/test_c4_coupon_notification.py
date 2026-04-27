# -*- coding: utf-8 -*-
"""C-4. 수익 100% 쿠폰 신청 처리 알림 단위 테스트.

검증 항목:
  1. 쿠폰 키워드("쿠폰", "100%") 포함 메시지 → 처리 진행
  2. 키워드 없는 메시지 → skipped 반환
  3. Sheets append + Slack DM이 정상 호출되는지
  4. run_on_completion — kakao_notifier=None 시 graceful stub 반환
"""
from __future__ import annotations

from datetime import datetime

import pytest
import pytz

from src.handlers.c4_coupon_notification import (
    is_coupon_request,
    run_on_slack_message,
    run_on_completion,
)
from tests.fakes import FakeNotifier

KST = pytz.timezone("Asia/Seoul")


# ── FakeSheets helpers ────────────────────────────────────────────────────────

class FakeWorksheet:
    def __init__(self) -> None:
        self.appended: list[list] = []

    def append_row(self, row: list) -> None:
        self.appended.append(row)


class FakeSpreadsheet:
    def __init__(self) -> None:
        self._ws = FakeWorksheet()

    def worksheet(self, _name: str) -> FakeWorksheet:
        return self._ws


class FakeSheetsClient:
    def __init__(self) -> None:
        self._sh = FakeSpreadsheet()

    def open_by_key(self, _key: str) -> FakeSpreadsheet:
        return self._sh

    @property
    def worksheet(self) -> FakeWorksheet:
        return self._sh._ws


# ── 테스트 ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("수익 100% 쿠폰 신청합니다",      True),
    ("쿠폰 발급 요청드립니다",          True),
    ("100% 수익 설정 부탁드려요",       True),
    ("일반 문의입니다",                 False),
    ("안녕하세요 테스트 메시지",        False),
])
def test_is_coupon_request(text: str, expected: bool) -> None:
    assert is_coupon_request(text) is expected


def test_run_on_slack_message_processes_coupon_request() -> None:
    """쿠폰 키워드 포함 메시지 → Sheets 기록 + Slack DM 발송."""
    sheets_client = FakeSheetsClient()
    slack_notifier = FakeNotifier(send_result=True)
    fixed_time = datetime(2026, 4, 24, 10, 0, 0, tzinfo=KST)

    result = run_on_slack_message(
        creator_name="테스트 크리에이터",
        slack_message_text="수익 100% 쿠폰 신청합니다",
        sheets_client=sheets_client,
        coupon_sheet_id="sheet-id",
        coupon_sheet_tab="쿠폰신청",
        slack_notifier=slack_notifier,
        admin_slack_user_id="U01ADMIN",
        labelive_admin_url="https://labelive.io",
        requested_at=fixed_time,
    )

    assert result.get("skipped") is not True
    assert result["creator_name"] == "테스트 크리에이터"
    assert result["sheet_appended"] is True
    assert result["slack_dm_sent"] is True
    assert result["kakao_sent"] is False  # 완료 알림은 별도 플로우

    # Sheets에 행이 추가됐는지 확인
    appended = sheets_client.worksheet.appended
    assert len(appended) == 1
    assert appended[0][0] == "테스트 크리에이터"
    assert appended[0][2] == "대기"

    # Slack DM이 담당자 ID로 발송됐는지 확인
    assert len(slack_notifier.sent) == 1
    assert slack_notifier.sent[0]["recipient"] == "U01ADMIN"
    assert "레이블리" in slack_notifier.sent[0]["message"]


def test_run_on_slack_message_skips_non_coupon() -> None:
    """쿠폰 키워드 없는 메시지 → skipped 반환, 부작용 없음."""
    sheets_client = FakeSheetsClient()
    slack_notifier = FakeNotifier()

    result = run_on_slack_message(
        creator_name="테스트",
        slack_message_text="일반 문의입니다",
        sheets_client=sheets_client,
        coupon_sheet_id="sheet-id",
        coupon_sheet_tab="쿠폰신청",
        slack_notifier=slack_notifier,
        admin_slack_user_id="U01ADMIN",
    )

    assert result["skipped"] is True
    assert sheets_client.worksheet.appended == []
    assert slack_notifier.sent == []


def test_run_on_completion_without_kakao_notifier() -> None:
    """kakao_notifier=None 시 graceful stub 반환 (에러 없음)."""
    fixed_time = datetime(2026, 4, 24, 15, 0, 0, tzinfo=KST)

    result = run_on_completion(
        creator_name="완료 크리에이터",
        creator_phone="01012345678",
        kakao_notifier=None,
        completed_at=fixed_time,
    )

    assert result["creator_name"] == "완료 크리에이터"
    assert result["kakao_sent"] is False


def test_run_on_slack_message_sheet_failure_graceful() -> None:
    """Sheets 기록 실패해도 Slack DM은 발송 시도, 결과에 sheet_appended=False."""

    class FailingSheets:
        def open_by_key(self, _key):
            raise RuntimeError("시트 접근 실패")

    slack_notifier = FakeNotifier(send_result=True)
    fixed_time = datetime(2026, 4, 24, 10, 0, 0, tzinfo=KST)

    result = run_on_slack_message(
        creator_name="크리에이터",
        slack_message_text="쿠폰 신청",
        sheets_client=FailingSheets(),
        coupon_sheet_id="sheet-id",
        coupon_sheet_tab="쿠폰신청",
        slack_notifier=slack_notifier,
        admin_slack_user_id="U01ADMIN",
        requested_at=fixed_time,
    )

    assert result["sheet_appended"] is False
    assert result["slack_dm_sent"] is True  # Slack은 Sheets 실패와 무관하게 발송
