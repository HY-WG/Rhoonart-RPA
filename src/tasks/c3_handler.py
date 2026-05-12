"""C-3 task handler — 신규 작품 등록.

post_invoke persists the work payload to Supabase (works + naver_works tables)
so the admin UI can display the registered work immediately after triggering.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pytz

from src.api.dependencies import KST as _KST, get_supabase
from src.core.interfaces.task_handler import ITaskHandler, TaskMeta

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")


class C3TaskHandler(ITaskHandler):
    @property
    def meta(self) -> TaskMeta:
        return TaskMeta(
            task_id="C-3",
            task_name="신규 작품 등록",
            lambda_module="lambda.c3_work_register_handler",
        )

    def post_invoke(
        self,
        result: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Save work payload to Supabase works + naver_works tables."""
        try:
            saved = _save_work_payload_to_supabase(payload)
            result["supabase_work"] = saved
        except Exception as exc:
            logger.warning("works Supabase 저장 실패: %s", exc)
            result["supabase_work_error"] = str(exc)
        return result


# ---------------------------------------------------------------------------
# Supabase persistence helper (moved from applications.py)
# ---------------------------------------------------------------------------

def _save_work_payload_to_supabase(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a c3/trigger work payload to Supabase works + naver_works tables."""
    sb = get_supabase()
    now = datetime.now(_KST).isoformat()
    title = str(payload.get("work_title") or "").strip()
    if not title:
        raise ValueError("work_title is required")
    rights_holder_name = str(payload.get("rights_holder_name") or "").strip()
    release_year_raw = payload.get("release_year")
    try:
        release_year = int(release_year_raw) if str(release_year_raw or "").strip() else None
    except ValueError:
        release_year = None

    rights_holder_id = None
    if rights_holder_name:
        try:
            holder_result = (
                sb.table("rights_holders")
                .select("id")
                .eq("rights_holder_name", rights_holder_name)
                .limit(1)
                .execute()
            )
            if holder_result.data:
                rights_holder_id = holder_result.data[0].get("id")
            else:
                created = (
                    sb.table("rights_holders")
                    .insert({"rights_holder_name": rights_holder_name, "updated_at": now})
                    .execute()
                )
                if created.data:
                    rights_holder_id = created.data[0].get("id")
        except Exception as exc:
            logger.warning("rights_holders lookup/insert failed: %s", exc)

    work_payload: dict[str, Any] = {
        "work_title": title,
        "rights_holder_id": rights_holder_id,
        "release_year": release_year,
        "description": payload.get("description") or "",
        "director": payload.get("director") or "",
        "cast": payload.get("cast") or "",
        "genre": payload.get("genre") or "",
        "video_type": payload.get("video_type") or "",
        "country": payload.get("country") or "",
        "platform": ",".join(payload.get("platforms") or []),
        "platforms": payload.get("platforms") or [],
        "platform_video_url": payload.get("platform_video_url") or "",
        "trailer_url": payload.get("trailer_url") or "",
        "thumbnail_url": payload.get("thumbnail_url") or "",
        "source_download_url": payload.get("source_download_url") or "",
        "active_flag": "Active",
        "updated_at": now,
    }

    def _matching_work_query(select: str = "id"):
        query = sb.table("works").select(select).eq("work_title", title)
        if release_year is not None:
            query = query.eq("release_year", release_year)
        if rights_holder_id is not None:
            query = query.eq("rights_holder_id", rights_holder_id)
        return query

    try:
        existing_query = sb.table("works").select("id").eq("work_title", title)
        if rights_holder_id is not None:
            existing_query = existing_query.eq("rights_holder_id", rights_holder_id)
        existing = existing_query.order("id", desc=True).limit(1).execute()
        if existing.data:
            work_result = (
                sb.table("works")
                .update(work_payload)
                .eq("id", existing.data[0]["id"])
                .execute()
            )
        else:
            work_result = sb.table("works").insert(work_payload).execute()
        work_row = (work_result.data or [work_payload])[0]
    except Exception as exc:
        logger.warning("works upsert failed: %s", exc)
        minimal: dict[str, Any] = {
            "work_title": title,
            "rights_holder_id": rights_holder_id,
            "platform": ",".join(payload.get("platforms") or []),
            "active_flag": "Active",
            "updated_at": now,
        }
        existing = _matching_work_query("id").order("id", desc=True).limit(1).execute()
        if existing.data:
            work_result = (
                sb.table("works")
                .update(minimal)
                .eq("id", existing.data[0]["id"])
                .execute()
            )
        else:
            work_result = sb.table("works").insert(minimal).execute()
        work_row = (work_result.data or [minimal])[0]

    # Sync to naver_works
    naver_payload: dict[str, Any] = {
        "work_title": title,
        "identifier": payload.get("identifier") or title,
        "rights_holder_name": rights_holder_name,
        "status": "Active",
        "updated_at": now,
    }
    try:
        sb.table("naver_works").upsert(naver_payload, on_conflict="work_title").execute()
    except Exception as exc:
        logger.warning("naver_works sync failed: %s", exc)

    return work_row
