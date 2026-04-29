from __future__ import annotations

import os
from typing import Any

import gspread
import requests
from dotenv import load_dotenv

from src.api.deps import build_google_creds

WORKBOOK_ID = "1JZ0eLnvMgpjAehpxRfPN2RiG6Pd22EidnnG8tmAvlKQ"
CONTENT_TAB = "A3_작품리스트의 사본"
MANAGEMENT_TAB = "A3_작품 관리의 사본"
REPORT_TAB = "A3_NAVERCLIP_성과보고"


def _normalize(value: str) -> str:
    return str(value or "").strip().lower()


def _find_header_row(values: list[list[str]], *candidate_groups: tuple[str, ...]) -> tuple[int, list[str]]:
    for index, row in enumerate(values):
        normalized = [_normalize(cell) for cell in row]
        if all(any(_normalize(candidate) in normalized for candidate in group) for group in candidate_groups):
            return index, row
    raise RuntimeError(f"header row not found for candidates: {candidate_groups}")


def _find_header_index(headers: list[str], *candidates: str) -> int:
    normalized = [_normalize(header) for header in headers]
    for candidate in candidates:
        key = _normalize(candidate)
        if key in normalized:
            return normalized.index(key)
    raise RuntimeError(f"header index not found for candidates: {candidates}")


def _pad_row(row: list[str], size: int) -> list[str]:
    return row + [""] * max(size - len(row), 0)


class SupabaseTable:
    def __init__(self, *, url: str, service_role_key: str, table_name: str) -> None:
        self._endpoint = f"{url.rstrip('/')}/rest/v1/{table_name}"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }

    def replace_all(self, rows: list[dict[str, Any]]) -> None:
        requests.delete(
            f"{self._endpoint}?id=gt.0",
            headers=self._headers,
            timeout=30,
        ).raise_for_status()

        for start in range(0, len(rows), 500):
            chunk = rows[start : start + 500]
            requests.post(
                self._endpoint,
                headers=self._headers,
                json=chunk,
                timeout=30,
            ).raise_for_status()


def load_workbook() -> gspread.Spreadsheet:
    load_dotenv(".env")
    creds = build_google_creds(
        os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json"),
        [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    return client.open_by_key(WORKBOOK_ID)


def read_content_catalog(workbook: gspread.Spreadsheet) -> list[dict[str, Any]]:
    ws = workbook.worksheet(CONTENT_TAB)
    values = ws.get_all_values()
    header_index, headers = _find_header_row(
        values,
        ("식별코드", "identifier"),
        ("작품명", "content_name"),
    )
    idx_name = _find_header_index(headers, "작품명", "content_name")
    idx_identifier = _find_header_index(headers, "식별코드", "identifier")
    idx_rights = _find_header_index(headers, "영상권리사", "rights_holder_name")
    idx_active = _find_header_index(headers, "영상 제공 상태", "active_flag", "status")
    size = max(idx_name, idx_identifier, idx_rights, idx_active) + 1

    rows_by_name: dict[str, dict[str, Any]] = {}
    for source_row, row in enumerate(values[header_index + 1 :], start=header_index + 2):
        padded = _pad_row(row, size)
        content_name = padded[idx_name].strip()
        identifier = padded[idx_identifier].strip()
        rights_holder_name = padded[idx_rights].strip()
        active_flag = padded[idx_active].strip()
        if not content_name:
            continue
        candidate = {
            "content_name": content_name,
            "identifier": identifier or None,
            "rights_holder_name": rights_holder_name or None,
            "active_flag": active_flag or None,
            "source_row": source_row,
        }
        existing = rows_by_name.get(content_name)
        if not existing:
            rows_by_name[content_name] = candidate
            continue
        if not existing.get("identifier") and candidate.get("identifier"):
            rows_by_name[content_name] = candidate
    return list(rows_by_name.values())


def read_rights_holders(workbook: gspread.Spreadsheet) -> list[dict[str, Any]]:
    ws = workbook.worksheet(MANAGEMENT_TAB)
    values = ws.get_all_values()
    header_index, headers = _find_header_row(
        values,
        ("영상저작권자", "holder_name"),
        ("이메일", "email"),
        ("진행 중인 작품", "current_work_title"),
        ("네이버 성과 보고 진행 여부", "selection"),
    )
    idx_holder = _find_header_index(headers, "영상저작권자", "holder_name")
    idx_manager = _find_header_index(headers, "담당자", "manager_name")
    idx_email = _find_header_index(headers, "이메일", "email")
    idx_channel_sheet = _find_header_index(headers, "참여 채널 리스트", "participation_channel_sheet_url")
    idx_review_form = _find_header_index(headers, "검수폼", "review_form_url")
    idx_review_sheet = _find_header_index(headers, "검수 시트", "review_sheet_url")
    idx_work = _find_header_index(headers, "진행 중인 작품", "current_work_title")
    idx_enabled = _find_header_index(headers, "네이버 성과 보고 진행 여부", "selection")
    idx_looker_sheet = _find_header_index(headers, "Looker Studio 기반 스프레드시트", "looker_spreadsheet_url")
    idx_looker_studio = _find_header_index(headers, "Looker Studio", "looker_studio_url")
    idx_update_cycle = _find_header_index(headers, "업데이트 주기", "update_cycle")
    size = max(
        idx_holder,
        idx_manager,
        idx_email,
        idx_channel_sheet,
        idx_review_form,
        idx_review_sheet,
        idx_work,
        idx_enabled,
        idx_looker_sheet,
        idx_looker_studio,
        idx_update_cycle,
    ) + 1

    rows: list[dict[str, Any]] = []
    for source_row, row in enumerate(values[header_index + 1 :], start=header_index + 2):
        padded = _pad_row(row, size)
        holder = padded[idx_holder].strip()
        email = padded[idx_email].strip()
        current_work_title = padded[idx_work].strip()
        if not holder and not email and not current_work_title:
            continue
        rows.append(
            {
                "rights_holder_name": holder or None,
                "manager_name": padded[idx_manager].strip() or None,
                "email": email or None,
                "participation_channel_sheet_url": padded[idx_channel_sheet].strip() or None,
                "review_form_url": padded[idx_review_form].strip() or None,
                "review_sheet_url": padded[idx_review_sheet].strip() or None,
                "current_work_title": current_work_title or None,
                "naver_report_enabled": padded[idx_enabled].strip().upper() == "O",
                "looker_spreadsheet_url": padded[idx_looker_sheet].strip() or None,
                "looker_studio_url": padded[idx_looker_studio].strip() or None,
                "update_cycle": padded[idx_update_cycle].strip() or None,
                "source_row": source_row,
            }
        )
    return rows


def read_clip_reports(workbook: gspread.Spreadsheet) -> list[dict[str, Any]]:
    ws = workbook.worksheet(REPORT_TAB)
    values = ws.get_all_values()
    if not values:
        return []
    headers = values[0]
    idx_video_url = _find_header_index(headers, "영상URL")
    idx_uploaded_at = _find_header_index(headers, "영상업로드일")
    idx_channel_name = _find_header_index(headers, "채널명")
    idx_view_count = _find_header_index(headers, "조회수")
    idx_checked_at = _find_header_index(headers, "데이터확인일")
    idx_clip_title = _find_header_index(headers, "제목")
    idx_work_title = _find_header_index(headers, "작품")
    idx_platform = _find_header_index(headers, "플랫폼")
    idx_rights_holder = _find_header_index(headers, "권리사")
    size = max(
        idx_video_url,
        idx_uploaded_at,
        idx_channel_name,
        idx_view_count,
        idx_checked_at,
        idx_clip_title,
        idx_work_title,
        idx_platform,
        idx_rights_holder,
    ) + 1

    rows: list[dict[str, Any]] = []
    for source_row, row in enumerate(values[1:], start=2):
        padded = _pad_row(row, size)
        if not any(cell.strip() for cell in padded):
            continue
        raw_views = padded[idx_view_count].replace(",", "").strip()
        rows.append(
            {
                "video_url": padded[idx_video_url].strip() or None,
                "uploaded_at": padded[idx_uploaded_at].strip() or None,
                "channel_name": padded[idx_channel_name].strip() or None,
                "view_count": int(raw_views) if raw_views else 0,
                "checked_at": padded[idx_checked_at].strip() or None,
                "clip_title": padded[idx_clip_title].strip() or None,
                "work_title": padded[idx_work_title].strip(),
                "platform": padded[idx_platform].strip() or None,
                "rights_holder_name": padded[idx_rights_holder].strip() or None,
                "source_row": source_row,
            }
        )
    return rows


def main() -> None:
    load_dotenv(".env")
    supabase_url = os.environ["SUPABASE_URL"]
    service_role_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    workbook = load_workbook()
    content_rows = read_content_catalog(workbook)
    rights_rows = read_rights_holders(workbook)
    clip_rows = read_clip_reports(workbook)

    tables = {
        "b2_content_catalog": content_rows,
        "b2_rights_holders": rights_rows,
        "b2_clip_reports": clip_rows,
        "b2_run_logs": [],
    }

    for table_name, rows in tables.items():
        table = SupabaseTable(
            url=supabase_url,
            service_role_key=service_role_key,
            table_name=table_name,
        )
        table.replace_all(rows)
        print(f"{table_name}: {len(rows)} rows migrated")


if __name__ == "__main__":
    main()
