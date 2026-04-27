# -*- coding: utf-8 -*-
"""C-4. 수익 100% 쿠폰 신청 처리 알림 핸들러.

플로우 A — Slack 메시지 수신 시 (keyword trigger):
  1. 메시지에 쿠폰 키워드("쿠폰", "100%") 포함 여부 확인
  2. Google Sheets 처리 목록에 신청 기록 (크리에이터명, 요청 일시, 상태=대기)
  3. 담당자에게 Slack DM 발송 (레이블리 어드민 수익 설정 직링크 포함)

플로우 B — Sheets 완료 업데이트 감지 시 (GAS onEdit webhook):
  4. 처리 완료 행 식별 → 크리에이터에게 카카오 알림톡 발송
     (stub: 카카오 알림톡 API 계정·템플릿 미확인 → API 확인 후 구현)

트리거:
  A: Slack Event API (message.channels) → Lambda keyword filter
  B: Google Apps Script onEdit → HTTPS POST → Lambda
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import pytz

from ..core.interfaces.notifier import INotifier
from ..core.logger import CoreLogger

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)

TASK_ID   = "C-4"
TASK_NAME = "수익 100% 쿠폰 신청 처리 알림"

# 쿠폰 신청 키워드 필터
COUPON_KEYWORDS: list[str] = ["쿠폰", "100%"]

# 레이블리 어드민 수익 설정 URL (환경변수 LABELIVE_ADMIN_URL로 오버라이드 가능)
_LABELIVE_ADMIN_BASE = "https://labelive.io"


# ── 결과 모델 ─────────────────────────────────────────────────────────────────

@dataclass
class CouponRequestResult:
    creator_name: str
    requested_at: datetime
    sheet_appended: bool
    slack_dm_sent: bool
    kakao_sent: bool  # 플로우 B 완료 알림톡 (항상 False — stub)

    def to_dict(self) -> dict:
        return {
            "creator_name":  self.creator_name,
            "requested_at":  self.requested_at.isoformat(),
            "sheet_appended": self.sheet_appended,
            "slack_dm_sent": self.slack_dm_sent,
            "kakao_sent":    self.kakao_sent,
        }


# ── 공개 진입점 ────────────────────────────────────────────────────────────────

def is_coupon_request(text: str) -> bool:
    """메시지에 쿠폰 관련 키워드가 포함되어 있는지 확인."""
    return any(kw in text for kw in COUPON_KEYWORDS)


def run_on_slack_message(
    creator_name: str,
    slack_message_text: str,
    sheets_client: Any,           # gspread.Client
    coupon_sheet_id: str,
    coupon_sheet_tab: str,
    slack_notifier: Any,          # SlackNotifier
    admin_slack_user_id: str,     # 담당자 Slack user ID (예: "U01ABCDE")
    labelive_admin_url: str = "",
    requested_at: Optional[datetime] = None,
) -> dict:
    """Slack 쿠폰 신청 메시지 수신 시 처리 (플로우 A).

    Args:
        creator_name:          Slack 메시지를 보낸 크리에이터명
        slack_message_text:    Slack 메시지 원문
        sheets_client:         인증된 gspread.Client
        coupon_sheet_id:       쿠폰 처리 목록 Google Sheets ID
        coupon_sheet_tab:      쿠폰 처리 탭명 (예: "쿠폰신청")
        slack_notifier:        Slack 알림 클라이언트
        admin_slack_user_id:   담당자 Slack User ID (DM 대상)
        labelive_admin_url:    레이블리 어드민 URL (빈값이면 기본값 사용)
        requested_at:          신청 시각 (기본: 현재)

    Returns:
        {"skipped": True} 또는 CouponRequestResult.to_dict()
    """
    if not is_coupon_request(slack_message_text):
        log.info("[C-4] 쿠폰 키워드 없음 — 처리 건너뜀")
        return {"skipped": True, "reason": "no_coupon_keyword"}

    requested_at = requested_at or datetime.now(KST)
    log.info("[C-4] 쿠폰 신청 감지: 크리에이터=%s, 시각=%s", creator_name, requested_at)

    # 1. Google Sheets 기록
    sheet_appended = _append_to_coupon_sheet(
        sheets_client, coupon_sheet_id, coupon_sheet_tab,
        creator_name, requested_at,
    )

    # 2. 담당자 Slack DM
    admin_url = labelive_admin_url or _LABELIVE_ADMIN_BASE
    slack_dm_sent = _send_admin_slack_dm(
        slack_notifier, admin_slack_user_id,
        creator_name, requested_at, admin_url,
    )

    result = CouponRequestResult(
        creator_name=creator_name,
        requested_at=requested_at,
        sheet_appended=sheet_appended,
        slack_dm_sent=slack_dm_sent,
        kakao_sent=False,
    )
    log.info("[C-4] 플로우 A 완료: %s", result.to_dict())
    return result.to_dict()


def run_on_completion(
    creator_name: str,
    creator_phone: str,
    kakao_notifier: Any = None,   # KakaoNotifier (stub — API 키 미확인)
    completed_at: Optional[datetime] = None,
) -> dict:
    """Sheets 처리 완료 업데이트 감지 시 카카오 알림톡 발송 (플로우 B).

    GAS onEdit → HTTPS POST → Lambda 에 의해 호출.

    Args:
        creator_name:    완료 처리된 크리에이터명
        creator_phone:   카카오 알림톡 수신 전화번호
        kakao_notifier:  카카오 알림톡 클라이언트 (None이면 stub)
        completed_at:    처리 완료 시각 (기본: 현재)

    Returns:
        {"creator_name", "completed_at", "kakao_sent"}
    """
    completed_at = completed_at or datetime.now(KST)
    log.info("[C-4] 처리 완료 감지: 크리에이터=%s", creator_name)

    kakao_sent = _send_kakao_completion(kakao_notifier, creator_name, creator_phone, completed_at)

    result = {
        "creator_name": creator_name,
        "completed_at": completed_at.isoformat(),
        "kakao_sent":   kakao_sent,
    }
    log.info("[C-4] 플로우 B 완료: %s", result)
    return result


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _append_to_coupon_sheet(
    sheets_client: Any,
    sheet_id: str,
    tab_name: str,
    creator_name: str,
    requested_at: datetime,
) -> bool:
    """Google Sheets 쿠폰 처리 목록에 신청 행을 추가한다.

    컬럼 구조 (가정):
        A: 크리에이터명 | B: 요청 일시 | C: 처리 상태
    """
    try:
        sh = sheets_client.open_by_key(sheet_id)
        ws = sh.worksheet(tab_name)
        ws.append_row([
            creator_name,
            requested_at.strftime("%Y-%m-%d %H:%M:%S"),
            "대기",
        ])
        log.info("[C-4] Sheets 기록 완료: %s → %s (탭: %s)", creator_name, sheet_id, tab_name)
        return True
    except Exception as e:
        log.error("[C-4] Sheets 기록 실패: %s", e)
        return False


def _send_admin_slack_dm(
    slack_notifier: Any,
    admin_user_id: str,
    creator_name: str,
    requested_at: datetime,
    admin_url: str,
) -> bool:
    """담당자에게 Slack DM으로 쿠폰 신청 알림을 발송한다."""
    date_str = requested_at.strftime("%Y-%m-%d %H:%M")
    message = (
        f":ticket: *수익 100% 쿠폰 신청 접수*\n"
        f"• 크리에이터: *{creator_name}*\n"
        f"• 요청 일시: {date_str}\n"
        f"• 처리: <{admin_url}|레이블리 어드민 수익 설정 바로가기>\n"
        f"\n처리 완료 후 시트 상태를 *완료*로 업데이트해주세요."
    )
    try:
        return slack_notifier.send(recipient=admin_user_id, message=message)
    except Exception as e:
        log.error("[C-4] Slack DM 발송 실패: %s", e)
        return False


def _send_kakao_completion(
    kakao_notifier: Any,
    creator_name: str,
    creator_phone: str,
    completed_at: datetime,
) -> bool:
    """크리에이터에게 카카오 알림톡으로 쿠폰 적용 완료를 알린다.

    ⏸ stub: 카카오 알림톡 API 계정 및 템플릿 ID 미확인.
    API 키 확인 후 kakao_notifier.send() 실 구현으로 교체.
    """
    if kakao_notifier is None:
        log.info("[C-4] KakaoNotifier 미설정 — 카카오 알림톡 건너뜀 (stub)")
        return False

    try:
        return kakao_notifier.send(
            recipient=creator_phone,
            message=f"[루나트] {creator_name}님의 수익 100% 쿠폰이 적용되었습니다.",
            template_code="COUPON_APPLIED",  # TODO: 실제 알림톡 템플릿 코드로 교체
        )
    except Exception as e:
        log.error("[C-4] 카카오 알림톡 발송 실패 (stub): %s", e)
        return False
