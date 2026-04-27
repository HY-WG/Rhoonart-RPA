"""Google Sheets 기반 Repository 구현체.

gspread Worksheet 객체를 주입받아 동작한다.
Supabase 전환 시 동일한 인터페이스를 구현한 SupabaseXxxRepository로 교체한다.
"""
import json
from datetime import datetime
from typing import Optional

import gspread
import pytz

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
    ChannelStat, RightsHolder,
    Lead, LeadFilter,
    LogEntry,
)
from ..logger import CoreLogger

KST = pytz.timezone("Asia/Seoul")
log = CoreLogger(__name__)


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
                ]
                self._ws.update(f"A{row_num}:K{row_num}", [row_data])
            else:
                row_data = [
                    lead.channel_id, lead.channel_name, lead.channel_url,
                    lead.platform, lead.genre.value, lead.monthly_shorts_views,
                    lead.subscribers or "", lead.email or "",
                    lead.email_sent_status.value, lead.discovered_at.isoformat(), "",
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
        )

    def _col_index(self, header: str) -> int:
        return self._ws.row_values(1).index(header) + 1


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


