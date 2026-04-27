# -*- coding: utf-8 -*-
"""D-3. 카카오 오리지널 크리에이터 월초 점검 핸들러.

현행:
  카카오 오리지널 크리에이터 신규 입점 시 담당자가 수동으로
  구글폼 응답을 취합 → 시트 입력 → 권한 요청 → 안내 발송의
  전 과정을 수동 처리.

자동화 범위:
  STEP 1 (구현):  구글폼 응답 → '최종 리스트' 시트 자동 입력 + 규모 카테고리 계산
  STEP 2 (보류):  카카오 숏폼 스튜디오 권한 부여 요청 메시지 발송 (브라우저 제어)
  STEP 3 (보류):  온보딩 완료 안내 + 카카오톡 단톡방 초대 (브라우저 제어)
  STEP 4 (보류):  레이블리 어드민 채널 등록 [미결: 채널 관리 키값 필요]
  STEP 5 (보류):  월간 정기 정산 프로세스 [미결: 정산팀 확인 필요]

구글 시트:
  입력폼 응답 시트 ID : KAKAO_FORM_SHEET_ID  (구글폼이 연결된 스프레드시트)
  출력 시트 ID        : KAKAO_OUTPUT_SHEET_ID  (1tqhZEoUnTITURcJTGhPAcPPjzckVstdsETcUMY7I7Ys)
  출력 탭             : 최종 리스트

규모 카테고리:
  메가    : 구독자 100만명 이상
  매크로  : 10만 ~ 100만명
  마이크로: 1만 ~ 10만명
  나노    : 1만명 미만
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.logger import CoreLogger

log = CoreLogger(__name__)

TASK_ID   = "D-3"
TASK_NAME = "카카오 오리지널 크리에이터 월초 점검"

# ── 규모 카테고리 ─────────────────────────────────────────────────────────────

def classify_scale(subscribers: int) -> str:
    """구독자 수 → 규모 카테고리 변환."""
    if subscribers >= 1_000_000:
        return "메가"
    if subscribers >= 100_000:
        return "매크로"
    if subscribers >= 10_000:
        return "마이크로"
    return "나노"


# ── 폼 응답 → 시트 행 매핑 설정 ───────────────────────────────────────────────
#
# 구글폼 응답 헤더명(form_col)  →  최종 리스트 헤더명(sheet_col)
# Sheets API 활성화 후 실제 헤더 확인하여 수정할 것.
#
# 규모(SCALE_COL)는 구독자 수에서 자동 계산하므로 매핑에 포함하지 않는다.

SUBSCRIBER_FORM_COL = "구독자 수"    # 폼의 구독자 수 컬럼명 (수정 가능)
SCALE_SHEET_COL     = "규모"          # 최종 리스트의 규모 컬럼명

# 폼 컬럼 → 시트 컬럼 직접 매핑 (필요 시 추가/수정)
COLUMN_MAP: dict[str, str] = {
    "타임스탬프":         "신청일시",
    "채널명":             "채널명",
    "유튜브 채널 URL":    "유튜브 채널 URL",
    "카카오 숏폼 채널명": "카카오 숏폼 채널명",
    "구독자 수":          "구독자 수",
    "장르":               "장르",
    "담당자명":           "담당자명",
    "담당자 이메일":      "담당자 이메일",
    "담당자 연락처":      "담당자 연락처",
}


# ── 결과 모델 ─────────────────────────────────────────────────────────────────

@dataclass
class OnboardingResult:
    total_responses:  int
    newly_added:      int
    skipped_existing: int
    errors:           int
    rows_written:     list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_responses":  self.total_responses,
            "newly_added":      self.newly_added,
            "skipped_existing": self.skipped_existing,
            "errors":           self.errors,
        }


# ── 공개 진입점 ────────────────────────────────────────────────────────────────

def run(
    form_ws: Any,      # gspread.Worksheet  — 구글폼 응답 탭
    output_ws: Any,    # gspread.Worksheet  — '최종 리스트' 탭
    column_map: Optional[dict[str, str]] = None,
    subscriber_col: Optional[str] = None,
    scale_col: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """D-3 Step 1: 구글폼 응답 → '최종 리스트' 시트 자동 입력.

    Args:
        form_ws:        구글폼 응답이 연결된 gspread Worksheet
        output_ws:      출력 대상 '최종 리스트' gspread Worksheet
        column_map:     폼 컬럼 → 시트 컬럼 매핑 (None이면 COLUMN_MAP 사용)
        subscriber_col: 구독자 수 컬럼명 (None이면 SUBSCRIBER_FORM_COL 사용)
        scale_col:      규모 컬럼명 (None이면 SCALE_SHEET_COL 사용)
        dry_run:        True이면 시트에 실제로 쓰지 않고 결과만 반환

    Returns:
        OnboardingResult.to_dict()
    """
    col_map      = column_map   or COLUMN_MAP
    sub_col      = subscriber_col or SUBSCRIBER_FORM_COL
    sc_col       = scale_col    or SCALE_SHEET_COL

    log.info("[D-3] Step 1 시작: 폼 응답 → 최종 리스트 동기화")

    # 1. 폼 응답 읽기
    form_records = form_ws.get_all_records()
    log.info("[D-3] 폼 응답 %d건 로드", len(form_records))

    # 2. 시트 기존 데이터 로드 (중복 방지용)
    existing_records = output_ws.get_all_records()
    existing_keys    = _build_existing_keys(existing_records)
    output_headers   = output_ws.row_values(1)

    if not output_headers:
        log.warning("[D-3] 최종 리스트 헤더가 비어 있음 — 헤더 자동 생성")
        output_headers = _generate_headers(col_map, sc_col)
        if not dry_run:
            output_ws.append_row(output_headers)

    result = OnboardingResult(total_responses=len(form_records), newly_added=0,
                               skipped_existing=0, errors=0)

    for record in form_records:
        channel_name = str(record.get("채널명", "")).strip()
        if not channel_name:
            continue

        # 중복 확인 (채널명 기준)
        if channel_name in existing_keys:
            log.debug("[D-3] 중복 스킵: %s", channel_name)
            result.skipped_existing += 1
            continue

        try:
            row = _build_output_row(record, output_headers, col_map, sub_col, sc_col)
            result.rows_written.append(dict(zip(output_headers, row)))

            if not dry_run:
                output_ws.append_row(row, value_input_option="USER_ENTERED")
                log.info("[D-3] 추가: %s (규모: %s)", channel_name,
                         record.get("_scale", ""))
            result.newly_added += 1

        except Exception as e:
            log.error("[D-3] 행 처리 실패 (%s): %s", channel_name, e)
            result.errors += 1

    log.info("[D-3] Step 1 완료: 신규 %d건 / 중복 스킵 %d건 / 오류 %d건",
             result.newly_added, result.skipped_existing, result.errors)
    return result.to_dict()


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _build_existing_keys(records: list[dict]) -> set[str]:
    """기존 시트 채널명 집합 반환 (중복 방지용)."""
    return {str(r.get("채널명", "")).strip() for r in records if r.get("채널명")}


def _build_output_row(
    record: dict,
    output_headers: list[str],
    col_map: dict[str, str],
    sub_col: str,
    sc_col: str,
) -> list[str]:
    """폼 응답 레코드 1건 → 시트 행 리스트 변환."""
    # 역매핑: 시트 헤더 → 폼 값
    sheet_to_form = {v: k for k, v in col_map.items()}

    # 규모 계산
    try:
        raw = str(record.get(sub_col, "0")).replace(",", "").replace("명", "").strip()
        subscribers = int(raw) if raw.isdigit() else 0
    except (ValueError, TypeError):
        subscribers = 0
    scale = classify_scale(subscribers)
    record["_scale"] = scale  # 로그용 임시 저장

    row = []
    for header in output_headers:
        if header == sc_col:
            row.append(scale)
        elif header in sheet_to_form:
            form_key = sheet_to_form[header]
            row.append(str(record.get(form_key, "")))
        else:
            row.append("")
    return row


def _generate_headers(col_map: dict[str, str], scale_col: str) -> list[str]:
    """출력 시트 헤더 자동 생성 (시트가 비어있을 때)."""
    headers = list(col_map.values())
    if scale_col not in headers:
        # 구독자 수 다음에 규모 삽입
        try:
            idx = headers.index("구독자 수") + 1
            headers.insert(idx, scale_col)
        except ValueError:
            headers.append(scale_col)
    return headers
