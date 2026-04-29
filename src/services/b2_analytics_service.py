from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable


@dataclass(frozen=True)
class B2AnalyticsFilters:
    checked_from: date | None = None
    checked_to: date | None = None
    uploaded_from: date | None = None
    uploaded_to: date | None = None
    channel_name: str | None = None
    clip_title: str | None = None
    work_title: str | None = None
    rights_holder_name: str | None = None
    platform: str | None = None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _contains(haystack: Any, needle: str | None) -> bool:
    if not needle:
        return True
    return needle.casefold() in str(haystack or "").casefold()


class B2AnalyticsService:
    """In-memory analytics shaping on top of clip-level report rows."""

    def filter_rows(
        self,
        rows: Iterable[dict[str, Any]],
        filters: B2AnalyticsFilters,
    ) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for row in rows:
            checked_at = _parse_date(row.get("checked_at"))
            uploaded_at = _parse_date(row.get("uploaded_at"))

            if filters.checked_from and (checked_at is None or checked_at < filters.checked_from):
                continue
            if filters.checked_to and (checked_at is None or checked_at > filters.checked_to):
                continue
            if filters.uploaded_from and (uploaded_at is None or uploaded_at < filters.uploaded_from):
                continue
            if filters.uploaded_to and (uploaded_at is None or uploaded_at > filters.uploaded_to):
                continue
            if filters.channel_name and row.get("channel_name") != filters.channel_name:
                continue
            if filters.work_title and row.get("work_title") != filters.work_title:
                continue
            if filters.rights_holder_name and row.get("rights_holder_name") != filters.rights_holder_name:
                continue
            if filters.platform and row.get("platform") != filters.platform:
                continue
            if not _contains(row.get("clip_title"), filters.clip_title):
                continue
            filtered.append(dict(row))
        return filtered

    def summarize(self, rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
        materialized = list(rows)
        views = [int(row.get("view_count") or 0) for row in materialized]
        return {
            "clip_count": len(materialized),
            "channel_count": len({row.get("channel_name") for row in materialized if row.get("channel_name")}),
            "work_count": len({row.get("work_title") for row in materialized if row.get("work_title")}),
            "rights_holder_count": len(
                {row.get("rights_holder_name") for row in materialized if row.get("rights_holder_name")}
            ),
            "total_views": sum(views),
            "max_views": max(views, default=0),
        }

    def group_rows(
        self,
        rows: Iterable[dict[str, Any]],
        *,
        group_by: str,
    ) -> list[dict[str, Any]]:
        field_map = {
            "clip": "clip_title",
            "channel": "channel_name",
            "work": "work_title",
            "rights_holder": "rights_holder_name",
        }
        key_field = field_map.get(group_by, "clip_title")
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = str(row.get(key_field) or "(unclassified)")
            buckets[key].append(row)

        grouped: list[dict[str, Any]] = []
        for key, bucket in buckets.items():
            grouped.append(
                {
                    "group_key": key,
                    "group_by": group_by,
                    "clip_count": len(bucket),
                    "channel_count": len({row.get("channel_name") for row in bucket if row.get("channel_name")}),
                    "work_count": len({row.get("work_title") for row in bucket if row.get("work_title")}),
                    "rights_holder_count": len(
                        {row.get("rights_holder_name") for row in bucket if row.get("rights_holder_name")}
                    ),
                    "total_views": sum(int(row.get("view_count") or 0) for row in bucket),
                    "latest_checked_at": max(
                        (_parse_date(row.get("checked_at")) for row in bucket if row.get("checked_at")),
                        default=None,
                    ),
                    "sample_rows": bucket[:3],
                }
            )

        grouped.sort(
            key=lambda item: (
                -int(item["total_views"]),
                str(item["group_key"]).casefold(),
            )
        )
        return grouped

    def filter_options(self, rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
        materialized = list(rows)
        checked_dates = sorted(
            {_parse_date(row.get("checked_at")) for row in materialized if row.get("checked_at")}
        )
        uploaded_dates = sorted(
            {_parse_date(row.get("uploaded_at")) for row in materialized if row.get("uploaded_at")}
        )
        return {
            "channel_names": sorted({row.get("channel_name") for row in materialized if row.get("channel_name")}),
            "work_titles": sorted({row.get("work_title") for row in materialized if row.get("work_title")}),
            "rights_holder_names": sorted(
                {row.get("rights_holder_name") for row in materialized if row.get("rights_holder_name")}
            ),
            "platforms": sorted({row.get("platform") for row in materialized if row.get("platform")}),
            "checked_date_min": checked_dates[0].isoformat() if checked_dates else None,
            "checked_date_max": checked_dates[-1].isoformat() if checked_dates else None,
            "uploaded_date_min": uploaded_dates[0].isoformat() if uploaded_dates else None,
            "uploaded_date_max": uploaded_dates[-1].isoformat() if uploaded_dates else None,
        }
