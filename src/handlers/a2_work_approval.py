# -*- coding: utf-8 -*-
"""A-2 작품 사용요청 승인 자동화."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import pytz
import requests as http_requests

from ..core.interfaces.notifier import INotifier
from ..core.logger import CoreLogger

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)

TASK_ID = "A-2"
TASK_NAME = "작품 사용요청 승인 자동화"

_SLACK_CHANNEL_RE = re.compile(r'채널:\s*["\u201c\u2018]([^"\u201d\u2019]+)["\u201d\u2019]')


@dataclass
class ApprovalResult:
    channel_name: str
    work_title: str
    applicant_email: str
    drive_file_id: str
    drive_file_url: str
    email_sent: bool
    slack_replied: bool
    admin_api_updated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "work_title": self.work_title,
            "applicant_email": self.applicant_email,
            "drive_file_id": self.drive_file_id,
            "drive_file_url": self.drive_file_url,
            "email_sent": self.email_sent,
            "slack_replied": self.slack_replied,
            "admin_api_updated": self.admin_api_updated,
        }


def parse_slack_message(text: str) -> tuple[str, str]:
    """Slack 요청 메시지에서 채널명과 작품명을 추출한다.

    기대 형식:
        채널: "정호영" 님의 신규 영상 사용 요청이 있습니다.
        21세기 대군부인
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError(f"Slack 메시지 형식 오류: 최소 2줄이 필요합니다. text={text!r}")

    match = _SLACK_CHANNEL_RE.search(lines[0])
    if not match:
        raise ValueError(f"채널명을 추출할 수 없습니다. first_line={lines[0]!r}")

    channel_name = match.group(1).strip()
    work_title = lines[1].strip()

    if not channel_name:
        raise ValueError(f"채널명이 비어 있습니다. first_line={lines[0]!r}")
    if not work_title:
        raise ValueError(f"작품명이 비어 있습니다. second_line={lines[1]!r}")

    log.info("[A-2] 파싱 완료: channel=%r work=%r", channel_name, work_title)
    return channel_name, work_title


def parse_manual_request(channel_name: str, work_title: str) -> tuple[str, str]:
    """홈페이지/수동 endpoint용 요청값을 검증한다."""
    normalized_channel = channel_name.strip()
    normalized_work = work_title.strip()
    if not normalized_channel:
        raise ValueError("channel_name is required")
    if not normalized_work:
        raise ValueError("work_title is required")
    return normalized_channel, normalized_work


def run(
    slack_channel_id: str,
    slack_message_ts: str,
    slack_message_text: str,
    sheets_client: Any,
    drive_service: Any,
    email_notifier: INotifier,
    slack_notifier: Any,
    creator_sheet_id: str,
    drive_folder_id: str,
    sender_email: str,
    admin_api_base_url: str = "",
    requested_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """A-2 작품 사용요청 승인 자동화를 실행한다."""
    requested_at = requested_at or datetime.now(KST)

    channel_name, work_title = parse_slack_message(slack_message_text)
    applicant_email = _lookup_creator_email(sheets_client, creator_sheet_id, channel_name)
    log.info("[A-2] 신청자 이메일 조회 완료: %s -> %s", channel_name, applicant_email)

    file_id, file_name, file_url = _search_drive_file(drive_service, drive_folder_id, work_title)
    log.info("[A-2] Drive 파일 발견: %s (id=%s)", file_name, file_id)

    _grant_viewer_permission(drive_service, file_id, applicant_email)
    log.info("[A-2] Drive viewer 권한 부여 완료: file=%s email=%s", file_id, applicant_email)

    email_body = _build_approval_email(work_title, file_url, requested_at)
    email_subject = f'[르호안아트] "{work_title}" 사용 승인 안내'
    email_sent = email_notifier.send(
        recipient=applicant_email,
        message=email_body,
        subject=email_subject,
        html=True,
        sender=sender_email,
    )
    if email_sent:
        log.info("[A-2] 승인 메일 발송 완료: %s", applicant_email)
    else:
        log.error("[A-2] 승인 메일 발송 실패: %s", applicant_email)

    slack_replied = _reply_to_slack_thread(
        slack_notifier=slack_notifier,
        channel_id=slack_channel_id,
        thread_ts=slack_message_ts,
        channel_name=channel_name,
        work_title=work_title,
        applicant_email=applicant_email,
    )
    admin_updated = _update_admin_api(admin_api_base_url, slack_message_ts)

    result = ApprovalResult(
        channel_name=channel_name,
        work_title=work_title,
        applicant_email=applicant_email,
        drive_file_id=file_id,
        drive_file_url=file_url,
        email_sent=email_sent,
        slack_replied=slack_replied,
        admin_api_updated=admin_updated,
    )
    log.info("[A-2] 처리 완료: %s", result.to_dict())
    return result.to_dict()


def _lookup_creator_email(sheets_client: Any, sheet_id: str, channel_name: str) -> str:
    """크리에이터 시트에서 채널명으로 이메일을 찾는다."""
    try:
        spreadsheet = sheets_client.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1
        headers = worksheet.row_values(1)
    except Exception as exc:
        raise RuntimeError(f"크리에이터 시트 접근 실패: sheet_id={sheet_id}") from exc

    email_col_idx: Optional[int] = None
    for idx, header in enumerate(headers):
        if re.search(r"이메일|email", header, re.IGNORECASE):
            email_col_idx = idx
            break
    if email_col_idx is None:
        raise ValueError(f"이메일 컬럼을 찾을 수 없습니다. headers={headers}")

    name_col_idx = 0
    for idx, header in enumerate(headers):
        if re.search(r"채널명|채널|크리에이터|creator", header, re.IGNORECASE):
            name_col_idx = idx
            break

    for row in worksheet.get_all_values()[1:]:
        if len(row) <= max(name_col_idx, email_col_idx):
            continue
        if row[name_col_idx].strip() != channel_name.strip():
            continue
        email = row[email_col_idx].strip()
        if not email:
            raise ValueError(f"채널 '{channel_name}'의 이메일이 비어 있습니다.")
        return email

    raise ValueError(f"크리에이터 시트에서 채널명을 찾을 수 없습니다: {channel_name!r}")


def _search_drive_file(
    drive_service: Any,
    folder_id: str,
    work_title: str,
) -> tuple[str, str, str]:
    """Drive 폴더에서 작품명과 일치하는 파일을 찾는다."""
    safe_title = work_title.replace("'", "\\'")
    query = (
        f"name contains '{safe_title}' "
        f"and '{folder_id}' in parents "
        "and trashed = false"
    )
    try:
        response = drive_service.files().list(
            q=query,
            fields="files(id, name, webViewLink)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=10,
        ).execute()
    except Exception as exc:
        raise RuntimeError(f"Drive 파일 검색 실패: work_title={work_title!r}") from exc

    files = response.get("files", [])
    if not files:
        raise ValueError(
            f"Drive 폴더에서 '{work_title}' 파일을 찾지 못했습니다. folder_id={folder_id}"
        )

    if len(files) > 1:
        log.warning(
            "[A-2] 작품명 '%s'과 일치하는 파일이 %d개입니다. 첫 번째 파일을 사용합니다: %s",
            work_title,
            len(files),
            [file["name"] for file in files],
        )

    first = files[0]
    return first["id"], first["name"], first.get("webViewLink", "")


def _grant_viewer_permission(drive_service: Any, file_id: str, email: str) -> None:
    """Drive 파일에 viewer 권한을 부여한다."""
    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={
                "type": "user",
                "role": "reader",
                "emailAddress": email,
            },
            sendNotificationEmail=False,
            supportsAllDrives=True,
        ).execute()
    except Exception as exc:
        raise RuntimeError(
            f"Drive 권한 부여 실패: file_id={file_id} email={email}"
        ) from exc


def _build_approval_email(work_title: str, file_url: str, requested_at: datetime) -> str:
    date_str = requested_at.strftime("%m월 %d일")
    return f"""
<html>
<body style="font-family: sans-serif; color: #333; line-height: 1.7; max-width: 600px;">
<p>안녕하세요.</p>

<p>
귀하께서 <strong>{date_str}</strong> 요청하신
<strong>"{work_title}"</strong>의 사용을 <strong>승인</strong>하였습니다.
</p>

<p>아래 링크에서 파일을 이용해 주세요.</p>

<p style="margin: 24px 0;">
  <a href="{file_url}"
     style="background: #4285F4; color: #fff; padding: 12px 24px;
            border-radius: 4px; text-decoration: none; font-weight: bold;">
    작품 파일 열기
  </a>
</p>

<p style="font-size: 13px; color: #666;">
  링크가 열리지 않는 경우 아래 URL을 브라우저에 붙여 넣어 주세요.<br>
  <span style="word-break: break-all;">{file_url}</span>
</p>

<hr style="border: none; border-top: 1px solid #eee; margin-top: 32px;">
<p style="font-size: 12px; color: #999;">
  본 메일은 르호안아트 자동 승인 시스템에서 발송되었습니다.<br>
  문의 사항은 담당자에게 연락해 주세요.
</p>
</body>
</html>
""".strip()


def _reply_to_slack_thread(
    slack_notifier: Any,
    channel_id: str,
    thread_ts: str,
    channel_name: str,
    work_title: str,
    applicant_email: str,
) -> bool:
    """Slack 스레드에 승인 완료 메시지를 남긴다."""
    message = (
        ":white_check_mark: *승인 처리 완료*\n"
        f"• 크리에이터: *{channel_name}* ({applicant_email})\n"
        f"• 작품: *{work_title}*\n"
        "• Drive 보기 권한 부여 및 안내 메일 발송 완료"
    )
    try:
        return slack_notifier.reply_to_thread(channel_id, thread_ts, message)
    except Exception as exc:
        log.error("[A-2] Slack 스레드 회신 실패: %s", exc)
        return False


def _update_admin_api(base_url: str, message_ts: str) -> bool:
    """Admin API 상태 업데이트 stub."""
    if not base_url:
        log.info("[A-2] Admin API URL 미설정 - 상태 업데이트 건너뜀")
        return False

    endpoint = f"{base_url.rstrip('/')}/requests/{message_ts}/status"
    try:
        response = http_requests.patch(
            endpoint,
            json={"status": "확인"},
            timeout=10,
        )
        response.raise_for_status()
        log.info("[A-2] Admin API 상태 업데이트 완료: %s", endpoint)
        return True
    except Exception as exc:
        log.warning("[A-2] Admin API 상태 업데이트 실패: %s", exc)
        return False
