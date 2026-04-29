from __future__ import annotations

from typing import Any

import requests


class SupabaseB2Repository:
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
        return self._get(
            f"/b2_content_catalog?select=*&order=content_name.asc&limit={limit}"
        )

    def list_rights_holders(
        self,
        *,
        enabled_only: bool = False,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        suffix = f"/b2_rights_holders?select=*&order=rights_holder_name.asc&limit={limit}"
        if enabled_only:
            suffix = f"/b2_rights_holders?select=*&naver_report_enabled=eq.true&order=rights_holder_name.asc&limit={limit}"
        return self._get(suffix)

    def list_clip_reports(
        self,
        *,
        limit: int = 100,
        work_title: str | None = None,
    ) -> list[dict[str, Any]]:
        suffix = f"/b2_clip_reports?select=*&order=checked_at.desc,view_count.desc&limit={limit}"
        if work_title:
            from urllib.parse import quote

            suffix = (
                "/b2_clip_reports"
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
        return self._get(f"/b2_clip_reports?{'&'.join(params)}")

    def list_all_clip_reports(self, limit: int = 5000) -> list[dict[str, Any]]:
        return self._get(
            f"/b2_clip_reports?select=*&order=checked_at.desc,view_count.desc&limit={limit}"
        )

    def create_looker_delivery_stub(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            f"{self._base}/b2_run_logs",
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
