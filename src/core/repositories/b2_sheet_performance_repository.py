from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import gspread

from ...models.performance import ChannelStat, ClipReport, ContentCatalogItem, RightsHolder
from ..interfaces.repository import IPerformanceRepository
from ..logger import CoreLogger

log = CoreLogger(__name__)


def _normalize(value: str) -> str:
    return str(value or "").strip().lower()


def _find_header_row(
    values: list[list[str]],
    *required_candidate_groups: tuple[str, ...],
) -> tuple[int | None, list[str]]:
    for index, row in enumerate(values):
        normalized = [_normalize(cell) for cell in row]
        if all(any(_normalize(candidate) in normalized for candidate in group) for group in required_candidate_groups):
            return index, row
    return None, []


def _find_header_index(headers: list[str], *candidates: str) -> int | None:
    normalized = [_normalize(header) for header in headers]
    for candidate in candidates:
        key = _normalize(candidate)
        if key in normalized:
            return normalized.index(key)
    return None


def _pad_row(row: list[str], size: int) -> list[str]:
    if len(row) >= size:
        return row
    return row + [""] * (size - len(row))


def _rows_from_worksheet(
    ws: gspread.Worksheet,
    *required_candidate_groups: tuple[str, ...],
) -> tuple[list[str], list[list[str]], int]:
    values = ws.get_all_values()
    if not values:
        return [], [], 0

    header_index, headers = _find_header_row(values, *required_candidate_groups)
    if header_index is None:
        return [], [], 0

    return headers, values[header_index + 1 :], header_index + 1


class B2SheetPerformanceRepository(IPerformanceRepository):
    """Sheet-backed repository for B-2 clip crawling and reporting."""

    COL_IDENTIFIER = "identifier"
    COL_CONTENT_NAME = "content_name"

    CONTENT_ID_CANDIDATES = ("식별코드", "identifier")
    CONTENT_NAME_CANDIDATES = ("작품명", "content_name", "title")
    CONTENT_RIGHTS_HOLDER_CANDIDATES = ("영상권리사", "rights_holder_name")
    CONTENT_ACTIVE_CANDIDATES = ("영상 제공 상태", "active_flag", "status")

    MANAGEMENT_RIGHTS_HOLDER_CANDIDATES = ("영상저작권자", "권리사명", "holder_name")
    MANAGEMENT_MANAGER_CANDIDATES = ("담당자", "manager_name")
    MANAGEMENT_EMAIL_CANDIDATES = ("이메일", "email")
    MANAGEMENT_CURRENT_WORK_CANDIDATES = ("진행 중인 작품", "작품명", "current_work_title")
    MANAGEMENT_MARKER_CANDIDATES = ("네이버 성과 보고 진행 여부", "진행 여부", "선택")
    MANAGEMENT_LOOKER_SHEET_CANDIDATES = ("Looker Studio 기반 스프레드시트", "looker_spreadsheet_url")
    MANAGEMENT_LOOKER_STUDIO_CANDIDATES = ("Looker Studio", "looker_studio_url")
    MANAGEMENT_UPDATE_CYCLE_CANDIDATES = ("업데이트 주기", "update_cycle")

    REPORT_HEADERS = [
        "영상URL",
        "영상업로드일",
        "채널명",
        "조회수",
        "데이터확인일",
        "제목",
        "작품",
        "플랫폼",
        "권리사",
    ]

    def __init__(
        self,
        *,
        content_ws: gspread.Worksheet,
        stats_ws: gspread.Worksheet,
        rights_ws: gspread.Worksheet,
        management_ws: gspread.Worksheet | None = None,
        looker_dashboards: dict[str, str] | None = None,
    ) -> None:
        self._content_ws = content_ws
        self._reports_ws = stats_ws
        self._rights_ws = rights_ws
        self._management_ws = management_ws or rights_ws
        self._looker_dashboards = looker_dashboards or {}

    def get_content_catalog(self) -> list[ContentCatalogItem]:
        catalog_map = self._read_content_catalog_map()
        selected_rows = self._read_enabled_management_rows()
        if not selected_rows:
            items = list(catalog_map.values())
            log.warning("[B-2] 관리 시트에서 'O' 대상을 찾지 못해 전체 작품 카탈로그 %d건을 반환합니다.", len(items))
            return items

        results: list[ContentCatalogItem] = []
        for row in selected_rows:
            work_title = row["current_work_title"]
            item = catalog_map.get(work_title)
            if not item:
                log.warning("[B-2] 작품리스트에서 '%s' 식별코드를 찾지 못했습니다.", work_title)
                continue
            results.append(
                ContentCatalogItem(
                    identifier=item.identifier,
                    content_name=item.content_name,
                    rights_holder_name=row["rights_holder_name"] or item.rights_holder_name,
                    active_flag=item.active_flag,
                    source_row=item.source_row,
                )
            )
        log.info("[B-2] 작품 관리 시트 필터 적용: %d건 선택", len(results))
        return results

    def get_content_list(self) -> list[tuple[str, str]]:
        return [(item.identifier, item.content_name) for item in self.get_content_catalog() if item.identifier]

    def upsert_channel_stats(self, stats: list[ChannelStat]) -> int:
        # B-2 is now clip-report centric. Keep this method for compatibility and summary counts.
        return len(stats)

    def replace_clip_reports(self, reports: list[ClipReport]) -> int:
        self._reports_ws.update("A1:I1", [self.REPORT_HEADERS])
        self._clear_existing_report_rows()

        if not reports:
            log.info("[B-2] A3_NAVERCLIP_성과보고에 기록할 클립 데이터가 없습니다.")
            return 0

        rows = [
            [
                report.video_url,
                report.uploaded_at.isoformat() if report.uploaded_at else "",
                report.channel_name,
                report.view_count,
                report.checked_at.isoformat(),
                report.clip_title,
                report.work_title,
                report.platform,
                report.rights_holder_name or "",
            ]
            for report in reports
        ]
        self._reports_ws.append_rows(rows, value_input_option="USER_ENTERED")
        log.info("[B-2] A3_NAVERCLIP_성과보고 기록 완료: %d건", len(rows))
        return len(rows)

    def get_rights_holders(self) -> list[RightsHolder]:
        selected_rows = self._read_enabled_management_rows()
        holders: list[RightsHolder] = []
        seen: set[tuple[str, str, str]] = set()

        for index, row in enumerate(selected_rows, start=1):
            email = row["email"].strip()
            if not email:
                continue
            dashboard_url = row["looker_studio_url"].strip() or self._looker_dashboards.get(row["rights_holder_name"], "")
            dedupe_key = (row["rights_holder_name"], email, dashboard_url)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            holders.append(
                RightsHolder(
                    holder_id=str(index),
                    name=row["rights_holder_name"],
                    email=email,
                    dashboard_url=dashboard_url or None,
                    channel_ids=[],
                )
            )

        log.info("[B-2] 메일 발송 대상 권리사 조회: %d건", len(holders))
        return holders

    def _read_content_catalog_map(self) -> dict[str, ContentCatalogItem]:
        headers, rows, data_start_row = _rows_from_worksheet(
            self._content_ws,
            self.CONTENT_ID_CANDIDATES,
            self.CONTENT_NAME_CANDIDATES,
        )
        if not headers:
            return {}

        identifier_index = _find_header_index(headers, *self.CONTENT_ID_CANDIDATES)
        name_index = _find_header_index(headers, *self.CONTENT_NAME_CANDIDATES)
        rights_holder_index = _find_header_index(headers, *self.CONTENT_RIGHTS_HOLDER_CANDIDATES)
        active_index = _find_header_index(headers, *self.CONTENT_ACTIVE_CANDIDATES)
        if identifier_index is None or name_index is None:
            return {}

        results: dict[str, ContentCatalogItem] = {}
        required_size = max(
            index
            for index in [identifier_index, name_index, rights_holder_index, active_index]
            if index is not None
        ) + 1
        for offset, row in enumerate(rows, start=data_start_row + 1):
            padded = _pad_row(row, required_size)
            content_name = padded[name_index].strip()
            identifier = padded[identifier_index].strip()
            if not content_name:
                continue
            results[content_name] = ContentCatalogItem(
                identifier=identifier,
                content_name=content_name,
                rights_holder_name=padded[rights_holder_index].strip() if rights_holder_index is not None else None,
                active_flag=padded[active_index].strip() if active_index is not None else None,
                source_row=offset,
            )
        return results

    def _read_enabled_management_rows(self) -> list[dict[str, str]]:
        headers, rows, data_start_row = _rows_from_worksheet(
            self._management_ws,
            self.MANAGEMENT_RIGHTS_HOLDER_CANDIDATES,
            self.MANAGEMENT_EMAIL_CANDIDATES,
            self.MANAGEMENT_CURRENT_WORK_CANDIDATES,
            self.MANAGEMENT_MARKER_CANDIDATES,
        )
        if not headers:
            return []

        idx_rights_holder = _find_header_index(headers, *self.MANAGEMENT_RIGHTS_HOLDER_CANDIDATES)
        idx_manager = _find_header_index(headers, *self.MANAGEMENT_MANAGER_CANDIDATES)
        idx_email = _find_header_index(headers, *self.MANAGEMENT_EMAIL_CANDIDATES)
        idx_work = _find_header_index(headers, *self.MANAGEMENT_CURRENT_WORK_CANDIDATES)
        idx_marker = _find_header_index(headers, *self.MANAGEMENT_MARKER_CANDIDATES)
        idx_looker_sheet = _find_header_index(headers, *self.MANAGEMENT_LOOKER_SHEET_CANDIDATES)
        idx_looker_studio = _find_header_index(headers, *self.MANAGEMENT_LOOKER_STUDIO_CANDIDATES)
        idx_update_cycle = _find_header_index(headers, *self.MANAGEMENT_UPDATE_CYCLE_CANDIDATES)
        if None in {idx_rights_holder, idx_email, idx_work, idx_marker}:
            return []

        required_size = max(
            index
            for index in [
                idx_rights_holder,
                idx_manager,
                idx_email,
                idx_work,
                idx_marker,
                idx_looker_sheet,
                idx_looker_studio,
                idx_update_cycle,
            ]
            if index is not None
        ) + 1

        results: list[dict[str, str]] = []
        for offset, row in enumerate(rows, start=data_start_row + 1):
            padded = _pad_row(row, required_size)
            if padded[idx_marker].strip().upper() != "O":
                continue
            results.append(
                {
                    "rights_holder_name": padded[idx_rights_holder].strip(),
                    "manager_name": padded[idx_manager].strip() if idx_manager is not None else "",
                    "email": padded[idx_email].strip(),
                    "current_work_title": padded[idx_work].strip(),
                    "looker_spreadsheet_url": padded[idx_looker_sheet].strip() if idx_looker_sheet is not None else "",
                    "looker_studio_url": padded[idx_looker_studio].strip() if idx_looker_studio is not None else "",
                    "update_cycle": padded[idx_update_cycle].strip() if idx_update_cycle is not None else "",
                    "source_row": str(offset),
                }
            )
        return results

    def _clear_existing_report_rows(self) -> None:
        row_count = self._reports_ws.row_count
        if row_count <= 1:
            return
        clear_range = f"A2:I{row_count}"
        if hasattr(self._reports_ws, "batch_clear"):
            self._reports_ws.batch_clear([clear_range])
        else:
            blank_rows = [[""] * len(self.REPORT_HEADERS) for _ in range(row_count - 1)]
            self._reports_ws.update(clear_range, blank_rows)

