"""Applications routes — A3/D3 forms, triggers, monthly report."""
from __future__ import annotations

import html
import io
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from src.api.dependencies import KST, check_auth, get_supabase, invoke_lambda
from src.tasks.registry import TASK_REGISTRY
from src.api.schemas.requests import (
    A3ApplicantCreateRequest,
    A3ApplicantResponse,
    GenericTriggerRequest,
    NaverMonthlyManagerUpdateRequest,
)
from src.core.clients.google_auth_client import ALL_SCOPES, build_google_creds
from src.config import settings
from src.core.repositories.sheet_repository import SheetNaverClipApplicantRepository
from src.models import NaverClipApplicant, RepresentativeChannelPlatform

import gspread

router = APIRouter(tags=["applications"])
logger = logging.getLogger(__name__)


# ── Sheet repositories ────────────────────────────────────────────────────────

class SheetNaverMonthlyReportConfigRepository:
    """Google Sheets backed config for the Naver monthly report admin UI."""

    TAB_NAME = "A3_REPORT_CONFIG"
    HEADERS = ["manager_name", "manager_email", "updated_at"]

    def __init__(self, spreadsheet_id: str) -> None:
        if not spreadsheet_id:
            raise RuntimeError("NAVER_APPLICANT_SHEET_ID is not configured")
        self._spreadsheet_id = spreadsheet_id
        creds = build_google_creds(settings.GOOGLE_CREDENTIALS_FILE, ALL_SCOPES)
        client = gspread.authorize(creds)
        try:
            self._spreadsheet = client.open_by_key(spreadsheet_id)
        except PermissionError:
            self._spreadsheet = None

    def applicant_sheet_embed_url(self) -> dict[str, str]:
        if self._spreadsheet is None:
            return {
                "sheet_id": self._spreadsheet_id,
                "gid": "0",
                "url": f"https://docs.google.com/spreadsheets/d/{self._spreadsheet_id}/edit",
                "embed_url": f"https://docs.google.com/spreadsheets/d/{self._spreadsheet_id}/edit?rm=minimal",
            }
        worksheets = self._spreadsheet.worksheets()
        worksheet = next((item for item in worksheets if item.title == "Sheet1"), None)
        if worksheet is None:
            worksheet = worksheets[0] if worksheets else self._spreadsheet.add_worksheet(title="Sheet1", rows=1000, cols=10)
        sheet_id = self._spreadsheet.id
        gid = worksheet.id
        return {
            "sheet_id": sheet_id,
            "gid": str(gid),
            "url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={gid}",
            "embed_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit?rm=minimal#gid={gid}",
        }

    def get_manager(self) -> dict[str, str]:
        if self._spreadsheet is None:
            return {
                "manager_name": settings.SENDER_NAME or "Rhoonart",
                "manager_email": settings.NAVER_MANAGER_EMAIL or settings.SENDER_EMAIL,
                "updated_at": "",
            }
        worksheet = self._config_worksheet()
        rows = worksheet.get_all_records()
        if rows:
            row = rows[0]
            return {
                "manager_name": str(row.get("manager_name") or settings.SENDER_NAME or "Rhoonart"),
                "manager_email": str(row.get("manager_email") or settings.NAVER_MANAGER_EMAIL or settings.SENDER_EMAIL),
                "updated_at": str(row.get("updated_at") or ""),
            }
        return {
            "manager_name": settings.SENDER_NAME or "Rhoonart",
            "manager_email": settings.NAVER_MANAGER_EMAIL or settings.SENDER_EMAIL,
            "updated_at": "",
        }

    def update_manager(self, *, manager_name: str, manager_email: str) -> dict[str, str]:
        if self._spreadsheet is None:
            raise RuntimeError(
                "Google Sheet permission is missing. Share the spreadsheet with the service account."
            )
        worksheet = self._config_worksheet()
        updated_at = datetime.now(KST).isoformat()
        values = [manager_name, manager_email, updated_at]
        if len(worksheet.get_all_values()) <= 1:
            worksheet.append_row(values)
        else:
            worksheet.update("A2:C2", [values])
        return {
            "manager_name": manager_name,
            "manager_email": manager_email,
            "updated_at": updated_at,
        }

    def export_current_sheet_xlsx(self) -> tuple[str, bytes]:
        import requests as http_requests  # noqa: PLC0415
        now = datetime.now(KST)
        filename = f"naver_inbound_{now.strftime('%Y%m')}.xlsx"
        if self._spreadsheet is None:
            export_resp = http_requests.get(
                f"https://docs.google.com/spreadsheets/d/{self._spreadsheet_id}/export",
                params={"format": "xlsx", "gid": "0"},
                timeout=20,
            )
            content_type = export_resp.headers.get("content-type", "")
            if export_resp.ok and "spreadsheet" in content_type:
                return filename, export_resp.content
            raise RuntimeError(
                "Google Sheet permission is missing. Share the spreadsheet with the service account "
                "or make the sheet exportable."
            )
        from openpyxl import Workbook  # noqa: PLC0415

        worksheets = self._spreadsheet.worksheets()
        worksheet = next((item for item in worksheets if item.title == "Sheet1"), None)
        if worksheet is None:
            worksheet = worksheets[0] if worksheets else self._spreadsheet.add_worksheet(title="Sheet1", rows=1000, cols=10)

        values = worksheet.get_all_values()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sheet1"
        for row in values:
            sheet.append(row)
        for column_cells in sheet.columns:
            max_length = max((len(str(cell.value or "")) for cell in column_cells), default=0)
            column_letter = column_cells[0].column_letter
            sheet.column_dimensions[column_letter].width = min(max(max_length + 2, 10), 42)

        stream = io.BytesIO()
        workbook.save(stream)
        return filename, stream.getvalue()

    def _config_worksheet(self):
        try:
            worksheet = self._spreadsheet.worksheet(self.TAB_NAME)
        except Exception:
            worksheet = self._spreadsheet.add_worksheet(
                title=self.TAB_NAME,
                rows=20,
                cols=len(self.HEADERS),
            )
        first_row = worksheet.row_values(1)
        if first_row[: len(self.HEADERS)] != self.HEADERS:
            worksheet.update("A1:C1", [self.HEADERS])
        return worksheet


def build_naver_monthly_report_config_repository() -> SheetNaverMonthlyReportConfigRepository:
    return SheetNaverMonthlyReportConfigRepository(
        settings.NAVER_INBOUND_REPORT_SHEET_ID
        or settings.NAVER_APPLICANT_SHEET_ID
        or settings.NAVER_FORM_ID
    )


def build_naver_clip_repository() -> SheetNaverClipApplicantRepository:
    spreadsheet_id = (
        settings.NAVER_INBOUND_REPORT_SHEET_ID
        or settings.NAVER_APPLICANT_SHEET_ID
        or settings.NAVER_FORM_ID
    )
    if not spreadsheet_id:
        raise RuntimeError("NAVER_INBOUND_REPORT_SHEET_ID or NAVER_APPLICANT_SHEET_ID is not configured")
    creds = build_google_creds(settings.GOOGLE_CREDENTIALS_FILE, ALL_SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(spreadsheet_id)
    preferred_tabs = [
        "Sheet1",
        settings.NAVER_APPLICANT_TAB,
    ]
    try:
        worksheet = next(sheet.worksheet(tab) for tab in preferred_tabs if tab)
    except Exception:
        worksheet = sheet.add_worksheet(title="Sheet1", rows=1000, cols=10)
    return SheetNaverClipApplicantRepository(worksheet, spreadsheet=sheet)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_filename(value: str) -> str:
    allowed = []
    for char in value.strip():
        if char.isalnum() or char in {" ", ".", "-", "_", "(", ")"}:
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed).strip(" .") or "upload"


def _applicant_to_response(applicant: NaverClipApplicant) -> A3ApplicantResponse:
    return A3ApplicantResponse(
        applicant_id=applicant.applicant_id,
        name=applicant.name,
        phone_number=applicant.phone_number,
        naver_id=applicant.naver_id,
        naver_clip_profile_name=applicant.naver_clip_profile_name,
        naver_clip_profile_id=applicant.naver_clip_profile_id,
        representative_channel_name=applicant.representative_channel_name,
        representative_channel_platform=applicant.representative_channel_platform,
        channel_url=applicant.channel_url,
        submitted_at=applicant.submitted_at,
    )


async def _upload_kakao_creator_file(
    *,
    file: UploadFile | None,
    creator_name: str,
    field_label: str,
    submitted_at: str,
) -> dict[str, str | None]:
    if not file or not file.filename:
        return {"file_id": None, "file_name": None, "file_url": None, "mime_type": None, "size": None}

    content = await file.read()
    if not content:
        return {"file_id": None, "file_name": None, "file_url": None, "mime_type": file.content_type, "size": "0"}
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"{field_label} file exceeds 100 MB.")
    if not settings.DRIVE_FOLDER_ID:
        raise HTTPException(status_code=500, detail="DRIVE_FOLDER_ID is not configured.")

    creds = build_google_creds(settings.GOOGLE_CREDENTIALS_FILE, ALL_SCOPES)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    safe_creator = _clean_filename(creator_name)
    safe_original = _clean_filename(file.filename)
    drive_name = f"kakao-shortform_{submitted_at}_{safe_creator}_{field_label}_{safe_original}"
    media = MediaIoBaseUpload(
        io.BytesIO(content),
        mimetype=file.content_type or "application/octet-stream",
        resumable=False,
    )
    created = drive.files().create(
        body={"name": drive_name, "parents": [settings.DRIVE_FOLDER_ID]},
        media_body=media,
        fields="id,name,webViewLink,mimeType,size",
        supportsAllDrives=True,
    ).execute()
    file_id = created.get("id")
    return {
        "file_id": file_id,
        "file_name": created.get("name") or drive_name,
        "file_url": created.get("webViewLink") or (
            f"https://drive.google.com/file/d/{file_id}/view" if file_id else None
        ),
        "mime_type": created.get("mimeType") or file.content_type,
        "size": str(created.get("size") or len(content)),
    }


# ── HTML form pages ───────────────────────────────────────────────────────────

@router.get("/a3/apply", response_class=HTMLResponse)
def a3_apply_page() -> str:
    platform_options = "".join(
        f'<option value="{option.value}">{option.value}</option>'
        for option in RepresentativeChannelPlatform
    )
    return f"""
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>네이버 클립 크리에이터 프로그램 참여 신청서</title>
      <style>
        body {{ font-family: "Segoe UI", "Apple SD Gothic Neo", sans-serif; background: #f6f1ea; margin: 0; color: #18222d; }}
        .shell {{ max-width: 920px; margin: 0 auto; padding: 32px 20px 48px; }}
        .card {{ background: #fffdf8; border: 1px solid #ddcfbc; border-radius: 16px; padding: 28px; box-shadow: 0 16px 40px rgba(24,34,45,.08); }}
        h1 {{ margin-top: 0; font-size: 32px; }}
        p, small {{ color: #64717d; line-height: 1.6; }}
        .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        label {{ display: grid; gap: 8px; font-weight: 600; }}
        label.full {{ grid-column: 1 / -1; }}
        input, select {{ border: 1px solid #d7c8b5; border-radius: 10px; padding: 12px 14px; font: inherit; background: white; }}
        .help-image {{ width: min(100%, 739px); border: 1px solid #e2e8f0; border-radius: 10px; }}
        button {{ border: 0; border-radius: 999px; background: #1b6b73; color: white; padding: 14px 20px; font-weight: 700; cursor: pointer; }}
        pre {{ background: #17212b; color: #dce8f3; padding: 16px; border-radius: 12px; overflow: auto; min-height: 120px; }}
        @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} }}
      </style>
    </head>
    <body>
      <div class="shell">
        <div class="card">
          <h1>네이버 클립 크리에이터 프로그램 참여 신청서</h1>
          <p>네이버 클립 크리에이터 프로그램 등록을 위한 정보를 입력해주세요.</p>
          <form id="a3-form" class="grid">
            <label><span>이름</span><input name="name" required /></label>
            <label><span>전화번호</span><input name="phone_number" required /></label>
            <label><span>네이버 ID</span><input name="naver_id" required /></label>
            <label><span>네이버 클립 프로필명</span><input name="naver_clip_profile_name" required /></label>
            <label class="full"><span>네이버 클립 프로필 ID</span>
              <input name="naver_clip_profile_id" required />
              <small>'클립 크리에이터' 앱 &gt; 하단의 '내 클립' 탭 &gt; 빨간색 동그라미 친 부분</small>
              <img class="help-image" alt="네이버 클립 프로필 ID 확인 위치" src="https://lh7-rt.googleusercontent.com/formsz/AN7BsVA_mSmxAZR4ioRZ2SRv6FfKF8i1gilrWQ_7z3hgf2VHKeJDC8QbGl4PyrVq6lGiKHbi4Jmlv8RdDorHfY2-U3i2_NlAOQrLSxHulwf5TqM7KF7M6MYfQt3CRC53TDw0i_96xP7pnOwYYfsbMZrTk31bAesoMeJC9r5nOghtU1HiP1oqxeV4B-GMdin2kB8keoi4Yn4QOzWawlFX=w739?key=DrisoAEWc8EdWeDFYruIGQ" />
            </label>
            <label><span>대표 채널명</span><input name="representative_channel_name" required /></label>
            <label><span>대표 채널 활동 플랫폼</span><select name="representative_channel_platform" required>{platform_options}</select></label>
            <label class="full"><span>채널 URL</span><input name="channel_url" type="url" required /></label>
            <div class="full"><button type="submit">신청 저장</button></div>
          </form>
          <pre id="result">아직 제출하지 않았습니다.</pre>
        </div>
      </div>
      <script>
        const form = document.getElementById('a3-form');
        const result = document.getElementById('result');
        form.addEventListener('submit', async (event) => {{
          event.preventDefault();
          const payload = Object.fromEntries(new FormData(form).entries());
          const response = await fetch('/api/a3/applicants', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(payload),
          }});
          const data = await response.json();
          result.textContent = JSON.stringify(data, null, 2);
        }});
      </script>
    </body>
    </html>
    """


@router.get("/d3/apply", response_class=HTMLResponse)
def d3_apply_page(
    channel_id: str = "",
    channel_name: str = "",
    platform: str = "",
) -> str:
    channel_name_value = html.escape(channel_name or "")
    note_value = html.escape(
        f"portal channel_id={channel_id}, platform={platform}".strip(", ")
        if channel_id or platform
        else ""
    )
    return f"""
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>카카오톡 숏폼 크리에이터 신청</title>
      <style>
        body {{ font-family: "Segoe UI", "Apple SD Gothic Neo", sans-serif; background: #f7f8fb; margin: 0; color: #172033; }}
        .shell {{ max-width: 860px; margin: 0 auto; padding: 32px 20px 48px; }}
        .card {{ background: white; border: 1px solid #d9e2ef; border-radius: 12px; padding: 28px; box-shadow: 0 14px 34px rgba(15, 23, 42, .08); }}
        h1 {{ margin: 0; font-size: 28px; }}
        p, small {{ color: #64748b; line-height: 1.6; }}
        .grid {{ display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        label {{ display: grid; gap: 8px; font-weight: 700; color: #334155; }}
        label.full {{ grid-column: 1 / -1; }}
        input, select, textarea {{ border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px 14px; font: inherit; background: white; }}
        textarea {{ min-height: 96px; resize: vertical; }}
        button {{ border: 0; border-radius: 8px; background: #111827; color: white; padding: 13px 18px; font-weight: 800; cursor: pointer; }}
        pre {{ background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow: auto; min-height: 80px; }}
        .ok {{ color: #047857; }}
        .fail {{ color: #dc2626; }}
        @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} }}
      </style>
    </head>
    <body>
      <main class="shell">
        <section class="card">
          <h1>카카오톡 숏폼 크리에이터 신청</h1>
          <p>신청 정보와 정산 서류를 제출해주세요. 업로드 파일은 Google Drive에 저장되고, 제출 정보와 파일 링크는 Supabase에 저장됩니다.</p>
          <form id="d3-form" class="grid" enctype="multipart/form-data">
            <label><span>이름</span><input name="creator_name" value="{channel_name_value}" required /></label>
            <label><span>전화번호</span><input name="phone_number" required /></label>
            <label class="full"><span>대표 SNS 플랫폼</span>
              <select name="representative_sns_platform" required>
                <option value="">선택해주세요</option>
                <option value="유튜브">유튜브</option>
                <option value="인스타그램">인스타그램</option>
                <option value="틱톡">틱톡</option>
                <option value="네이버 클립">네이버 클립</option>
                <option value="아프리카 TV">아프리카 TV</option>
                <option value="트위치">트위치</option>
                <option value="기타">기타</option>
              </select>
              <small>여러 플랫폼에서 활동 중이어도 대표 채널이 속한 플랫폼 하나를 선택해주세요.</small>
            </label>
            <label class="full"><span>기타 플랫폼명</span><input name="representative_sns_platform_other" placeholder="기타 선택 시 입력" /></label>
            <label><span>채널명</span><input name="channel_name" required /></label>
            <label><span>채널 링크</span><input name="channel_link" type="url" placeholder="https://..." required /></label>
            <label class="full"><span>카카오톡 숏폼 계정 유형</span>
              <select name="kakao_shortform_account_type" required>
                <option value="">선택해주세요</option>
                <option value="기존 카카오톡 계정">기존 카카오톡 계정</option>
                <option value="베타 계정">베타 계정</option>
              </select>
            </label>
            <label class="full"><span>카카오톡 숏폼 계정</span>
              <input name="kakao_shortform_account_email" type="email" placeholder="qwerty12@naver.com" required />
              <small>카카오톡 숏폼 크리에이터로 활동할 계정을 이메일 형식으로 기입해주세요. 베타 계정은 기존 카카오톡 계정을 그대로 기입하면 안 됩니다.</small>
            </label>
            <label class="full"><span>신분증 or 사업자 등록증</span>
              <input name="identity_or_business_file" type="file" required />
              <small>개인 명의 정산: 신분증 사본 / 사업자 명의 정산: 사업자 등록증. 업로드가 안 될 시 개인톡으로 전달 부탁드립니다.</small>
            </label>
            <label class="full"><span>통장 사본</span>
              <input name="bankbook_file" type="file" required />
              <small>개인 명의 / 사업자 명의에 맞는 통장 사본을 업로드해주세요. 지원되는 파일 1개, 최대 100 MB입니다.</small>
            </label>
            <label class="full"><span>유튜브 - 카카오톡 숏폼 연동 서비스 이용을 희망하시나요?</span>
              <select name="youtube_kakao_sync_wanted" required>
                <option value="">선택해주세요</option>
                <option value="예">예</option>
                <option value="아니오">아니오</option>
              </select>
              <small>유튜브 업로드 영상이 자동으로 카카오톡 숏폼에도 업로드되는 서비스입니다. 인스타그램 연동 서비스는 현재 개발 중입니다.</small>
            </label>
            <label class="full"><span>메모</span><textarea name="note">{note_value}</textarea></label>
            <div class="full"><button type="submit">신청 저장</button></div>
          </form>
          <pre id="result">아직 제출하지 않았습니다.</pre>
        </section>
      </main>
      <script>
        const form = document.getElementById('d3-form');
        const result = document.getElementById('result');
        form.addEventListener('submit', async (event) => {{
          event.preventDefault();
          result.className = '';
          result.textContent = '저장 중입니다...';
          const response = await fetch('/api/d3/kakao-creators', {{
            method: 'POST',
            body: new FormData(form),
          }});
          const data = await response.json();
          result.className = response.ok ? 'ok' : 'fail';
          result.textContent = response.ok
            ? '신청이 저장되었습니다.\\n' + JSON.stringify(data, null, 2)
            : '저장 실패\\n' + JSON.stringify(data, null, 2);
        }});
      </script>
    </body>
    </html>
    """


# ── A3 applicants ─────────────────────────────────────────────────────────────

@router.get("/api/a3/applicants", response_model=list[A3ApplicantResponse])
def list_a3_applicants(_: None = Depends(check_auth)) -> list[A3ApplicantResponse]:
    repo = build_naver_clip_repository()
    return [_applicant_to_response(applicant) for applicant in repo.list_applicants()]


@router.post("/api/a3/applicants", response_model=A3ApplicantResponse)
def create_a3_applicant(payload: A3ApplicantCreateRequest) -> A3ApplicantResponse:
    try:
        repo = build_naver_clip_repository()
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=(
                "Google Sheet permission is missing. Share the settlement spreadsheet "
                "with the service account."
            ),
        ) from exc
    applicant = NaverClipApplicant.create(
        name=payload.name,
        phone_number=payload.phone_number,
        naver_id=payload.naver_id,
        naver_clip_profile_name=payload.naver_clip_profile_name,
        naver_clip_profile_id=payload.naver_clip_profile_id,
        representative_channel_name=payload.representative_channel_name,
        representative_channel_platform=payload.representative_channel_platform,
        channel_url=payload.channel_url,
    )
    logger.info(
        "A-3 applicant save requested: sheet_id=%s applicant_id=%s name=%s channel=%s",
        settings.NAVER_INBOUND_REPORT_SHEET_ID or settings.NAVER_APPLICANT_SHEET_ID,
        applicant.applicant_id,
        applicant.name,
        applicant.representative_channel_name,
    )
    saved = repo.create_applicant(applicant)
    logger.info("A-3 applicant saved: applicant_id=%s", saved.applicant_id)
    return _applicant_to_response(saved)


# ── D3 kakao creators ─────────────────────────────────────────────────────────

@router.post("/api/d3/kakao-creators")
async def create_kakao_creator_application(
    creator_name: str = Form(...),
    phone_number: str = Form(...),
    representative_sns_platform: str = Form(...),
    representative_sns_platform_other: str = Form(""),
    channel_name: str = Form(...),
    channel_link: str = Form(...),
    kakao_shortform_account_type: str = Form(...),
    kakao_shortform_account_email: str = Form(...),
    youtube_kakao_sync_wanted: str = Form(...),
    note: str = Form(""),
    identity_or_business_file: UploadFile | None = File(None),
    bankbook_file: UploadFile | None = File(None),
) -> dict[str, Any]:
    sb = get_supabase()
    now_dt = datetime.now(KST)
    now = now_dt.isoformat()
    submitted_at = now_dt.strftime("%Y%m%d_%H%M%S")
    creator = creator_name.strip()
    platform = representative_sns_platform.strip()
    platform_other = representative_sns_platform_other.strip()
    platform_label = platform_other if platform == "기타" and platform_other else platform
    identity_upload = await _upload_kakao_creator_file(
        file=identity_or_business_file,
        creator_name=creator,
        field_label="identity_or_business",
        submitted_at=submitted_at,
    )
    bankbook_upload = await _upload_kakao_creator_file(
        file=bankbook_file,
        creator_name=creator,
        field_label="bankbook",
        submitted_at=submitted_at,
    )
    row = {
        "batch_number": "1차",
        "onboarding_round": "1차",
        "partner_name": "루나르트",
        "is_active": True,
        "operation_enabled": "O",
        "is_whitelisted": True,
        "whitelist_enabled": "O",
        "creator_name": creator,
        "is_crawled": False,
        "crawling_collection": None,
        "kakao_channel": None,
        "kakao_channel_name": channel_name.strip() or None,
        "contact_email": kakao_shortform_account_email.strip() or None,
        "kakao_email": kakao_shortform_account_email.strip() or None,
        "account_type": kakao_shortform_account_type.strip() or None,
        "channel_link": channel_link.strip() or None,
        "youtube_channel_id": None,
        "subscriber_count": None,
        "scale": None,
        "category": None,
        "sub_category": None,
        "account_classification": None,
        "is_linked": youtube_kakao_sync_wanted.strip() == "예",
        "sync_enabled": "O" if youtube_kakao_sync_wanted.strip() == "예" else "X",
        "jjal_studio_id": None,
        "zzalstudio_id": None,
        "is_onboarded": False,
        "onboarding_completed": "X",
        "permission_status": None,
        "representative_sns_platform": platform_label or None,
        "representative_sns_platform_other": platform_other or None,
        "channel_name": channel_name.strip() or None,
        "phone_number": phone_number.strip() or None,
        "youtube_kakao_sync_wanted": youtube_kakao_sync_wanted.strip() or None,
        "identity_or_business_file_id": identity_upload["file_id"],
        "identity_or_business_file_name": identity_upload["file_name"],
        "identity_or_business_file_url": identity_upload["file_url"],
        "bankbook_file_id": bankbook_upload["file_id"],
        "bankbook_file_name": bankbook_upload["file_name"],
        "bankbook_file_url": bankbook_upload["file_url"],
        "status": "pending",
        "remarks": note.strip() or None,
        "note": note.strip() or None,
        "created_at": now,
        "updated_at": now,
    }
    standard_field_names = {
        "batch_number", "is_active", "is_whitelisted", "is_crawled",
        "is_linked", "jjal_studio_id", "is_onboarded", "remarks",
    }
    try:
        result = sb.table("kakao_creators").insert(row).execute()
    except Exception as exc:
        if "column" not in str(exc).lower():
            raise
        fallback_row = {key: value for key, value in row.items() if key not in standard_field_names}
        result = sb.table("kakao_creators").insert(fallback_row).execute()
    return {"status": "received", "item": (result.data or [row])[0]}


# ── Task triggers ─────────────────────────────────────────────────────────────
#
# All task dispatch goes through TASK_REGISTRY (ITaskHandler).
# Each handler's build_event() / post_invoke() encapsulates task-specific logic
# that previously lived inline in each route function.

@router.get("/api/tasks")
def list_tasks(_: None = Depends(check_auth)) -> list[dict[str, str]]:
    """Return all registered task definitions (id, name, lambda_module)."""
    from src.tasks.registry import list_all_tasks
    return list_all_tasks()


@router.post("/api/tasks/{task_id}/trigger")
def trigger_task(
    task_id: str,
    request: GenericTriggerRequest,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    """Generic task trigger — dispatches to the registered ITaskHandler."""
    handler = TASK_REGISTRY.get(task_id.upper())
    if not handler:
        raise HTTPException(status_code=404, detail=f"unknown task: {task_id}")
    return handler.execute(request.payload, invoker=invoke_lambda)


@router.post("/api/a2/trigger")
def trigger_a2(request: GenericTriggerRequest, _: None = Depends(check_auth)) -> dict[str, Any]:
    return TASK_REGISTRY["A-2"].execute(request.payload, invoker=invoke_lambda)


@router.post("/api/a3/trigger")
def trigger_a3(request: GenericTriggerRequest, _: None = Depends(check_auth)) -> dict[str, Any]:
    return TASK_REGISTRY["A-3"].execute(request.payload, invoker=invoke_lambda)


@router.post("/api/b2/trigger")
def trigger_b2(request: GenericTriggerRequest, _: None = Depends(check_auth)) -> dict[str, Any]:
    return TASK_REGISTRY["B-2"].execute(request.payload, invoker=invoke_lambda)


@router.post("/api/c1/trigger")
def trigger_c1(request: GenericTriggerRequest, _: None = Depends(check_auth)) -> dict[str, Any]:
    return TASK_REGISTRY["C-1"].execute(request.payload, invoker=invoke_lambda)


@router.post("/api/c2/trigger")
def trigger_c2(request: GenericTriggerRequest, _: None = Depends(check_auth)) -> dict[str, Any]:
    return TASK_REGISTRY["C-2"].execute(request.payload, invoker=invoke_lambda)


@router.post("/api/c3/trigger")
def trigger_c3(request: GenericTriggerRequest, _: None = Depends(check_auth)) -> dict[str, Any]:
    return TASK_REGISTRY["C-3"].execute(request.payload, invoker=invoke_lambda)


@router.post("/api/c4/trigger")
def trigger_c4(request: GenericTriggerRequest, _: None = Depends(check_auth)) -> dict[str, Any]:
    return TASK_REGISTRY["C-4"].execute(request.payload, invoker=invoke_lambda)


@router.post("/api/d3/trigger")
def trigger_d3(request: GenericTriggerRequest, _: None = Depends(check_auth)) -> dict[str, Any]:
    return TASK_REGISTRY["D-3"].execute(request.payload, invoker=invoke_lambda)


# ── Monthly report ────────────────────────────────────────────────────────────

@router.get("/api/admin/naver/monthly-report")
def get_naver_monthly_report_config(_: None = Depends(check_auth)) -> dict[str, Any]:
    repo = build_naver_monthly_report_config_repository()
    return {
        "sheet": repo.applicant_sheet_embed_url(),
        "manager": repo.get_manager(),
    }


@router.patch("/api/admin/naver/monthly-report/manager")
def update_naver_monthly_report_manager(
    request: NaverMonthlyManagerUpdateRequest,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    repo = build_naver_monthly_report_config_repository()
    return repo.update_manager(
        manager_name=request.manager_name.strip(),
        manager_email=request.manager_email.strip(),
    )


@router.get("/api/admin/naver/monthly-report/export.xlsx")
def export_naver_monthly_report_xlsx(_: None = Depends(check_auth)) -> StreamingResponse:
    repo = build_naver_monthly_report_config_repository()
    try:
        filename, content = repo.export_current_sheet_xlsx()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"엑셀 파일 생성에 실패했습니다: {exc}") from exc
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
