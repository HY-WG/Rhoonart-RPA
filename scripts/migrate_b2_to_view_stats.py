from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from typing import Any

import requests
from dotenv import load_dotenv


def _normalize(value: str | None) -> str:
    return str(value or "").strip()


def _slug(value: str | None) -> str:
    text = _normalize(value).lower()
    return "-".join(part for part in text.replace("/", " ").replace("|", " ").split() if part)


def _hash_key(*parts: str | None) -> str:
    joined = "||".join(_normalize(part) for part in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


class SupabaseRest:
    def __init__(self, *, url: str, service_role_key: str, timeout: float = 30.0) -> None:
        self._base = f"{url.rstrip('/')}/rest/v1"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def list_rows(self, table: str, *, select: str = "*", limit: int = 5000) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self._base}/{table}",
            headers=self._headers,
            params={"select": select, "limit": str(limit)},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return list(response.json())

    def upsert_rows(self, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
        if not rows:
            return
        headers = {
            **self._headers,
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
        for start in range(0, len(rows), 500):
            chunk = rows[start : start + 500]
            response = requests.post(
                f"{self._base}/{table}",
                headers=headers,
                params={"on_conflict": on_conflict},
                json=chunk,
                timeout=self._timeout,
            )
            response.raise_for_status()


def build_rights_holders(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = _normalize(row.get("rights_holder_name"))
        if not name:
            continue
        key = _slug(name)
        current = dedup.get(key, {})
        dedup[key] = {
            "rights_holder_key": key,
            "rights_holder_name": name,
            "manager_name": _normalize(row.get("manager_name")) or current.get("manager_name"),
            "email": _normalize(row.get("email")) or current.get("email"),
            "participation_channel_sheet_url": _normalize(row.get("participation_channel_sheet_url")) or current.get("participation_channel_sheet_url"),
            "review_form_url": _normalize(row.get("review_form_url")) or current.get("review_form_url"),
            "review_sheet_url": _normalize(row.get("review_sheet_url")) or current.get("review_sheet_url"),
            "naver_report_enabled": bool(row.get("naver_report_enabled")),
            "looker_spreadsheet_url": _normalize(row.get("looker_spreadsheet_url")) or current.get("looker_spreadsheet_url"),
            "looker_studio_url": _normalize(row.get("looker_studio_url")) or current.get("looker_studio_url"),
            "update_cycle": _normalize(row.get("update_cycle")) or current.get("update_cycle"),
        }
    return list(dedup.values())


def build_channels(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        channel_name = _normalize(row.get("channel_name"))
        if not channel_name:
            continue
        platform = _normalize(row.get("platform"))
        key = _slug(f"{channel_name}|{platform or 'unknown'}")
        dedup[key] = {
            "channel_key": key,
            "channel_name": channel_name,
            "platform": platform or None,
        }
    return list(dedup.values())


def build_works(
    content_catalog_rows: Iterable[dict[str, Any]],
    clip_report_rows: Iterable[dict[str, Any]],
    rights_holder_id_by_key: dict[str, int],
) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}

    for row in content_catalog_rows:
        title = _normalize(row.get("content_name"))
        if not title:
            continue
        identifier = _normalize(row.get("identifier"))
        rights_holder_name = _normalize(row.get("rights_holder_name"))
        rights_key = _slug(rights_holder_name) if rights_holder_name else ""
        work_key = identifier or _slug(f"{title}|{rights_holder_name or 'unknown'}")
        dedup[work_key] = {
            "work_key": work_key,
            "identifier": identifier or None,
            "work_title": title,
            "rights_holder_id": rights_holder_id_by_key.get(rights_key),
            "platform": None,
            "active_flag": _normalize(row.get("active_flag")) or None,
        }

    for row in clip_report_rows:
        title = _normalize(row.get("work_title"))
        if not title:
            continue
        identifier = _normalize(row.get("identifier"))
        rights_holder_name = _normalize(row.get("rights_holder_name"))
        rights_key = _slug(rights_holder_name) if rights_holder_name else ""
        work_key = identifier or _slug(f"{title}|{rights_holder_name or 'unknown'}")
        existing = dedup.get(work_key, {})
        dedup[work_key] = {
            "work_key": work_key,
            "identifier": identifier or existing.get("identifier"),
            "work_title": title,
            "rights_holder_id": rights_holder_id_by_key.get(rights_key) or existing.get("rights_holder_id"),
            "platform": _normalize(row.get("platform")) or existing.get("platform"),
            "active_flag": existing.get("active_flag"),
        }

    return list(dedup.values())


def build_clips(
    clip_report_rows: Iterable[dict[str, Any]],
    channel_id_by_key: dict[str, int],
    work_id_by_key: dict[str, int],
) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for row in clip_report_rows:
        channel_name = _normalize(row.get("channel_name"))
        platform = _normalize(row.get("platform"))
        work_title = _normalize(row.get("work_title"))
        rights_holder_name = _normalize(row.get("rights_holder_name"))
        identifier = _normalize(row.get("identifier"))
        video_url = _normalize(row.get("video_url"))
        clip_title = _normalize(row.get("clip_title"))
        uploaded_at = _normalize(row.get("uploaded_at")) or None
        channel_key = _slug(f"{channel_name}|{platform or 'unknown'}")
        work_key = identifier or _slug(f"{work_title}|{rights_holder_name or 'unknown'}")
        clip_key = video_url or _hash_key(channel_name, work_title, clip_title, uploaded_at, platform)
        dedup[clip_key] = {
            "clip_key": clip_key,
            "video_url": video_url or None,
            "clip_title": clip_title or "(untitled clip)",
            "channel_id": channel_id_by_key.get(channel_key),
            "work_id": work_id_by_key.get(work_key),
            "uploaded_at": uploaded_at,
            "platform": platform or None,
        }
    return list(dedup.values())


def build_view_stats(
    clip_report_rows: Iterable[dict[str, Any]],
    clip_id_by_key: dict[str, int],
) -> list[dict[str, Any]]:
    dedup: dict[tuple[int, str], dict[str, Any]] = {}
    for row in clip_report_rows:
        channel_name = _normalize(row.get("channel_name"))
        platform = _normalize(row.get("platform"))
        work_title = _normalize(row.get("work_title"))
        identifier = _normalize(row.get("identifier"))
        rights_holder_name = _normalize(row.get("rights_holder_name"))
        video_url = _normalize(row.get("video_url"))
        clip_title = _normalize(row.get("clip_title"))
        uploaded_at = _normalize(row.get("uploaded_at"))
        clip_key = video_url or _hash_key(channel_name, work_title, clip_title, uploaded_at, platform)
        clip_id = clip_id_by_key.get(clip_key)
        if not clip_id:
            fallback_work_key = identifier or _slug(f"{work_title}|{rights_holder_name or 'unknown'}")
            fallback_clip_key = _hash_key(channel_name, fallback_work_key, clip_title, uploaded_at, platform)
            clip_id = clip_id_by_key.get(fallback_clip_key)
        if not clip_id:
            continue
        recorded_at = _normalize(row.get("checked_at"))
        if not recorded_at:
            continue
        key = (clip_id, recorded_at)
        view_count = int(row.get("view_count") or 0)
        existing = dedup.get(key)
        if existing is None or view_count > int(existing.get("view_count") or 0):
            dedup[key] = {
                "clip_id": clip_id,
                "recorded_at": recorded_at,
                "view_count": view_count,
            }
    return list(dedup.values())


def main() -> None:
    load_dotenv(".env")
    supabase_url = os.environ["SUPABASE_URL"]
    service_role_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    api = SupabaseRest(url=supabase_url, service_role_key=service_role_key)

    b2_rights_holders = api.list_rows("b2_rights_holders")
    b2_content_catalog = api.list_rows("b2_content_catalog")
    b2_clip_reports = api.list_rows("b2_clip_reports", limit=10000)

    rights_holder_rows = build_rights_holders(b2_rights_holders)
    api.upsert_rows("rights_holders", rights_holder_rows, on_conflict="rights_holder_key")
    rights_holders = api.list_rows("rights_holders", limit=5000)
    rights_holder_id_by_key = {row["rights_holder_key"]: row["id"] for row in rights_holders}

    channel_rows = build_channels(b2_clip_reports)
    api.upsert_rows("channels", channel_rows, on_conflict="channel_key")
    channels = api.list_rows("channels", limit=5000)
    channel_id_by_key = {row["channel_key"]: row["id"] for row in channels}

    work_rows = build_works(b2_content_catalog, b2_clip_reports, rights_holder_id_by_key)
    api.upsert_rows("works", work_rows, on_conflict="work_key")
    works = api.list_rows("works", limit=5000)
    work_id_by_key = {row["work_key"]: row["id"] for row in works}

    clip_rows = build_clips(b2_clip_reports, channel_id_by_key, work_id_by_key)
    api.upsert_rows("clips", clip_rows, on_conflict="clip_key")
    clips = api.list_rows("clips", limit=10000)
    clip_id_by_key = {row["clip_key"]: row["id"] for row in clips}

    view_stat_rows = build_view_stats(b2_clip_reports, clip_id_by_key)
    api.upsert_rows("view_stats", view_stat_rows, on_conflict="clip_id,recorded_at")

    print(json.dumps(
        {
            "rights_holders": len(rights_holder_rows),
            "channels": len(channel_rows),
            "works": len(work_rows),
            "clips": len(clip_rows),
            "view_stats": len(view_stat_rows),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
