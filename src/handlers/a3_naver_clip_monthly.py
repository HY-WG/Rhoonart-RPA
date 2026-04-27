"""A-3. 네이버 클립 월별 채널 인입 자동화 핸들러.

두 가지 모드:
  confirm (매월 말일): 전월 신청자 취합 → Slack 담당자 확인 요청
  send    (매월 1일):  전월 신청자 취합 → 네이버 제출용 엑셀 생성 → 담당자 메일 발송

네이버 제출 엑셀 포맷:
  구글 스프레드시트 템플릿(1sd1XKBQPnueYfCmFWZeejc2ltaonXEcWGY63aE22efQ, gid=1934175920)
  의 헤더 구조를 그대로 따른다.
"""
import io
from calendar import monthrange
from datetime import datetime
from enum import Enum
from typing import Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
import pytz

from ..core.interfaces.repository import INaverClipRepository, ILogRepository
from ..core.interfaces.notifier import INotifier
from ..core.logger import CoreLogger

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)

TASK_ID   = "A-3"
TASK_NAME = "네이버 클립 월별 채널 인입 자동화"


class RunMode(str, Enum):
    CONFIRM = "confirm"  # 말일: Slack 확인 요청
    SEND    = "send"     # 1일: 엑셀 생성 + 메일 발송


def run(
    form_repo: INaverClipRepository,
    log_repo: ILogRepository,
    slack_notifier: INotifier,
    email_notifier: INotifier,
    mode: RunMode,
    manager_email: str,
    target_year: Optional[int] = None,
    target_month: Optional[int] = None,
    slack_channel: str = "",
) -> dict:
    """A-3 실행.

    Args:
        mode: RunMode.CONFIRM (말일) 또는 RunMode.SEND (1일)
        target_year/month: None이면 실행 시점 기준으로 자동 계산
    Returns:
        {"mode": str, "applicant_count": int, "action": str}
    """
    year, month = _resolve_target_month(target_year, target_month, mode)
    log.info("[A-3] 실행 모드: %s, 대상: %d년 %d월", mode.value, year, month)

    applicants = form_repo.get_applicants_by_month(year, month)
    log.info("[A-3] 신청자 %d명 조회됨", len(applicants))

    if mode == RunMode.CONFIRM:
        return _handle_confirm(applicants, year, month, slack_notifier, slack_channel)
    else:
        return _handle_send(applicants, year, month, email_notifier, slack_notifier, manager_email)


# ── CONFIRM 모드 ──────────────────────────────────────

def _handle_confirm(
    applicants: list[dict],
    year: int,
    month: int,
    slack_notifier: INotifier,
    slack_channel: str,
) -> dict:
    """말일: 신청자 목록을 Slack에 전송하여 담당자 확인 요청."""
    if not applicants:
        msg = f":information_source: *[A-3]* {year}년 {month}월 네이버 클립 신청자가 없습니다."
        slack_notifier.send(slack_channel, msg)
        return {"mode": "confirm", "applicant_count": 0, "action": "no_applicants_notified"}

    lines = [f"*[A-3] {year}년 {month}월 네이버 클립 채널 인입 신청자 목록* (총 {len(applicants)}명)\n"]
    for i, a in enumerate(applicants, 1):
        lines.append(
            f"{i}. *{a['channel_name']}* | {a['genre']} | {a['manager_name']} ({a['manager_email']})"
        )
    lines.append(
        f"\n이상 없으면 {year}년 {month + 1 if month < 12 else 1}월 1일에 네이버 제출용 엑셀이 자동 발송됩니다. :white_check_mark:"
    )

    slack_notifier.send(slack_channel, "\n".join(lines))
    log.info("[A-3] Slack 확인 요청 발송 완료 (%d명)", len(applicants))
    return {"mode": "confirm", "applicant_count": len(applicants), "action": "slack_sent"}


# ── SEND 모드 ─────────────────────────────────────────

def _handle_send(
    applicants: list[dict],
    year: int,
    month: int,
    email_notifier: INotifier,
    slack_notifier: INotifier,
    manager_email: str,
) -> dict:
    """1일: 엑셀 생성 후 담당자에게 메일 발송."""
    if not applicants:
        log.warning("[A-3] %d년 %d월 신청자 없음 — 메일 발송 건너뜀", year, month)
        return {"mode": "send", "applicant_count": 0, "action": "skipped_no_applicants"}

    excel_bytes = _build_excel(applicants, year, month)
    filename = f"네이버클립_채널인입_{year}{month:02d}.xlsx"
    subject  = f"[루나트] {year}년 {month}월 네이버 클립 채널 인입 신청자 명단"
    body     = _build_email_body(len(applicants), year, month)

    success = email_notifier.send(
        recipient=manager_email,
        message=body,
        subject=subject,
        html=True,
        attachments=[(filename, excel_bytes)],
    )

    if success:
        log.info("[A-3] 메일 발송 완료 → %s (%d명)", manager_email, len(applicants))
        return {"mode": "send", "applicant_count": len(applicants), "action": "email_sent", "filename": filename}
    else:
        raise RuntimeError(f"메일 발송 실패 → {manager_email}")


# ── 엑셀 생성 ─────────────────────────────────────────

def _build_excel(applicants: list[dict], year: int, month: int) -> bytes:
    """네이버 클립 제출용 엑셀 생성.

    헤더 구조:
        No. | 채널명 | 채널 URL | 장르 | 담당자명 | 담당자 이메일 | 신청일

    실제 네이버 제출 양식(gid=1934175920)과 다를 경우 헤더 목록 수정 필요.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{year}년 {month}월"

    # 헤더
    headers = ["No.", "채널명", "채널 URL", "장르", "담당자명", "담당자 이메일", "신청일"]
    _write_header_row(ws, headers)

    # 데이터
    for i, a in enumerate(applicants, 1):
        ws.append([
            i,
            a.get("channel_name", ""),
            a.get("channel_url", ""),
            a.get("genre", ""),
            a.get("manager_name", ""),
            a.get("manager_email", ""),
            a.get("timestamp", "")[:10],  # YYYY-MM-DD
        ])
        # URL 열 링크 처리
        if a.get("channel_url"):
            ws.cell(row=i + 1, column=3).hyperlink = a["channel_url"]
            ws.cell(row=i + 1, column=3).font = Font(color="0563C1", underline="single")

    # 열 너비 자동 조정
    col_widths = [6, 25, 45, 12, 15, 30, 14]
    for col_idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_header_row(ws, headers: list[str]) -> None:
    header_fill  = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font  = Font(name="맑은 고딕", bold=True, color="FFFFFF", size=10)
    header_align = Alignment(horizontal="center", vertical="center")
    thin_border  = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"),  bottom=Side(style="thin"),
    )
    ws.append(headers)
    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill   = header_fill
        cell.font   = header_font
        cell.alignment = header_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 22


def _build_email_body(count: int, year: int, month: int) -> str:
    return f"""
<html><body style="font-family:sans-serif;color:#333;">
<p>안녕하세요.</p>
<p>루나트입니다.<br>
{year}년 {month}월 <strong>네이버 클립 채널 인입 신청자 명단</strong>을 첨부파일로 전달드립니다.</p>
<ul>
  <li>신청자 수: <strong>{count}명</strong></li>
  <li>대상 월: <strong>{year}년 {month}월</strong></li>
</ul>
<p>첨부된 엑셀 파일을 네이버 담당자에게 제출해 주세요.</p>
<p style="font-size:12px;color:#888;">본 메일은 자동 발송되었습니다.</p>
</body></html>
""".strip()


# ── 헬퍼 ─────────────────────────────────────────────

def _resolve_target_month(
    year: Optional[int],
    month: Optional[int],
    mode: RunMode,
) -> tuple[int, int]:
    """대상 연월 계산.

    - CONFIRM (말일 실행): 현재 월 (이번 달 신청자 확인)
    - SEND    (1일 실행):  전월 (지난 달 신청자 제출)
    """
    if year and month:
        return year, month

    now = datetime.now(KST)
    if mode == RunMode.SEND:
        # 1일 실행 → 전월 데이터
        if now.month == 1:
            return now.year - 1, 12
        return now.year, now.month - 1
    # CONFIRM → 현재 월
    return now.year, now.month
