# -*- coding: utf-8 -*-
"""D-3. 카카오 오리지널 크리에이터 월초 점검 핸들러 단위 테스트.

검증 항목:
  1. classify_scale — 구독자 수 → 규모 카테고리 경계값 검증
  2. run() — 폼 응답 신규 행 → 출력 시트에 추가됨
  3. run() — 중복 채널명 → 스킵 카운트 증가, 시트 미추가
  4. run() — dry_run=True → 시트에 쓰지 않고 newly_added만 반환
  5. run() — 빈 폼 응답 → newly_added=0
  6. run() — 출력 시트 헤더 없음 → 헤더 자동 생성
  7. run() — 구독자 수 콤마/단위 포함 문자열 파싱
  8. run() — 규모(scale) 컬럼이 자동 계산되어 올바른 위치에 삽입됨
  9. _build_existing_keys — 채널명 기반 중복 키 집합 반환
  10. _generate_headers — col_map + scale_col 로 헤더 자동 생성
"""
from __future__ import annotations

import pytest

from src.handlers.d3_kakao_creator_onboarding import (
    COLUMN_MAP,
    SCALE_SHEET_COL,
    SUBSCRIBER_FORM_COL,
    OnboardingResult,
    _build_existing_keys,
    _build_output_row,
    _generate_headers,
    classify_scale,
    run,
)
from tests.fakes import FakeWorksheet


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────────

def _form_record(**overrides) -> dict:
    """폼 응답 레코드 기본값."""
    defaults = {
        "타임스탬프":         "2024/05/01 오후 3:05:00",
        "채널명":             "테스트채널",
        "유튜브 채널 URL":    "https://youtube.com/@test",
        "카카오 숏폼 채널명": "test_kakao",
        "구독자 수":          "50000",
        "장르":               "드라마",
        "담당자명":           "홍길동",
        "담당자 이메일":      "test@example.com",
        "담당자 연락처":      "010-1234-5678",
    }
    defaults.update(overrides)
    return defaults


def _output_headers() -> list[str]:
    """출력 시트 표준 헤더 (COLUMN_MAP 값 순서 + 규모)."""
    return _generate_headers(COLUMN_MAP, SCALE_SHEET_COL)


def _make_form_ws(records: list[dict]) -> FakeWorksheet:
    """폼 응답 FakeWorksheet 생성."""
    if not records:
        return FakeWorksheet(headers=list(_form_record().keys()), rows=[])
    headers = list(records[0].keys())
    rows = [[str(r.get(h, "")) for h in headers] for r in records]
    return FakeWorksheet(headers=headers, rows=rows)


def _make_output_ws(existing_channel_names: list[str] | None = None) -> FakeWorksheet:
    """출력 시트 FakeWorksheet 생성. 기존 채널 행을 포함할 수 있음."""
    headers = _output_headers()
    rows: list[list[str]] = []
    for name in (existing_channel_names or []):
        row = [""] * len(headers)
        if "채널명" in headers:
            row[headers.index("채널명")] = name
        rows.append(row)
    return FakeWorksheet(headers=headers, rows=rows)


# ── classify_scale 테스트 ────────────────────────────────────────────────────────

class TestClassifyScale:

    @pytest.mark.parametrize("subscribers,expected", [
        (0,           "나노"),
        (9_999,       "나노"),
        (10_000,      "마이크로"),
        (99_999,      "마이크로"),
        (100_000,     "매크로"),
        (999_999,     "매크로"),
        (1_000_000,   "메가"),
        (5_000_000,   "메가"),
    ])
    def test_boundary_values(self, subscribers: int, expected: str) -> None:
        assert classify_scale(subscribers) == expected


# ── 내부 헬퍼 테스트 ──────────────────────────────────────────────────────────────

class TestBuildExistingKeys:

    def test_returns_set_of_channel_names(self) -> None:
        records = [{"채널명": "채널A"}, {"채널명": "채널B"}, {"채널명": ""}]
        keys = _build_existing_keys(records)
        assert "채널A" in keys
        assert "채널B" in keys
        assert "" not in keys  # 빈 값 제외

    def test_empty_records(self) -> None:
        assert _build_existing_keys([]) == set()

    def test_strips_whitespace(self) -> None:
        records = [{"채널명": "  채널A  "}]
        keys = _build_existing_keys(records)
        assert "채널A" in keys


class TestGenerateHeaders:

    def test_scale_col_inserted_after_subscribers(self) -> None:
        headers = _generate_headers(COLUMN_MAP, SCALE_SHEET_COL)
        assert SCALE_SHEET_COL in headers
        if "구독자 수" in headers:
            idx_sub   = headers.index("구독자 수")
            idx_scale = headers.index(SCALE_SHEET_COL)
            assert idx_scale == idx_sub + 1, "규모는 구독자 수 바로 다음에 위치해야 함"

    def test_no_duplicate_scale_col(self) -> None:
        headers = _generate_headers(COLUMN_MAP, SCALE_SHEET_COL)
        assert headers.count(SCALE_SHEET_COL) == 1


class TestBuildOutputRow:

    def test_scale_calculated_from_subscribers(self) -> None:
        record = _form_record(**{"구독자 수": "150000"})
        headers = _output_headers()
        row = _build_output_row(record, headers, COLUMN_MAP, SUBSCRIBER_FORM_COL, SCALE_SHEET_COL)

        scale_idx = headers.index(SCALE_SHEET_COL)
        assert row[scale_idx] == "매크로"

    def test_subscriber_string_with_comma(self) -> None:
        """쉼표가 포함된 구독자 수 파싱."""
        record = _form_record(**{"구독자 수": "1,200,000"})
        headers = _output_headers()
        row = _build_output_row(record, headers, COLUMN_MAP, SUBSCRIBER_FORM_COL, SCALE_SHEET_COL)

        scale_idx = headers.index(SCALE_SHEET_COL)
        assert row[scale_idx] == "메가"

    def test_subscriber_string_with_unit_suffix(self) -> None:
        """'명' 단위가 붙은 구독자 수 파싱."""
        record = _form_record(**{"구독자 수": "5000명"})
        headers = _output_headers()
        row = _build_output_row(record, headers, COLUMN_MAP, SUBSCRIBER_FORM_COL, SCALE_SHEET_COL)

        scale_idx = headers.index(SCALE_SHEET_COL)
        assert row[scale_idx] == "나노"

    def test_row_length_matches_headers(self) -> None:
        record = _form_record()
        headers = _output_headers()
        row = _build_output_row(record, headers, COLUMN_MAP, SUBSCRIBER_FORM_COL, SCALE_SHEET_COL)

        assert len(row) == len(headers)


# ── run() 통합 테스트 ─────────────────────────────────────────────────────────────

class TestRun:

    def test_new_record_appended_to_output(self) -> None:
        """신규 폼 응답 → 출력 시트에 행 1개 추가."""
        form_ws   = _make_form_ws([_form_record()])
        output_ws = _make_output_ws()

        result = run(form_ws=form_ws, output_ws=output_ws)

        assert result["newly_added"] == 1
        assert result["skipped_existing"] == 0
        assert result["errors"] == 0
        assert len(output_ws.appended) == 1

    def test_multiple_new_records(self) -> None:
        """신규 응답 3개 → 3행 추가."""
        records = [
            _form_record(**{"채널명": f"채널{i}"})
            for i in range(3)
        ]
        form_ws   = _make_form_ws(records)
        output_ws = _make_output_ws()

        result = run(form_ws=form_ws, output_ws=output_ws)

        assert result["newly_added"] == 3
        assert len(output_ws.appended) == 3

    def test_duplicate_channel_skipped(self) -> None:
        """기존에 있는 채널명 → 스킵, 시트 미추가."""
        form_ws   = _make_form_ws([_form_record(**{"채널명": "이미있는채널"})])
        output_ws = _make_output_ws(existing_channel_names=["이미있는채널"])

        result = run(form_ws=form_ws, output_ws=output_ws)

        assert result["newly_added"] == 0
        assert result["skipped_existing"] == 1
        assert len(output_ws.appended) == 0

    def test_dry_run_does_not_write_sheet(self) -> None:
        """dry_run=True → 시트에 쓰지 않고 newly_added만 반환."""
        form_ws   = _make_form_ws([_form_record(), _form_record(**{"채널명": "채널2"})])
        output_ws = _make_output_ws()

        result = run(form_ws=form_ws, output_ws=output_ws, dry_run=True)

        assert result["newly_added"] == 2
        assert len(output_ws.appended) == 0  # 실제로 쓰지 않음

    def test_empty_form_returns_zero_counts(self) -> None:
        """빈 폼 응답 → 모든 카운트 0."""
        form_ws   = _make_form_ws([])
        output_ws = _make_output_ws()

        result = run(form_ws=form_ws, output_ws=output_ws)

        assert result["newly_added"] == 0
        assert result["skipped_existing"] == 0
        assert result["total_responses"] == 0

    def test_empty_channel_name_skipped_silently(self) -> None:
        """채널명이 빈 행 → 카운트 없이 무시."""
        form_ws   = _make_form_ws([_form_record(**{"채널명": ""})])
        output_ws = _make_output_ws()

        result = run(form_ws=form_ws, output_ws=output_ws)

        assert result["newly_added"] == 0
        assert result["skipped_existing"] == 0

    def test_output_sheet_no_headers_auto_generated(self) -> None:
        """출력 시트 헤더 없음 → 헤더 자동 생성 후 데이터 추가."""
        form_ws   = _make_form_ws([_form_record()])
        output_ws = FakeWorksheet(headers=[], rows=[])  # 헤더 없음

        result = run(form_ws=form_ws, output_ws=output_ws)

        # 헤더 자동 생성 후 데이터 행 추가 (총 2개 append: 헤더 + 데이터)
        assert result["newly_added"] == 1
        assert len(output_ws.appended) == 2  # 헤더 + 데이터

    def test_scale_column_value_in_written_row(self) -> None:
        """작성된 행에 규모 컬럼 값이 올바르게 계산됨."""
        form_ws   = _make_form_ws([_form_record(**{"구독자 수": "1500000"})])
        output_ws = _make_output_ws()

        run(form_ws=form_ws, output_ws=output_ws)

        assert len(output_ws.appended) == 1
        written_row = output_ws.appended[0]
        headers     = _output_headers()
        scale_idx   = headers.index(SCALE_SHEET_COL)
        assert written_row[scale_idx] == "메가"

    def test_result_total_responses_matches_form(self) -> None:
        """total_responses 는 폼 전체 행 수와 일치."""
        records = [_form_record(**{"채널명": f"채널{i}"}) for i in range(5)]
        form_ws   = _make_form_ws(records)
        output_ws = _make_output_ws()

        result = run(form_ws=form_ws, output_ws=output_ws)

        assert result["total_responses"] == 5

    def test_mixed_new_and_duplicate(self) -> None:
        """신규 2개 + 중복 1개 혼합."""
        records = [
            _form_record(**{"채널명": "신규채널A"}),
            _form_record(**{"채널명": "기존채널"}),
            _form_record(**{"채널명": "신규채널B"}),
        ]
        form_ws   = _make_form_ws(records)
        output_ws = _make_output_ws(existing_channel_names=["기존채널"])

        result = run(form_ws=form_ws, output_ws=output_ws)

        assert result["newly_added"] == 2
        assert result["skipped_existing"] == 1
        assert len(output_ws.appended) == 2
