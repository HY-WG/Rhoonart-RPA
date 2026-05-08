from __future__ import annotations

import os
import re
import sys
from typing import Any

from dotenv import load_dotenv

from create_metabase_b2_dashboard import MetabaseClient


DASHBOARD_PREFIX = "B2 Naver Clip Report"


def _extract_filter_sql(existing_query: str) -> str:
    lower_query = existing_query.lower()
    from_marker = "from public.v_naver_clip_report_daily_history h"
    from_index = lower_query.find(from_marker)
    if from_index < 0:
        raise ValueError("Cannot find v_naver_clip_report_daily_history FROM clause.")

    end_markers = [
        lower_query.find("\ngroup by", from_index),
        lower_query.find("\norder by", from_index),
        lower_query.find("\nlimit", from_index),
    ]
    end_candidates = [index for index in end_markers if index >= 0]
    end_index = min(end_candidates) if end_candidates else len(existing_query)
    return existing_query[from_index:end_index].rstrip()


def _deduped_cte(filter_sql: str) -> str:
    return f"""with deduped as (
  select
    h.checked_date_kst::date as period,
    h.rights_holder_name,
    h.channel_name,
    h.work_title,
    h.video_url,
    max(h.view_count) as view_count,
    max(h.clip_title) as clip_title,
    min(h.uploaded_at) as uploaded_at,
    string_agg(distinct h.identifier::text, ', ' order by h.identifier::text) as identifier
{filter_sql}
  group by
    h.checked_date_kst::date,
    h.rights_holder_name,
    h.channel_name,
    h.work_title,
    h.video_url
)"""


def _query_for_card(card_name: str, filter_sql: str) -> str | None:
    cte = _deduped_cte(filter_sql)
    if "영상별 수치 상세" in card_name:
        return f"""{cte}
select
  d.period as "기간",
  d.work_title as "작품명",
  d.channel_name as "채널명",
  d.clip_title as "제목",
  d.video_url as "영상 URL",
  d.uploaded_at as "업로드일",
  d.view_count as "조회수",
  d.rights_holder_name as "권리사",
  d.identifier as "identifier"
from deduped d
order by 1 desc, 7 desc, 2 asc, 3 asc
limit 1000"""

    if "일자별 조회수 추이" in card_name:
        return f"""{cte}
select
  d.period as "기간",
  sum(d.view_count) as "조회수",
  count(*) as "영상수"
from deduped d
group by d.period
order by "기간" asc"""

    if "채널명별 조회수 및 영상수" in card_name:
        return f"""{cte}
select
  d.channel_name as "채널명",
  sum(d.view_count) as "조회수",
  count(*) as "영상수"
from deduped d
group by d.channel_name
order by "조회수" desc
limit 40"""

    if re.search(r"(^| )조회수$", card_name):
        return f"""{cte}
select coalesce(sum(d.view_count), 0) as "조회수"
from deduped d"""

    if re.search(r"(^| )영상수$", card_name):
        return f"""{cte}
select count(*) as "영상수"
from deduped d"""

    if re.search(r"(^| )작품 수$", card_name):
        return f"""{cte}
select count(distinct d.work_title) as "작품 수"
from deduped d"""

    if re.search(r"(^| )채널 수$", card_name):
        return f"""{cte}
select count(distinct d.channel_name) as "채널 수"
from deduped d"""

    return None


def _native_query(dataset_query: dict[str, Any]) -> str | None:
    for stage in dataset_query.get("stages") or []:
        native = stage.get("native")
        if isinstance(native, str):
            return native
    native = dataset_query.get("native") or {}
    query = native.get("query")
    return query if isinstance(query, str) else None


def _set_native_query(dataset_query: dict[str, Any], query: str) -> bool:
    changed = False
    for stage in dataset_query.get("stages") or []:
        if isinstance(stage.get("native"), str) and stage["native"] != query:
            stage["native"] = query
            changed = True
    native = dataset_query.get("native") or {}
    if isinstance(native.get("query"), str) and native["query"] != query:
        native["query"] = query
        changed = True
    return changed


def _dashboard_cards(client: MetabaseClient) -> list[tuple[int, str]]:
    resp = client.session.get(f"{client.base_url}/api/dashboard", timeout=30)
    client._raise(resp, "GET /api/dashboard failed")
    cards: list[tuple[int, str]] = []
    for dashboard in resp.json():
        dashboard_name = str(dashboard.get("name") or "")
        if not dashboard_name.startswith(DASHBOARD_PREFIX) or dashboard.get("archived"):
            continue
        detail_resp = client.session.get(
            f"{client.base_url}/api/dashboard/{dashboard['id']}",
            timeout=30,
        )
        client._raise(detail_resp, f"GET /api/dashboard/{dashboard['id']} failed")
        for dashcard in detail_resp.json().get("dashcards") or []:
            card = dashcard.get("card") or {}
            card_id = card.get("id") or dashcard.get("card_id")
            card_name = str(card.get("name") or "")
            if card_id and card_name:
                cards.append((int(card_id), card_name))
    return cards


def main() -> int:
    load_dotenv(".env")
    base_url = os.getenv("METABASE_URL") or "http://localhost:3000"
    email = os.getenv("METABASE_EMAIL")
    password = os.getenv("METABASE_PASSWORD")
    if not email or not password:
        print("METABASE_EMAIL and METABASE_PASSWORD are required.", file=sys.stderr)
        return 2

    client = MetabaseClient(base_url, email, password)
    patched = 0
    skipped = 0
    seen_card_ids: set[int] = set()
    for card_id, card_name in _dashboard_cards(client):
        if card_id in seen_card_ids:
            continue
        seen_card_ids.add(card_id)
        card_resp = client.session.get(f"{client.base_url}/api/card/{card_id}", timeout=30)
        client._raise(card_resp, f"GET /api/card/{card_id} failed")
        card = card_resp.json()
        dataset_query = card.get("dataset_query") or {}
        native = _native_query(dataset_query)
        if not native:
            skipped += 1
            continue
        try:
            filter_sql = _extract_filter_sql(native)
        except ValueError:
            skipped += 1
            continue
        next_query = _query_for_card(card_name, filter_sql)
        if not next_query:
            skipped += 1
            continue
        if not _set_native_query(dataset_query, next_query):
            print(f"already patched card {card_id} {card_name}")
            continue
        client.put(f"/api/card/{card_id}", {"dataset_query": dataset_query})
        patched += 1
        print(f"patched card {card_id} {card_name}")

    print(f"patched={patched} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
