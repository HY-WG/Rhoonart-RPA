from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests
from requests import HTTPError

from ...models.performance import ChannelStat, ClipReport, RightsHolder


class SupabaseNaverRepository:
    CONTENT_TABLE = "naver_works"
    RIGHTS_HOLDERS_TABLE = "naver_rights_holders"
    CLIP_REPORTS_TABLE = "naver_clip_report_legacy_rows"
    CLIP_REPORT_STAGING_TABLE = "naver_clip_report_staging"
    CLIP_REPORT_RUNS_TABLE = "naver_clip_report_runs"
    CLIP_REPORT_DAILY_TABLE = "naver_clip_report_daily_rows"
    REPORT_DELIVERY_LOGS_TABLE = "naver_report_delivery_logs"
    REFRESH_YEAR_RPC = "refresh_naver_clip_report_year"

    def __init__(
        self,
        *,
        supabase_url: str,
        service_role_key: str,
        timeout: float = 20.0,
    ) -> None:
        base_url = supabase_url.rstrip("/")
        self._base = f"{base_url}/rest/v1"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def list_content_catalog(self, limit: int = 200) -> list[dict[str, Any]]:
        return [self._normalize_work_row(row) for row in self._get(
            f"/{self.CONTENT_TABLE}?select=*&order=work_title.asc&limit={limit}"
        )]

    def upsert_content_catalog_item(
        self,
        *,
        content_name: str,
        identifier: str,
        rights_holder_name: str,
        **extra: Any,
    ) -> dict[str, Any]:
        existing = self._get(
            f"/{self.CONTENT_TABLE}?select=*&work_title=eq.{quote(content_name)}&limit=1"
        )
        payload = {
            "work_title": content_name,
            "identifier": identifier,
            "rights_holder_name": rights_holder_name,
            "status": extra.pop("active_flag", extra.pop("status", "Active")),
            **{key: value for key, value in extra.items() if value is not None},
        }
        if existing:
            return self._normalize_work_row(self._patch(
                f"/{self.CONTENT_TABLE}?id=eq.{existing[0]['id']}",
                payload,
            ))
        return self._normalize_work_row(self._post(f"/{self.CONTENT_TABLE}", payload))

    def list_rights_holders(
        self,
        *,
        enabled_only: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        suffix = f"/{self.RIGHTS_HOLDERS_TABLE}?select=*&order=rights_holder_name.asc&limit={limit}"
        if enabled_only:
            suffix = f"/{self.RIGHTS_HOLDERS_TABLE}?select=*&naver_report_enabled=eq.true&order=rights_holder_name.asc&limit={limit}"
        return self._get(suffix)

    def upsert_rights_holder(
        self,
        *,
        rights_holder_name: str,
        email: str | None = None,
        current_work_title: str | None = None,
        naver_report_enabled: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        existing = self._get(
            f"/{self.RIGHTS_HOLDERS_TABLE}?select=*&rights_holder_name=eq.{quote(rights_holder_name)}&limit=1"
        )
        payload = {
            "rights_holder_name": rights_holder_name,
            "email": email,
            "current_work_title": current_work_title,
            "naver_report_enabled": naver_report_enabled,
            **{key: value for key, value in extra.items() if value is not None},
        }
        if existing:
            return self._patch(
                f"/{self.RIGHTS_HOLDERS_TABLE}?id=eq.{existing[0]['id']}",
                payload,
            )
        return self._post(f"/{self.RIGHTS_HOLDERS_TABLE}", payload)

    def list_enabled_content_catalog(self, limit: int = 1000) -> list[dict[str, Any]]:
        try:
            return [self._normalize_work_row(row) for row in self._get(
                f"/{self.CONTENT_TABLE}"
                "?select=*&naver_report_enabled=eq.true"
                f"&order=work_title.asc&limit={limit}"
            )]
        except HTTPError as exc:
            if exc.response is None or exc.response.status_code != 400:
                raise

        contents = self.list_content_catalog(limit=limit)
        enabled_holders = {
            row.get("rights_holder_name")
            for row in self.list_rights_holders(enabled_only=True, limit=limit)
            if row.get("rights_holder_name")
        }
        return [
            row
            for row in contents
            if row.get("identifier") and row.get("rights_holder_name") in enabled_holders
        ]

    def update_rights_holder_report_links(
        self,
        *,
        rights_holder_name: str,
        looker_spreadsheet_url: str | None = None,
        looker_studio_url: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            key: value
            for key, value in {
                "looker_spreadsheet_url": looker_spreadsheet_url,
                "looker_studio_url": looker_studio_url,
            }.items()
            if value
        }
        if not payload:
            return {}
        return self._patch(
            f"/{self.RIGHTS_HOLDERS_TABLE}?rights_holder_name=eq.{quote(rights_holder_name)}",
            payload,
        )

    def get_content_list(self) -> list[tuple[str, str]]:
        return [
            (str(row.get("identifier") or ""), str(row.get("content_name") or ""))
            for row in self.list_enabled_content_catalog()
            if row.get("identifier") and row.get("content_name")
        ]

    def upsert_channel_stats(self, stats: list[ChannelStat]) -> int:
        return len(stats)

    def replace_clip_reports(self, reports: list[ClipReport]) -> int:
        rows = [
            {
                "video_url": report.video_url,
                "uploaded_at": report.uploaded_at.isoformat() if report.uploaded_at else None,
                "channel_name": report.channel_name,
                "view_count": report.view_count,
                "checked_at": report.checked_at.isoformat(),
                "clip_title": report.clip_title,
                "work_title": report.work_title,
                "platform": report.platform,
                "rights_holder_name": report.rights_holder_name,
                "identifier": report.identifier,
            }
            for report in reports
        ]
        self._delete(f"/{self.CLIP_REPORTS_TABLE}?id=gt.0")
        for start in range(0, len(rows), 500):
            chunk = rows[start : start + 500]
            if chunk:
                self._post(f"/{self.CLIP_REPORTS_TABLE}", chunk)
        return len(rows)

    def get_rights_holders(self) -> list[RightsHolder]:
        return [
            RightsHolder(
                holder_id=str(row.get("id") or row.get("rights_holder_name") or ""),
                name=str(row.get("rights_holder_name") or ""),
                email=row.get("email"),
                dashboard_url=row.get("looker_studio_url"),
                channel_ids=[],
            )
            for row in self.list_rights_holders(enabled_only=True, limit=1000)
            if row.get("rights_holder_name")
        ]

    def list_clip_reports(
        self,
        *,
        limit: int = 100,
        work_title: str | None = None,
    ) -> list[dict[str, Any]]:
        suffix = f"/{self.CLIP_REPORTS_TABLE}?select=*&order=checked_at.desc,view_count.desc&limit={limit}"
        if work_title:
            from urllib.parse import quote

            suffix = (
                f"/{self.CLIP_REPORTS_TABLE}"
                f"?select=*&work_title=eq.{quote(work_title)}"
                "&order=checked_at.desc,view_count.desc"
                f"&limit={limit}"
            )
        return self._get(suffix)

    def list_clip_reports_filtered(
        self,
        *,
        checked_from: str | None = None,
        checked_to: str | None = None,
        uploaded_from: str | None = None,
        uploaded_to: str | None = None,
        channel_name: str | None = None,
        clip_title: str | None = None,
        work_title: str | None = None,
        rights_holder_name: str | None = None,
        platform: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        from urllib.parse import quote

        params = ["select=*", "order=checked_at.desc,view_count.desc", f"limit={limit}"]
        if checked_from:
            params.append(f"checked_at=gte.{quote(checked_from)}")
        if checked_to:
            params.append(f"checked_at=lte.{quote(checked_to)}")
        if uploaded_from:
            params.append(f"uploaded_at=gte.{quote(uploaded_from)}")
        if uploaded_to:
            params.append(f"uploaded_at=lte.{quote(uploaded_to)}")
        if channel_name:
            params.append(f"channel_name=eq.{quote(channel_name)}")
        if work_title:
            params.append(f"work_title=eq.{quote(work_title)}")
        if rights_holder_name:
            params.append(f"rights_holder_name=eq.{quote(rights_holder_name)}")
        if platform:
            params.append(f"platform=eq.{quote(platform)}")
        if clip_title:
            params.append(f"clip_title=ilike.*{quote(clip_title)}*")
        return self._get(f"/{self.CLIP_REPORTS_TABLE}?{'&'.join(params)}")

    def list_all_clip_reports(self, limit: int = 5000) -> list[dict[str, Any]]:
        return self._get(
            f"/{self.CLIP_REPORTS_TABLE}?select=*&order=checked_at.desc,view_count.desc&limit={limit}"
        )

    def replace_test_clip_reports(self, rows: list[dict[str, Any]]) -> int:
        self._delete(f"/{self.CLIP_REPORT_STAGING_TABLE}?id=gt.0")
        for start in range(0, len(rows), 500):
            chunk = rows[start : start + 500]
            if chunk:
                self._post(f"/{self.CLIP_REPORT_STAGING_TABLE}", chunk)
        return len(rows)

    def ensure_daily_clip_reports_table(self) -> None:
        try:
            self._get(f"/{self.CLIP_REPORT_DAILY_TABLE}?select=id&limit=1")
        except HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                raise RuntimeError(
                    "naver_clip_report_daily_rows table is missing. "
                    "Apply the Naver report table migration before collecting reports."
                ) from exc
            raise

    def create_daily_report_run(
        self,
        *,
        checked_at: str,
        triggered_by: str,
        target_identifier_count: int,
    ) -> dict[str, Any]:
        return self._post(
            f"/{self.CLIP_REPORT_RUNS_TABLE}",
            {
                "checked_at": checked_at,
                "triggered_by": triggered_by,
                "target_identifier_count": target_identifier_count,
                "status": "running",
            },
        )

    def finish_daily_report_run(
        self,
        *,
        run_id: str,
        status: str,
        row_count: int = 0,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        return self._patch(
            f"/{self.CLIP_REPORT_RUNS_TABLE}?run_id=eq.{run_id}",
            {
                "status": status,
                "row_count": row_count,
                "error_message": error_message,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def insert_daily_clip_reports(
        self,
        *,
        run_id: str,
        rows: list[dict[str, Any]],
    ) -> int:
        prepared = [{**row, "run_id": run_id} for row in rows]
        for start in range(0, len(prepared), 500):
            chunk = prepared[start : start + 500]
            if chunk:
                self._post(f"/{self.CLIP_REPORT_DAILY_TABLE}", chunk)
        return len(prepared)

    def refresh_yearly_clip_reports(self, year: int) -> None:
        response = requests.post(
            f"{self._base}/rpc/{self.REFRESH_YEAR_RPC}",
            headers=self._headers,
            json={"target_year": year},
            timeout=self._timeout,
        )
        response.raise_for_status()

    def create_looker_delivery_stub(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self._base}/{self.REPORT_DELIVERY_LOGS_TABLE}",
            headers={**self._headers, "Prefer": "return=representation"},
            json={
                "run_id": payload.get("run_id"),
                "execution_mode": "admin_stub",
                "send_notifications": False,
                "status": "stub_only",
                "result_json": payload,
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        rows = response.json()
        return dict(rows[0]) if rows else {}

    def _get(self, suffix: str) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self._base}{suffix}",
            headers=self._headers,
            timeout=self._timeout,
        )
        response.raise_for_status()
        return list(response.json())

    def _post(self, suffix: str, payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        response = requests.post(
            f"{self._base}{suffix}",
            headers={**self._headers, "Prefer": "return=representation"},
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        rows = response.json()
        return dict(rows[0]) if isinstance(rows, list) and rows else {}

    def _patch(self, suffix: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.patch(
            f"{self._base}{suffix}",
            headers={**self._headers, "Prefer": "return=representation"},
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        rows = response.json()
        return dict(rows[0]) if rows else {}

    def _delete(self, suffix: str) -> None:
        response = requests.delete(
            f"{self._base}{suffix}",
            headers=self._headers,
            timeout=self._timeout,
        )
        response.raise_for_status()

    @staticmethod
    def _normalize_work_row(row: dict[str, Any]) -> dict[str, Any]:
        if "content_name" not in row and "work_title" in row:
            row = {**row, "content_name": row.get("work_title")}
        if "active_flag" not in row and "status" in row:
            row = {**row, "active_flag": row.get("status")}
        return row


SupabaseB2Repository = SupabaseNaverRepository
