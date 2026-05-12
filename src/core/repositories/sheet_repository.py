"""Google Sheets 기반 Repository 구현체.

gspread Worksheet 객체를 주입받아 동작한다.
Supabase 전환 시 동일한 인터페이스를 구현한 SupabaseXxxRepository로 교체한다.
"""
import json
from datetime import datetime
from typing import Optional

import gspread
import pytz
from gspread.exceptions import WorksheetNotFound

from ..utils.datetime_utils import parse_form_timestamp
from ..interfaces.repository import (
    ICreatorRepository,
    IWorkRequestRepository,
    INaverClipRepository,
    IPerformanceRepository,
    ILeadRepository,
    ILogRepository,
)
from ...models import (
    Creator, OnboardingStatus,
    WorkRequest, RequestStatus,
    ChannelStat, RightsHolder, ContentCatalogItem, ClipReport,
    Lead, LeadFilter,
    LogEntry,
    NaverClipApplicant,
    RepresentativeChannelPlatform,
)
from ..logger import CoreLogger

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)


def naver_settlement_tab_name(year: int, month: int) -> str:
    return f"{year % 100:02d}.{month:02d}"


def _rows_to_dicts(ws: gspread.Worksheet) -> list[dict]:
    return ws.get_all_records(default_blank="")


class SheetCreatorRepository(ICreatorRepository):
    def __init__(self, ws: gspread.Worksheet) -> None:
        self._ws = ws

    def get_new_contracts(self, since: datetime) -> list[Creator]:
        rows = _rows_to_dicts(self._ws)
        result = []
        for i, row in enumerate(rows, start=2):
            raw_date = row.get("contract_date", "")
            if not raw_date:
                continue
            try:
                contract_date = datetime.fromisoformat(str(raw_date))
            except ValueError:
                continue
            if contract_date.replace(tzinfo=None) >= since.replace(tzinfo=None):
                result.append(Creator.from_sheet_row(row, row_index=i))
        return result

    def update_onboarding_status(self, creator_id: str, status: OnboardingStatus) -> None:
        rows = _rows_to_dicts(self._ws)
        for i, row in enumerate(rows, start=2):
            if str(row.get("creator_id", "")) == creator_id:
                col = self._col_index("onboarding_status")
                self._ws.update_cell(i, col, status.value)
                log.info("크리에이터 %s 온보딩 상태 → %s", creator_id, status.value)
                return
        log.warning("크리에이터 %s 를 시트에서 찾을 수 없음", creator_id)

    def _col_index(self, header: str) -> int:
        return self._ws.row_values(1).index(header) + 1


class SheetWorkRequestRepository(IWorkRequestRepository):
    def __init__(self, ws: gspread.Worksheet) -> None:
        self._ws = ws

    def get_request_by_message_ts(self, message_ts: str) -> Optional[WorkRequest]:
        rows = _rows_to_dicts(self._ws)
        for i, row in enumerate(rows, start=2):
            if str(row.get("slack_message_ts", "")) == message_ts:
                return self._row_to_model(row, i)
        return None

    def save_request(self, request: WorkRequest) -> None:
        self._ws.append_row([
            request.request_id,
            request.applicant_email,
            request.drive_file_id,
            request.drive_file_name,
            request.slack_message_ts,
            request.slack_channel_id,
            request.status.value,
            (request.requested_at or datetime.now(KST)).isoformat(),
            "",
        ])

    def update_request_status(self, request_id: str, status: RequestStatus) -> None:
        rows = _rows_to_dicts(self._ws)
        for i, row in enumerate(rows, start=2):
            if str(row.get("request_id", "")) == request_id:
                self._ws.update_cell(i, self._col_index("status"), status.value)
                self._ws.update_cell(i, self._col_index("processed_at"), datetime.now(KST).isoformat())
                return

    def _row_to_model(self, row: dict, row_index: int) -> WorkRequest:
        return WorkRequest(
            request_id=row.get("request_id", ""),
            applicant_email=row.get("applicant_email", ""),
            drive_file_id=row.get("drive_file_id", ""),
            drive_file_name=row.get("drive_file_name", ""),
            slack_message_ts=row.get("slack_message_ts", ""),
            slack_channel_id=row.get("slack_channel_id", ""),
            status=RequestStatus(row.get("status", "대기중")),
            row_index=row_index,
        )

    def _col_index(self, header: str) -> int:
        return self._ws.row_values(1).index(header) + 1


class SheetPerformanceRepository(IPerformanceRepository):
    """B-2 성과 보고용 Repository.

    Args:
        content_ws: 콘텐츠 관리 시트 (식별코드 목록, gid=161689321)
        stats_ws:   성과 데이터 기록 시트
        rights_ws:  작품 관리 시트 (권리사 이메일, gid=567622906)
    """

    # 콘텐츠 관리 시트 컬럼명 — 실제 헤더와 다를 경우 환경 변수로 오버라이드 가능
    COL_IDENTIFIER = "식별코드"
    COL_CONTENT_NAME = "콘텐츠명"
    # 권리사 시트 컬럼명
    COL_EMAIL = "이메일"
    COL_HOLDER_NAME = "권리사명"
    COL_DASHBOARD_URL = "대시보드URL"

    def __init__(
        self,
        content_ws: gspread.Worksheet,
        stats_ws: gspread.Worksheet,
        rights_ws: gspread.Worksheet,
        looker_dashboards: Optional[dict] = None,
    ) -> None:
        self._content_ws = content_ws
        self._stats_ws = stats_ws
        self._rights_ws = rights_ws
        # {권리사명: Looker URL} — 시트에 대시보드URL 컬럼이 없을 때 폴백으로 사용
        self._looker_dashboards: dict[str, str] = looker_dashboards or {}

    def get_content_list(self) -> list[tuple[str, str]]:
        """콘텐츠 관리 시트에서 (식별코드, 콘텐츠명) 목록 반환."""
        rows = _rows_to_dicts(self._content_ws)
        result = []
        for row in rows:
            identifier = str(row.get(self.COL_IDENTIFIER, "")).strip()
            name = str(row.get(self.COL_CONTENT_NAME, "")).strip()
            if identifier:
                result.append((identifier, name))
        log.info("콘텐츠 목록 조회: %d건", len(result))
        return result

    def get_content_catalog(self) -> list[ContentCatalogItem]:
        return [
            ContentCatalogItem(identifier=identifier, content_name=name)
            for identifier, name in self.get_content_list()
        ]

    def upsert_channel_stats(self, stats: list[ChannelStat]) -> int:
        existing = {row["channel_id"]: i + 2 for i, row in enumerate(_rows_to_dicts(self._stats_ws))}
        updated = 0
        for stat in stats:
            row_data = [
                stat.channel_id, stat.channel_name, stat.platform,
                stat.subscribers or "", stat.total_views or "",
                stat.weekly_views or "", stat.video_count or "",
                stat.crawled_at.isoformat(),
            ]
            if stat.channel_id in existing:
                row_num = existing[stat.channel_id]
                self._stats_ws.update(f"A{row_num}:H{row_num}", [row_data])
            else:
                self._stats_ws.append_row(row_data)
            updated += 1
        log.info("채널 통계 upsert 완료: %d건", updated)
        return updated

    def replace_clip_reports(self, reports: list[ClipReport]) -> int:
        del reports
        return 0

    def get_rights_holders(self) -> list[RightsHolder]:
        """'작품 관리' 탭에서 권리사 목록 반환.

        필수 컬럼: 이메일 / 선택 컬럼: 권리사명, 대시보드URL
        이메일이 없는 행은 건너뛴다.
        """
        rows = _rows_to_dicts(self._rights_ws)
        result = []
        for i, row in enumerate(rows):
            email = str(row.get(self.COL_EMAIL, "")).strip()
            if not email:
                continue
            name         = str(row.get(self.COL_HOLDER_NAME, "")).strip()
            # 시트의 대시보드URL 컬럼 우선, 없으면 looker_dashboards 맵에서 권리사명으로 조회
            dashboard_url = (
                str(row.get(self.COL_DASHBOARD_URL, "")).strip()
                or self._looker_dashboards.get(name, "")
                or None
            )
            result.append(RightsHolder(
                holder_id=str(i),
                name=name,
                email=email,
                slack_channel=str(row.get("슬랙채널", "")).strip() or None,
                dashboard_url=dashboard_url,
                channel_ids=[],
            ))
        log.info("권리사 목록 조회: %d건", len(result))
        return result


class SheetLeadRepository(ILeadRepository):
    def __init__(self, ws: gspread.Worksheet) -> None:
        self._ws = ws
        self._ensure_tier_column()

    def upsert_leads(self, leads: list[Lead]) -> int:
        all_rows = _rows_to_dicts(self._ws)
        # channel_id -> (row_number, existing_row_dict)
        existing = {row["channel_id"]: (i + 2, row) for i, row in enumerate(all_rows)}
        new_count = 0
        for lead in leads:
            if lead.channel_id in existing:
                row_num, existing_row = existing[lead.channel_id]
                # 기존 이메일 발송 상태(sent/bounced 등)를 보존하여 중복 발송 방지.
                # 크롤러가 생성한 Lead는 항상 default(미발송)이므로 그대로 덮어쓰면 안 됨.
                preserved_status = existing_row.get(
                    "email_sent_status", lead.email_sent_status.value
                )
                row_data = [
                    lead.channel_id, lead.channel_name, lead.channel_url,
                    lead.platform, lead.genre.value, lead.monthly_shorts_views,
                    lead.subscribers or "", lead.email or "",
                    preserved_status, lead.discovered_at.isoformat(), "",
                    lead.tier or "",
                ]
                self._ws.update(f"A{row_num}:L{row_num}", [row_data])
            else:
                row_data = [
                    lead.channel_id, lead.channel_name, lead.channel_url,
                    lead.platform, lead.genre.value, lead.monthly_shorts_views,
                    lead.subscribers or "", lead.email or "",
                    lead.email_sent_status.value, lead.discovered_at.isoformat(), "",
                    lead.tier or "",
                ]
                self._ws.append_row(row_data)
                new_count += 1
        log.info("리드 upsert 완료: 신규 %d건", new_count)
        return new_count

    def get_leads_for_email(self, filters: LeadFilter) -> list[Lead]:
        rows = _rows_to_dicts(self._ws)
        result = []
        for row in rows:
            lead = self._row_to_model(row)
            if filters.genre and lead.genre != filters.genre:
                continue
            if lead.monthly_shorts_views < filters.min_monthly_views:
                continue
            if filters.email_sent_status and lead.email_sent_status != filters.email_sent_status:
                continue
            if filters.platform and lead.platform != filters.platform:
                continue
            result.append(lead)
        return result

    def update_lead_email_status(self, channel_id: str, status: str) -> None:
        rows = _rows_to_dicts(self._ws)
        for i, row in enumerate(rows, start=2):
            if str(row.get("channel_id", "")) == channel_id:
                self._ws.update_cell(i, self._col_index("email_sent_status"), status)
                self._ws.update_cell(i, self._col_index("last_contacted_at"), datetime.now(KST).isoformat())
                return

    def _row_to_model(self, row: dict) -> Lead:
        from ...models.lead import Genre, EmailSentStatus
        return Lead(
            channel_id=row.get("channel_id", ""),
            channel_name=row.get("channel_name", ""),
            channel_url=row.get("channel_url", ""),
            platform=row.get("platform", ""),
            genre=Genre(row.get("genre", "기타")),
            monthly_shorts_views=int(row.get("monthly_shorts_views", 0) or 0),
            subscribers=int(row["subscribers"]) if row.get("subscribers") else None,
            email=row.get("email") or None,
            email_sent_status=EmailSentStatus(row.get("email_sent_status", "미발송")),
            tier=row.get("tier") or None,
        )

    def _col_index(self, header: str) -> int:
        return self._ws.row_values(1).index(header) + 1

    def _ensure_tier_column(self) -> None:
        headers = self._ws.row_values(1)
        if "tier" in headers:
            return
        next_col = len(headers) + 1 if headers else 1
        self._ws.add_cols(1)
        self._ws.update_cell(1, next_col, "tier")


class SheetLogRepository(ILogRepository):
    """로그 시트 스키마: task_id | task_name | executed_at | status | log_data(JSON)"""

    def __init__(self, ws: gspread.Worksheet) -> None:
        self._ws = ws
        self._ensure_header()

    def _ensure_header(self) -> None:
        if not self._ws.row_values(1):
            self._ws.append_row(["task_id", "task_name", "executed_at", "status", "log_data"])

    def write_log(self, entry: LogEntry) -> None:
        self._ws.append_row([
            entry.task_id,
            entry.task_name,
            entry.executed_at.isoformat(),
            entry.status.value,
            entry.to_json(),
        ])
        log.info("[로그] %s %s 기록 완료", entry.task_id, entry.status.value)


# ──────────────────────────────────────────────
# 구글폼 응답 Repository (A-3)
# ──────────────────────────────────────────────

class SheetFormResponseRepository(INaverClipRepository):
    """구글폼 응답 시트 Repository.

    구글폼 응답은 자동으로 연결된 스프레드시트에 저장된다.
    응답 시트의 헤더명은 폼 질문 제목과 동일하므로
    환경 변수로 컬럼명을 설정할 수 있게 한다.

    기본 컬럼명 (실제 폼 질문명과 다를 경우 오버라이드):
        타임스탬프     → 응답 일시 (구글폼 자동 생성)
        채널명         → 신청 채널명
        채널 URL       → 채널 URL
        담당자명       → 신청자 이름
        담당자 이메일  → 신청자 이메일
        장르           → 채널 장르
    """

    COL_TIMESTAMP    = "타임스탬프"
    COL_CHANNEL_NAME = "채널명"
    COL_CHANNEL_URL  = "채널 URL"
    COL_MANAGER_NAME = "담당자명"
    COL_MANAGER_EMAIL= "담당자 이메일"
    COL_GENRE        = "장르"

    def __init__(self, ws: gspread.Worksheet, col_map: Optional[dict] = None) -> None:
        self._ws = ws
        # col_map으로 컬럼명 오버라이드 가능: {"COL_TIMESTAMP": "실제헤더명", ...}
        if col_map:
            for attr, val in col_map.items():
                if hasattr(self, attr):
                    setattr(self, attr, val)

    def get_applicants_by_month(self, year: int, month: int) -> list[dict]:
        """특정 연/월에 신청한 응답자 목록 반환."""
        rows = _rows_to_dicts(self._ws)
        result = []
        for row in rows:
            ts_raw = str(row.get(self.COL_TIMESTAMP, "")).strip()
            if not ts_raw:
                continue
            try:
                # 구글폼 타임스탬프 형식: "2024/04/01 오후 3:00:00" 또는 ISO 형식
                ts = parse_form_timestamp(ts_raw)
            except ValueError:
                log.warning("타임스탬프 파싱 실패: %s", ts_raw)
                continue
            if ts.year == year and ts.month == month:
                result.append({
                    "timestamp": ts.isoformat(),
                    "channel_name": str(row.get(self.COL_CHANNEL_NAME, "")).strip(),
                    "channel_url":  str(row.get(self.COL_CHANNEL_URL, "")).strip(),
                    "manager_name": str(row.get(self.COL_MANAGER_NAME, "")).strip(),
                    "manager_email":str(row.get(self.COL_MANAGER_EMAIL, "")).strip(),
                    "genre":        str(row.get(self.COL_GENRE, "")).strip(),
                })
        log.info("폼 응답 조회 (%d년 %d월): %d건", year, month, len(result))
        return result


class SheetNaverClipApplicantRepository(INaverClipRepository):
    """Worksheet-backed repository for A-3 homepage submissions."""

    HEADER_ROW_INDEX = 5
    INSERT_ROW_INDEX = 6
    HEADERS = [
        "applicant_id",
        "submitted_at",
        "name",
        "phone_number",
        "naver_id",
        "naver_clip_profile_name",
        "naver_clip_profile_id",
        "representative_channel_name",
        "representative_channel_platform",
        "channel_url",
    ]

    def __init__(
        self,
        ws: gspread.Worksheet,
        spreadsheet: gspread.Spreadsheet | None = None,
    ) -> None:
        self._ws = ws
        self._spreadsheet = spreadsheet
        self._ensure_header()

    def create_applicant(self, applicant: NaverClipApplicant) -> NaverClipApplicant:
        headers = self._header_values()
        row = self._build_insert_row(applicant, headers)
        insert_row_index = self._insert_row_index()
        self._ws.insert_row(
            row,
            index=insert_row_index,
            value_input_option="USER_ENTERED",
        )
        self._refresh_month_highlight(applicant.submitted_at, headers)
        return applicant

    def list_applicants(self) -> list[NaverClipApplicant]:
        rows = self._applicant_rows()
        applicants: list[NaverClipApplicant] = []
        for row in rows:
            submitted_at_raw = str(
                row.get("submitted_at")
                or row.get("가입신청 일자")
                or row.get("활동시작월")
                or ""
            ).strip()
            if not submitted_at_raw:
                continue
            applicants.append(
                NaverClipApplicant(
                    applicant_id=str(row.get("applicant_id") or row.get("신청 ID") or "").strip(),
                    submitted_at=self._parse_applicant_timestamp(submitted_at_raw),
                    name=str(row.get("name") or row.get("이름") or "").strip(),
                    phone_number=str(
                        row.get("phone_number") or row.get("전화번호") or row.get("휴대폰번호") or ""
                    ).strip(),
                    naver_id=str(row.get("naver_id") or row.get("네이버ID") or row.get("네이버 ID") or "").strip(),
                    naver_clip_profile_name=str(
                        row.get("naver_clip_profile_name")
                        or row.get("네이버 클립 프로필명")
                        or row.get("클립 프로필명")
                        or ""
                    ).strip(),
                    naver_clip_profile_id=str(
                        row.get("naver_clip_profile_id")
                        or row.get("네이버 클립 프로필 ID")
                        or row.get("클립 프로필 ID")
                        or ""
                    ).strip(),
                    representative_channel_name=str(
                        row.get("representative_channel_name")
                        or row.get("대표 채널명")
                        or row.get("채널명")
                        or row.get("크리에이터명")
                        or ""
                    ).strip(),
                    representative_channel_platform=self._parse_platform(
                        str(
                            row.get("representative_channel_platform")
                            or row.get("대표 채널 플랫폼")
                            or row.get("카테고리")
                            or RepresentativeChannelPlatform.YOUTUBE.value
                        ).strip()
                    ),
                    channel_url=str(
                        row.get("channel_url")
                        or row.get("채널 URL")
                        or row.get("채널 링크")
                        or row.get("메인플랫폼URL")
                        or ""
                    ).strip(),
                )
            )
        return applicants

    def _parse_platform(self, value: str) -> RepresentativeChannelPlatform:
        try:
            return RepresentativeChannelPlatform(value)
        except ValueError:
            return RepresentativeChannelPlatform.YOUTUBE

    def _parse_applicant_timestamp(self, value: str) -> datetime:
        try:
            return parse_form_timestamp(value)
        except ValueError:
            compact = value.replace(" ", "")
            if compact.endswith("일") and "월" in compact:
                month_text, day_text = compact[:-1].split("월", 1)
                if month_text.isdigit() and day_text.isdigit():
                    now = datetime.now(KST)
                    return datetime(now.year, int(month_text), int(day_text))
            raise

    def get_applicants_by_month(self, year: int, month: int) -> list[NaverClipApplicant]:
        if self._spreadsheet is not None:
            worksheet = self._month_worksheet(year, month)
            monthly_repo = SheetNaverClipApplicantRepository(worksheet)
            return monthly_repo.list_applicants()
        return [
            applicant
            for applicant in self.list_applicants()
            if applicant.submitted_at.year == year and applicant.submitted_at.month == month
        ]

    def _ensure_header(self) -> None:
        if self._header_values():
            return
        if not self._ws.row_values(1):
            self._ws.append_row(self.HEADERS)

    def _header_values(self) -> list[str]:
        intake_header_row = self._ws.row_values(3)
        if {"크리에이터명", "클립 ID", "네이버 NID"}.issubset(
            {str(value).strip() for value in intake_header_row}
        ):
            return intake_header_row
        header_row = self._ws.row_values(self.HEADER_ROW_INDEX)
        if any(str(value).strip() for value in header_row):
            return header_row
        return self._ws.row_values(1)

    def _insert_row_index(self) -> int:
        intake_header_row = self._ws.row_values(3)
        if {"크리에이터명", "클립 ID", "네이버 NID"}.issubset(
            {str(value).strip() for value in intake_header_row}
        ):
            return 4
        return self.INSERT_ROW_INDEX

    def _data_start_row_index(self) -> int:
        intake_header_row = self._ws.row_values(3)
        if {"크리에이터명", "클립 ID", "네이버 NID"}.issubset(
            {str(value).strip() for value in intake_header_row}
        ):
            return 4
        header_row = self._ws.row_values(self.HEADER_ROW_INDEX)
        if any(str(value).strip() for value in header_row):
            return self.HEADER_ROW_INDEX + 1
        return 2

    def _applicant_rows(self) -> list[dict]:
        intake_header_row = self._ws.row_values(3)
        if {"크리에이터명", "클립 ID", "네이버 NID"}.issubset(
            {str(value).strip() for value in intake_header_row}
        ):
            headers = [str(header).strip() for header in intake_header_row]
            values = self._ws.get_all_values()[3:]
            return [
                {
                    header: row[index] if index < len(row) else ""
                    for index, header in enumerate(headers)
                    if header
                }
                for row in values
                if any(str(cell).strip() for cell in row)
            ]
        header_row = self._ws.row_values(self.HEADER_ROW_INDEX)
        if any(str(value).strip() for value in header_row):
            headers = [str(header).strip() for header in header_row]
            values = self._ws.get_all_values()[self.HEADER_ROW_INDEX :]
            return [
                {
                    header: row[index] if index < len(row) else ""
                    for index, header in enumerate(headers)
                    if header
                }
                for row in values
                if any(str(cell).strip() for cell in row)
            ]
        return _rows_to_dicts(self._ws)

    def _build_insert_row(
        self,
        applicant: NaverClipApplicant,
        headers: list[str],
    ) -> list[str]:
        values_by_header = {
            "applicant_id": applicant.applicant_id,
            "submitted_at": applicant.submitted_at.isoformat(),
            "name": applicant.name,
            "phone_number": applicant.phone_number,
            "naver_id": applicant.naver_id,
            "naver_clip_profile_name": applicant.naver_clip_profile_name,
            "naver_clip_profile_id": applicant.naver_clip_profile_id,
            "representative_channel_name": applicant.representative_channel_name,
            "representative_channel_platform": applicant.representative_channel_platform.value,
            "channel_url": applicant.channel_url,
            "신청 ID": applicant.applicant_id,
            "신청일시": applicant.submitted_at.isoformat(),
            "신청일": applicant.submitted_at.isoformat(),
            "가입신청 일자": applicant.submitted_at.strftime("%Y-%m-%d"),
            "이름": applicant.name,
            "전화번호": applicant.phone_number,
            "네이버 ID": applicant.naver_id,
            "네이버ID": applicant.naver_id,
            "네이버 클립 프로필명": applicant.naver_clip_profile_name,
            "클립 프로필명": applicant.naver_clip_profile_name,
            "네이버 클립 프로필 ID": applicant.naver_clip_profile_id,
            "클립 프로필 ID": applicant.naver_clip_profile_id,
            "대표 채널명": applicant.representative_channel_name,
            "채널명": applicant.representative_channel_name,
            "대표 채널 플랫폼": applicant.representative_channel_platform.value,
            "채널 URL": applicant.channel_url,
            "채널 링크": applicant.channel_url,
            "활동시작월": f"{applicant.submitted_at.month}월 1일"
            if hasattr(applicant.submitted_at, "month")
            else "",
            "크리에이터명": applicant.naver_clip_profile_name or applicant.representative_channel_name,
            "클립 ID": applicant.naver_clip_profile_id,
            "클립프로필 URL": applicant.naver_clip_profile_id,
            "카테고리": applicant.representative_channel_platform.value,
            "휴대폰번호": applicant.phone_number,
            "이메일": "",
            "네이버 NID": applicant.naver_id,
            "소속": "루나르트",
            "메인플랫폼URL": applicant.channel_url,
            "연동채널 URL (네이버TV 등 있을 경우에만)": "",
        }
        return [str(values_by_header.get(header.strip(), "")) for header in headers]

    def _refresh_month_highlight(self, highlighted_at: datetime, headers: list[str]) -> None:
        if not headers:
            return
        end_col = chr(ord("A") + min(len(headers), 26) - 1)
        values = self._ws.get_all_values()
        data_start_row = self._data_start_row_index()
        month_header_index = self._month_header_index(headers)
        if month_header_index is None:
            row_count = max(len(values), data_start_row)
            self._format_row_range(data_start_row, row_count, end_col, self._white_background())
            self._format_row_range(data_start_row, data_start_row, end_col, self._green_background())
            return

        current_month_rows: list[int] = []
        previous_month_rows: list[int] = []
        for row_number, row in enumerate(values[data_start_row - 1 :], start=data_start_row):
            if not any(str(cell).strip() for cell in row):
                continue
            raw_month = row[month_header_index] if month_header_index < len(row) else ""
            try:
                row_date = self._parse_applicant_timestamp(str(raw_month).strip())
            except ValueError:
                previous_month_rows.append(row_number)
                continue
            if row_date.year == highlighted_at.year and row_date.month == highlighted_at.month:
                current_month_rows.append(row_number)
            else:
                previous_month_rows.append(row_number)

        for start, end in self._group_consecutive_rows(previous_month_rows):
            self._format_row_range(start, end, end_col, self._white_background())
        for start, end in self._group_consecutive_rows(current_month_rows):
            self._format_row_range(start, end, end_col, self._green_background())

    def _month_header_index(self, headers: list[str]) -> int | None:
        candidates = {
            "submitted_at",
            "가입신청 일자",
            "신청일시",
            "신청일",
            "활동시작월",
        }
        for index, header in enumerate(headers):
            if header.strip() in candidates:
                return index
        return None

    def _format_row_range(
        self,
        start_row: int,
        end_row: int,
        end_col: str,
        background_color: dict[str, float],
    ) -> None:
        if end_row < start_row:
            return
        self._ws.format(
            f"A{start_row}:{end_col}{end_row}",
            {"backgroundColor": background_color},
        )

    def _group_consecutive_rows(self, rows: list[int]) -> list[tuple[int, int]]:
        if not rows:
            return []
        rows = sorted(rows)
        ranges: list[tuple[int, int]] = []
        start = previous = rows[0]
        for row in rows[1:]:
            if row == previous + 1:
                previous = row
                continue
            ranges.append((start, previous))
            start = previous = row
        ranges.append((start, previous))
        return ranges

    def _green_background(self) -> dict[str, float]:
        return {
            "red": 0.91,
            "green": 0.97,
            "blue": 0.94,
        }

    def _white_background(self) -> dict[str, float]:
        return {
            "red": 1.0,
            "green": 1.0,
            "blue": 1.0,
        }

    def _month_worksheet(self, year: int, month: int) -> gspread.Worksheet:
        if self._spreadsheet is None:
            return self._ws
        tab_name = naver_settlement_tab_name(year, month)
        try:
            worksheet = self._spreadsheet.worksheet(tab_name)
        except WorksheetNotFound:
            worksheet = self._spreadsheet.add_worksheet(
                title=tab_name,
                rows=1000,
                cols=len(self.HEADERS),
            )
        if not worksheet.row_values(1):
            worksheet.update("A1:J1", [self.HEADERS])
        return worksheet

    def month_sheet_url(self, year: int, month: int) -> str:
        worksheet = self._month_worksheet(year, month)
        return (
            f"https://docs.google.com/spreadsheets/d/{self._spreadsheet.id}/edit"
            f"#gid={worksheet.id}"
            if self._spreadsheet is not None
            else ""
        )
