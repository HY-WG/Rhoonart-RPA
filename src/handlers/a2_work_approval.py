# -*- coding: utf-8 -*-
"""A-2. 작품사용신청 승인 자동화 핸들러.

플로우:
1. Slack 메시지에서 채널명(크리에이터명)과 작품명 파싱
2. 채널명으로 크리에이터 시트에서 이메일 검색
3. 작품명으로 Google Drive 폴더에서 파일 검색
4. 신청자 이메일에 Drive 파일 보기(viewer) 권한 부여
5. 승인 안내 이메일 발송 (from hoyoungy2@gmail.com)
6. Slack 스레드에 처리 완료 메시지 회신
7. Admin API stub: PATCH /requests/{id}/status {status: "승인"}
   → Mock API 수요일 수령 후 실 연결 예정

Slack 메시지 포맷 (확정):
    채널: "유호영" 의 신규 영상 사용 요청이 있습니다.
    21세기 대군부인
"""
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

TASK_ID   = "A-2"
TASK_NAME = "작품사용신청 승인 자동화"

# ── Slack 메시지 파싱 ──────────────────────────────────────────────────────────
# 1행: 채널: "유호영" 의 신규 영상 사용 요청이 있습니다.
#   → 채널명: "유호영"
# 2행: 21세기 대군부인
#   → 작품명: "21세기 대군부인"
_SLACK_CHANNEL_RE = re.compile(r'채널:\s*["\u201c\u2018]([^"\u201d\u2019]+)["\u201d\u2019]')


# ── 결과 ───────────────────────────────────────────────────────────────────────

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

    def to_dict(self) -> dict:
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


# ── 공개 진입점 ────────────────────────────────────────────────────────────────

def parse_slack_message(text: str) -> tuple[str, str]:
    """Slack 메시지 텍스트에서 (채널명, 작품명)을 추출한다.

    포맷:
        1행: 채널: "유호영" 의 신규 영상 사용 요청이 있습니다.
        2행: 21세기 대군부인

    Raises:
        ValueError: 메시지 형식이 맞지 않거나 채널명을 추출할 수 없을 때
    """
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        raise ValueError(f"Slack 메시지 형식 오류 — 2행 이상 필요: {text!r}")

    m = _SLACK_CHANNEL_RE.search(lines[0])
    if not m:
        raise ValueError(f"채널명 추출 실패 — 1행 형식 확인 필요: {lines[0]!r}")

    channel_name = m.group(1).strip()
    work_title   = lines[1].strip()

    if not channel_name:
        raise ValueError(f"채널명이 비어 있음: {lines[0]!r}")
    if not work_title:
        raise ValueError(f"작품명이 비어 있음: {lines[1]!r}")

    log.info("[A-2] 파싱 완료 — 채널명: %r / 작품명: %r", channel_name, work_title)
    return channel_name, work_title


def run(
    slack_channel_id: str,
    slack_message_ts: str,
    slack_message_text: str,
    sheets_client: Any,          # gspread.Client (lazy import)
    drive_service: Any,          # googleapiclient.discovery Resource
    email_notifier: INotifier,
    slack_notifier: Any,         # SlackNotifier (send + reply_to_thread)
    creator_sheet_id: str,
    drive_folder_id: str,
    sender_email: str,
    admin_api_base_url: str = "",
    requested_at: Optional[datetime] = None,
) -> dict:
    """A-2 작품사용신청 승인 자동화 실행.

    Args:
        slack_channel_id:    Slack 채널 ID (스레드 회신용)
        slack_message_ts:    Slack 메시지 타임스탬프 (스레드 회신용)
        slack_message_text:  Slack 메시지 본문
        sheets_client:       인증된 gspread.Client
        drive_service:       인증된 Google Drive API Resource
        email_notifier:      이메일 발송 클라이언트
        slack_notifier:      Slack 알림 클라이언트
        creator_sheet_id:    크리에이터 시트 ID (채널명→이메일 조회)
        drive_folder_id:     작품 파일이 있는 Drive 폴더 ID
        sender_email:        발신 이메일 주소 (hoyoungy2@gmail.com)
        admin_api_base_url:  Admin API 베이스 URL (stub; 비어있으면 스킵)
        requested_at:        신청 시각 (메일 본문용, 기본: 현재)

    Returns:
        ApprovalResult.to_dict()
    """
    requested_at = requested_at or datetime.now(KST)

    # 1. Slack 메시지 파싱
    channel_name, work_title = parse_slack_message(slack_message_text)

    # 2. 크리에이터 이메일 조회 (시트 검색)
    applicant_email = _lookup_creator_email(sheets_client, creator_sheet_id, channel_name)
    log.info("[A-2] 이메일 조회 완료: %s → %s", channel_name, applicant_email)

    # 3. Drive에서 작품 파일 검색
    file_id, file_name, file_url = _search_drive_file(drive_service, drive_folder_id, work_title)
    log.info("[A-2] Drive 파일 발견: %s (id=%s)", file_name, file_id)

    # 4. 보기 권한 부여
    _grant_viewer_permission(drive_service, file_id, applicant_email)
    log.info("[A-2] 보기 권한 부여 완료: %s → %s", file_id, applicant_email)

    # 5. 승인 이메일 발송
    email_body    = _build_approval_email(work_title, file_url, requested_at)
    email_subject = f"[루나트] \"{work_title}\" 사용 승인 안내"
    email_sent = email_notifier.send(
        recipient=applicant_email,
        message=email_body,
        subject=email_subject,
        html=True,
        sender=sender_email,
    )
    if email_sent:
        log.info("[A-2] 승인 이메일 발송 완료 → %s", applicant_email)
    else:
        log.error("[A-2] 승인 이메일 발송 실패 → %s", applicant_email)

    # 6. Slack 스레드 회신
    slack_replied = _reply_to_slack_thread(
        slack_notifier, slack_channel_id, slack_message_ts,
        channel_name, work_title, applicant_email,
    )

    # 7. Admin API stub (Mock API 수령 후 실 연결)
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


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _lookup_creator_email(sheets_client: Any, sheet_id: str, channel_name: str) -> str:
    """크리에이터 시트에서 채널명으로 이메일을 검색한다.

    시트 구조 가정:
        A열: 채널명(크리에이터명)
        B열 이후: 이메일 열 포함 (헤더로 '이메일' 또는 'email' 식별)

    Raises:
        ValueError: 채널명 미발견 또는 이메일 열이 없는 경우
    """
    try:
        sh      = sheets_client.open_by_key(sheet_id)
        ws      = sh.sheet1
        headers = ws.row_values(1)
    except Exception as e:
        raise RuntimeError(f"크리에이터 시트 접근 실패 (sheet_id={sheet_id}): {e}") from e

    # 이메일 열 위치 탐색 (대소문자 무시)
    email_col_idx: Optional[int] = None
    for i, h in enumerate(headers):
        if re.search(r'이메일|email', h, re.IGNORECASE):
            email_col_idx = i
            break

    if email_col_idx is None:
        raise ValueError(f"이메일 열을 찾을 수 없음. 헤더: {headers}")

    # 채널명 열 탐색 (1열 기본, '채널명'/'크리에이터' 키워드 우선)
    name_col_idx = 0
    for i, h in enumerate(headers):
        if re.search(r'채널명|채널|크리에이터|creator', h, re.IGNORECASE):
            name_col_idx = i
            break

    # 전체 데이터 조회 후 검색 (성능상 문제 없을 정도의 시트 크기 가정)
    all_rows = ws.get_all_values()
    for row in all_rows[1:]:  # 헤더 제외
        if len(row) <= max(name_col_idx, email_col_idx):
            continue
        if row[name_col_idx].strip() == channel_name.strip():
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
    """Drive 폴더에서 작품명과 일치하는 파일을 검색한다.

    Returns:
        (file_id, file_name, web_view_link)

    Raises:
        ValueError: 파일을 찾지 못한 경우
        RuntimeError: Drive API 오류
    """
    safe_title = work_title.replace("'", "\\'")
    query = (
        f"name contains '{safe_title}' "
        f"and '{folder_id}' in parents "
        f"and trashed = false"
    )
    try:
        response = drive_service.files().list(
            q=query,
            fields="files(id, name, webViewLink)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=10,
        ).execute()
    except Exception as e:
        raise RuntimeError(f"Drive 파일 검색 실패 (작품명={work_title!r}): {e}") from e

    files = response.get("files", [])
    if not files:
        raise ValueError(
            f"Drive 폴더에서 '{work_title}' 파일을 찾지 못했습니다. "
            f"폴더 ID: {folder_id}"
        )

    # 가장 첫 번째 파일 사용 (복수 결과 시 경고)
    if len(files) > 1:
        log.warning(
            "[A-2] 작품명 '%s'에 일치하는 파일이 %d개입니다. 첫 번째를 사용합니다: %s",
            work_title, len(files), [f["name"] for f in files],
        )

    f = files[0]
    return f["id"], f["name"], f.get("webViewLink", "")


def _grant_viewer_permission(
    drive_service: Any,
    file_id: str,
    email: str,
) -> None:
    """Drive 파일에 이메일 주소로 보기(viewer) 권한을 부여한다.

    Raises:
        RuntimeError: Drive API 오류
    """
    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={
                "type":         "user",
                "role":         "reader",
                "emailAddress": email,
            },
            sendNotificationEmail=False,  # 자체 이메일 발송
            supportsAllDrives=True,
        ).execute()
    except Exception as e:
        raise RuntimeError(
            f"Drive 권한 부여 실패 (file_id={file_id}, email={email}): {e}"
        ) from e


def _build_approval_email(work_title: str, file_url: str, requested_at: datetime) -> str:
    date_str = requested_at.strftime("%m월 %d일")
    return f"""
<html>
<body style="font-family: sans-serif; color: #333; line-height: 1.7; max-width: 600px;">
<p>안녕하세요.</p>

<p>귀하께서 <strong>{date_str}</strong> 신청하신
<strong>"{work_title}"</strong>의 사용이 <strong>승인</strong>되었습니다.</p>

<p>다음 링크에서 이용해주세요.</p>

<p style="margin: 24px 0;">
  <a href="{file_url}"
     style="background: #4285F4; color: #fff; padding: 12px 24px;
            border-radius: 4px; text-decoration: none; font-weight: bold;">
    📁 작품 파일 열기
  </a>
</p>

<p style="font-size: 13px; color: #666;">
  위 링크로 접속이 어려우신 경우 아래 URL을 복사하여 브라우저에 붙여넣어 주세요.<br>
  <span style="word-break: break-all;">{file_url}</span>
</p>

<hr style="border: none; border-top: 1px solid #eee; margin-top: 32px;">
<p style="font-size: 12px; color: #999;">
  본 메일은 루나트 자동 승인 시스템에서 발송되었습니다.<br>
  문의 사항은 루나트 담당자에게 연락해 주세요.
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
    """Slack 스레드에 처리 완료 메시지를 회신한다."""
    message = (
        f":white_check_mark: *승인 처리 완료*\n"
        f"• 크리에이터: *{channel_name}* ({applicant_email})\n"
        f"• 작품: *{work_title}*\n"
        f"• Drive 보기 권한 부여 및 안내 이메일 발송 완료"
    )
    try:
        return slack_notifier.reply_to_thread(channel_id, thread_ts, message)
    except Exception as e:
        log.error("[A-2] Slack 스레드 회신 실패: %s", e)
        return False


def _update_admin_api(base_url: str, message_ts: str) -> bool:
    """Admin API로 신청 상태를 '승인'으로 업데이트한다.

    현재는 stub 구현 — Mock API 수요일 수령 후 실 연결 예정.
    base_url이 비어있으면 건너뜀.
    """
    if not base_url:
        log.info("[A-2] Admin API URL 미설정 — 상태 업데이트 건너뜀 (stub)")
        return False

    # TODO: message_ts → request_id 매핑 로직 추가 (Admin API 명세 확인 후)
    endpoint = f"{base_url.rstrip('/')}/requests/{message_ts}/status"
    try:
        resp = http_requests.patch(
            endpoint,
            json={"status": "승인"},
            timeout=10,
        )
        resp.raise_for_status()
        log.info("[A-2] Admin API 상태 업데이트 완료: %s", endpoint)
        return True
    except Exception as e:
        log.warning("[A-2] Admin API 상태 업데이트 실패 (stub): %s", e)
        return False
