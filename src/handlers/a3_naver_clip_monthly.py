"""A-3 monthly Naver Clip onboarding workflow.

Modes:
  - confirm: notify Slack with this month's homepage applicants
  - send: generate an Excel report for the previous month and email it
"""
from __future__ import annotations

import io
from datetime import datetime
from enum import Enum
from typing import Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
import pytz

from ..core.interfaces.notifier import INotifier
from ..core.interfaces.repository import ILogRepository, INaverClipRepository
from ..core.logger import CoreLogger
from ..models import NaverClipApplicant

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)

TASK_ID = "A-3"
TASK_NAME = "Naver Clip monthly onboarding intake"


class RunMode(str, Enum):
    CONFIRM = "confirm"
    SEND = "send"


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
    year, month = _resolve_target_month(target_year, target_month, mode)
    applicants = form_repo.get_applicants_by_month(year, month)

    if mode == RunMode.CONFIRM:
        return _handle_confirm(applicants, year, month, slack_notifier, slack_channel)
    return _handle_send(applicants, year, month, email_notifier, manager_email)


def _handle_confirm(
    applicants: list[NaverClipApplicant],
    year: int,
    month: int,
    slack_notifier: INotifier,
    slack_channel: str,
) -> dict:
    if not applicants:
        message = (
            f":information_source: *[A-3]* {year}-{month:02d} "
            "homepage applicants were not found."
        )
        slack_notifier.send(slack_channel, message)
        return {"mode": "confirm", "applicant_count": 0, "action": "no_applicants_notified"}

    lines = [
        f"*[A-3] {year}-{month:02d} Naver Clip applicant list* (total {len(applicants)})",
        "",
    ]
    for index, applicant in enumerate(applicants, start=1):
        lines.append(
            f"{index}. {applicant.name} | {applicant.representative_channel_name} | "
            f"{applicant.representative_channel_platform.value} | "
            f"{applicant.naver_clip_profile_name}"
        )

    slack_notifier.send(slack_channel, "\n".join(lines))
    return {"mode": "confirm", "applicant_count": len(applicants), "action": "slack_sent"}


def _handle_send(
    applicants: list[NaverClipApplicant],
    year: int,
    month: int,
    email_notifier: INotifier,
    manager_email: str,
) -> dict:
    if not applicants:
        return {"mode": "send", "applicant_count": 0, "action": "skipped_no_applicants"}

    excel_bytes = _build_excel(applicants, year, month)
    filename = f"naver_clip_onboarding_{year}{month:02d}.xlsx"
    subject = f"[Rhoonart] {year}-{month:02d} Naver Clip onboarding applicants"
    body = _build_email_body(len(applicants), year, month)

    success = email_notifier.send(
        recipient=manager_email,
        message=body,
        subject=subject,
        html=True,
        attachments=[(filename, excel_bytes)],
    )
    if not success:
        raise RuntimeError(f"failed to send onboarding email to {manager_email}")
    return {
        "mode": "send",
        "applicant_count": len(applicants),
        "action": "email_sent",
        "filename": filename,
    }


def _build_excel(applicants: list[NaverClipApplicant], year: int, month: int) -> bytes:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = f"{year}-{month:02d}"

    headers = [
        "No.",
        "신청일시",
        "이름",
        "전화번호",
        "네이버 ID",
        "네이버 클립 프로필명",
        "네이버 클립 프로필 ID",
        "대표 채널명",
        "대표 채널의 활동 플랫폼",
        "채널 URL",
    ]
    _write_header_row(worksheet, headers)

    for index, applicant in enumerate(applicants, start=1):
        worksheet.append(
            [
                index,
                applicant.submitted_at.strftime("%Y-%m-%d %H:%M"),
                applicant.name,
                applicant.phone_number,
                applicant.naver_id,
                applicant.naver_clip_profile_name,
                applicant.naver_clip_profile_id,
                applicant.representative_channel_name,
                applicant.representative_channel_platform.value,
                applicant.channel_url,
            ]
        )
        if applicant.channel_url:
            worksheet.cell(row=index + 1, column=10).hyperlink = applicant.channel_url
            worksheet.cell(row=index + 1, column=10).font = Font(
                color="0563C1",
                underline="single",
            )

    widths = [6, 18, 14, 18, 18, 24, 22, 22, 26, 40]
    for column_index, width in enumerate(widths, start=1):
        worksheet.column_dimensions[openpyxl.utils.get_column_letter(column_index)].width = width

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _write_header_row(worksheet, headers: list[str]) -> None:
    fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    font = Font(name="Malgun Gothic", bold=True, color="FFFFFF", size=10)
    alignment = Alignment(horizontal="center", vertical="center")
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    worksheet.append(headers)
    for column_index, _ in enumerate(headers, start=1):
        cell = worksheet.cell(row=1, column=column_index)
        cell.fill = fill
        cell.font = font
        cell.alignment = alignment
        cell.border = border
    worksheet.row_dimensions[1].height = 22


def _build_email_body(count: int, year: int, month: int) -> str:
    return (
        "<html><body style='font-family:sans-serif;color:#333;'>"
        "<p>안녕하세요.</p>"
        f"<p>{year}-{month:02d} Naver Clip 온보딩 신청자 명단을 전달드립니다.</p>"
        f"<p>신청자 수: <strong>{count}명</strong></p>"
        "<p>첨부 파일을 확인해 주세요.</p>"
        "<p style='font-size:12px;color:#888;'>본 메일은 자동 발송되었습니다.</p>"
        "</body></html>"
    )


def _resolve_target_month(
    year: Optional[int],
    month: Optional[int],
    mode: RunMode,
) -> tuple[int, int]:
    if year and month:
        return year, month

    now = datetime.now(KST)
    if mode == RunMode.SEND:
        if now.month == 1:
            return now.year - 1, 12
        return now.year, now.month - 1
    return now.year, now.month
