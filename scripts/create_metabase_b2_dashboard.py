from __future__ import annotations

import argparse
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from dotenv import load_dotenv


LABEL_START_DATE = "\uc2dc\uc791\uc77c"
LABEL_END_DATE = "\uc885\ub8cc\uc77c"
LABEL_WORK_TITLE = "\uc791\ud488\uba85"
LABEL_CHANNEL_NAME = "\ucc44\ub110\uba85"
LABEL_PERIOD = "\uae30\uac04"
LABEL_VIEW_COUNT = "\uc870\ud68c\uc218"
LABEL_VIDEO_COUNT = "\uc601\uc0c1\uc218"
LABEL_WORK_COUNT = "\uc791\ud488 \uc218"
LABEL_CHANNEL_COUNT = "\ucc44\ub110 \uc218"
LABEL_TITLE = "\uc81c\ubaa9"
LABEL_VIDEO_URL = "\uc601\uc0c1 URL"
LABEL_UPLOADED_AT = "\uc5c5\ub85c\ub4dc\uc77c"
LABEL_RIGHTS_HOLDER = "\uad8c\ub9ac\uc0ac"


@dataclass(frozen=True)
class DashboardContext:
    parameters: list[dict[str, Any]]
    template_tags: dict[str, dict[str, Any]]
    param_ids: dict[str, str]


@dataclass(frozen=True)
class CardSpec:
    name: str
    display: str
    query: str
    row: int
    col: int
    size_x: int
    size_y: int
    visualization_settings: dict[str, Any] | None = None


class MetabaseClient:
    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        public_base_url: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.public_base_url = (public_base_url or base_url).rstrip("/")
        self.session = requests.Session()
        resp = self.session.post(
            f"{self.base_url}/api/session",
            json={"username": email, "password": password},
            timeout=30,
        )
        self._raise(resp, "Metabase login failed")
        self.session.headers.update({"X-Metabase-Session": resp.json()["id"]})

    @staticmethod
    def _raise(resp: requests.Response, message: str) -> None:
        if resp.ok:
            return
        raise RuntimeError(f"{message}: HTTP {resp.status_code} {resp.text[:1000]}")

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        resp = self.session.post(f"{self.base_url}{path}", json=payload, timeout=30)
        self._raise(resp, f"POST {path} failed")
        return resp.json()

    def put(self, path: str, payload: dict[str, Any]) -> Any:
        resp = self.session.put(f"{self.base_url}{path}", json=payload, timeout=30)
        self._raise(resp, f"PUT {path} failed")
        return resp.json()

    def enable_public_sharing(self, dashboard_id: int) -> str:
        """Enable public sharing for a dashboard and return the public embed URL."""
        resp = self.session.post(
            f"{self.base_url}/api/dashboard/{dashboard_id}/public_link",
            json={},
            timeout=30,
        )
        if not resp.ok:
            # Already shared → fetch existing UUID
            resp2 = self.session.get(
                f"{self.base_url}/api/dashboard/{dashboard_id}",
                timeout=30,
            )
            self._raise(resp2, f"GET /api/dashboard/{dashboard_id} failed")
            uuid_val = resp2.json().get("public_uuid")
            if not uuid_val:
                raise RuntimeError(
                    f"Cannot get public UUID for dashboard {dashboard_id}: "
                    f"HTTP {resp.status_code} {resp.text[:400]}"
                )
        else:
            uuid_val = resp.json().get("uuid")
        return f"{self.public_base_url}/public/dashboard/{uuid_val}"

    def query_native(self, database_id: int, query: str) -> list[dict[str, Any]]:
        result = self.post(
            "/api/dataset",
            {"type": "native", "database": database_id, "native": {"query": query}},
        )
        data = result.get("data") or {}
        cols = [col.get("name") for col in data.get("cols", [])]
        return [dict(zip(cols, row)) for row in data.get("rows", [])]


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def static_list_values(values: list[str]) -> dict[str, Any]:
    return {"values": [[value, value] for value in values]}


def category_values_config(values: list[str]) -> dict[str, Any]:
    return {
        "values": [[value, value] for value in values],
        "filter_widget_type": "select",
    }


def make_context(
    default_work_titles: list[str],
    rights_holder_names: list[str] | None = None,
    work_title_values: list[str] | None = None,
) -> DashboardContext:
    today_date = datetime.now(timezone(timedelta(hours=9))).date()
    today = today_date.isoformat()
    default_start_date = (today_date - timedelta(days=30)).isoformat()
    work_title_default: str | list[str] | None = None
    if len(default_work_titles) == 1:
        work_title_default = default_work_titles[0]
    elif len(default_work_titles) > 1:
        work_title_default = default_work_titles
    rights_holder_default = rights_holder_names[0] if rights_holder_names else None
    work_title_values = work_title_values or default_work_titles

    param_ids = {
        "start_date": str(uuid.uuid4()),
        "end_date": str(uuid.uuid4()),
        "work_title": str(uuid.uuid4()),
        "channel_name": str(uuid.uuid4()),
        "rights_holder_name": str(uuid.uuid4()),
    }
    parameters = [
        *(
            [
                {
                    "id": param_ids["rights_holder_name"],
                    "name": LABEL_RIGHTS_HOLDER,
                    "slug": "rights_holder_name",
                    "type": "category",
                    "sectionId": "string",
                    "values_source_type": "static-list",
                    "values_source_config": static_list_values(rights_holder_names),
                    **({"default": rights_holder_default} if rights_holder_default else {}),
                }
            ]
            if rights_holder_names
            else []
        ),
        {
            "id": param_ids["start_date"],
            "name": LABEL_START_DATE,
            "slug": "start_date",
            "type": "date/single",
            "sectionId": "date",
            "default": default_start_date,
        },
        {
            "id": param_ids["end_date"],
            "name": LABEL_END_DATE,
            "slug": "end_date",
            "type": "date/single",
            "sectionId": "date",
            "default": today,
        },
        {
            "id": param_ids["work_title"],
            "name": LABEL_WORK_TITLE,
            "slug": "work_title",
            "type": "category",
            "sectionId": "string",
            **(
                {
                    "values_source_type": "static-list",
                    "values_source_config": category_values_config(work_title_values),
                }
                if work_title_values
                else {}
            ),
            **({"default": work_title_default} if work_title_default else {}),
        },
        {
            "id": param_ids["channel_name"],
            "name": LABEL_CHANNEL_NAME,
            "slug": "channel_name",
            "type": "category",
            "sectionId": "string",
        },
    ]
    template_tags = {
        "start_date": {
            "id": str(uuid.uuid4()),
            "name": "start_date",
            "display-name": LABEL_START_DATE,
            "type": "date",
            "widget-type": "date/single",
            "required": False,
        },
        "end_date": {
            "id": str(uuid.uuid4()),
            "name": "end_date",
            "display-name": LABEL_END_DATE,
            "type": "date",
            "widget-type": "date/single",
            "required": False,
        },
        "work_title": {
            "id": str(uuid.uuid4()),
            "name": "work_title",
            "display-name": LABEL_WORK_TITLE,
            "type": "text",
            "widget-type": "category",
            "required": False,
        },
        "channel_name": {
            "id": str(uuid.uuid4()),
            "name": "channel_name",
            "display-name": LABEL_CHANNEL_NAME,
            "type": "text",
            "required": False,
        },
        "rights_holder_name": {
            "id": str(uuid.uuid4()),
            "name": "rights_holder_name",
            "display-name": LABEL_RIGHTS_HOLDER,
            "type": "text",
            "required": False,
        },
    }
    return DashboardContext(
        parameters=parameters,
        template_tags=template_tags,
        param_ids=param_ids,
    )


def rights_holder_match_clause(holder_names: list[str], column: str = "h.rights_holder_name") -> str:
    clauses: list[str] = []
    for holder_name in holder_names:
        holder = sql_literal(holder_name)
        clauses.append(
            f"({column} = {holder} "
            f"or {column} ilike '%' || {holder} || '%' "
            f"or {holder} ilike '%' || {column} || '%')"
        )
    if not clauses:
        return "and false"
    return "and (\n  " + "\n  or ".join(clauses) + "\n)"


def base_filter(
    enabled_rights_holders: list[str],
    holder_name: str | None = None,
    use_rights_holder_parameter: bool = False,
) -> str:
    holder_clause = rights_holder_match_clause(
        [holder_name] if holder_name else enabled_rights_holders
    )
    parameter_clause = (
        "[[and h.rights_holder_name = {{rights_holder_name}}]]"
        if use_rights_holder_parameter
        else ""
    )

    return f"""
from public.v_naver_clip_report_daily_history h
where h.checked_date_kst::date >= {{{{start_date}}}}
and h.checked_date_kst::date <= {{{{end_date}}}}
[[and h.work_title = {{{{work_title}}}}]]
[[and h.channel_name = {{{{channel_name}}}}]]
{holder_clause}
{parameter_clause}
"""


def deduped_filter_cte(filter_sql: str) -> str:
    return f"""
with deduped as (
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
)
"""


def build_cards(
    enabled_rights_holders: list[str],
    holder_name: str | None = None,
    use_rights_holder_parameter: bool = False,
    include_work_channel_counts: bool = True,
) -> list[CardSpec]:
    filter_sql = base_filter(
        enabled_rights_holders,
        holder_name,
        use_rights_holder_parameter=use_rights_holder_parameter,
    )
    prefix = f"{holder_name} " if holder_name else ""
    cards = [
        CardSpec(
            name=f"{prefix}{LABEL_VIEW_COUNT}",
            display="scalar",
            row=0,
            col=0,
            size_x=6 if include_work_channel_counts else 12,
            size_y=4,
            query=f"""
{deduped_filter_cte(filter_sql)}
select coalesce(sum(d.view_count), 0) as "{LABEL_VIEW_COUNT}"
from deduped d
""",
        ),
        CardSpec(
            name=f"{prefix}{LABEL_VIDEO_COUNT}",
            display="scalar",
            row=0,
            col=6 if include_work_channel_counts else 12,
            size_x=6 if include_work_channel_counts else 12,
            size_y=4,
            query=f"""
{deduped_filter_cte(filter_sql)}
select count(*) as "{LABEL_VIDEO_COUNT}"
from deduped d
""",
        ),
        CardSpec(
            name=f"{prefix}{LABEL_CHANNEL_NAME}\ubcc4 {LABEL_VIEW_COUNT} \ubc0f {LABEL_VIDEO_COUNT}",
            display="row",
            row=4,
            col=0,
            size_x=24,
            size_y=11,
            query=f"""
{deduped_filter_cte(filter_sql)}
select
  d.channel_name as "{LABEL_CHANNEL_NAME}",
  sum(d.view_count) as "{LABEL_VIEW_COUNT}",
  count(*) as "{LABEL_VIDEO_COUNT}"
from deduped d
group by d.channel_name
order by "{LABEL_VIEW_COUNT}" desc
limit 40
""",
            visualization_settings={
                "graph.dimensions": [LABEL_CHANNEL_NAME],
                "graph.metrics": [LABEL_VIEW_COUNT, LABEL_VIDEO_COUNT],
                "graph.show_values": True,
            },
        ),
        CardSpec(
            name=f"{prefix}\uc77c\uc790\ubcc4 {LABEL_VIEW_COUNT} \ucd94\uc774",
            display="line",
            row=15,
            col=0,
            size_x=24,
            size_y=8,
            query=f"""
{deduped_filter_cte(filter_sql)}
select
  d.period as "{LABEL_PERIOD}",
  sum(d.view_count) as "{LABEL_VIEW_COUNT}",
  count(*) as "{LABEL_VIDEO_COUNT}"
from deduped d
group by d.period
order by "{LABEL_PERIOD}" asc
""",
        ),
        CardSpec(
            name=f"{prefix}\uc601\uc0c1\ubcc4 \uc218\uce58 \uc0c1\uc138",
            display="table",
            row=23,
            col=0,
            size_x=24,
            size_y=12,
            query=f"""
{deduped_filter_cte(filter_sql)}
select
  d.period as "{LABEL_PERIOD}",
  d.work_title as "{LABEL_WORK_TITLE}",
  d.channel_name as "{LABEL_CHANNEL_NAME}",
  d.clip_title as "{LABEL_TITLE}",
  d.video_url as "{LABEL_VIDEO_URL}",
  d.uploaded_at as "{LABEL_UPLOADED_AT}",
  d.view_count as "{LABEL_VIEW_COUNT}",
  d.rights_holder_name as "{LABEL_RIGHTS_HOLDER}",
  d.identifier as "identifier"
from deduped d
order by 1 desc, 7 desc, 2 asc, 3 asc
limit 1000
""",
        ),
    ]
    if include_work_channel_counts:
        cards.insert(
            2,
            CardSpec(
                name=f"{prefix}{LABEL_WORK_COUNT}",
                display="scalar",
                row=0,
                col=12,
                size_x=6,
                size_y=4,
                query=f"""
{deduped_filter_cte(filter_sql)}
select count(distinct d.work_title) as "{LABEL_WORK_COUNT}"
from deduped d
""",
            ),
        )
        cards.insert(
            3,
            CardSpec(
                name=f"{prefix}{LABEL_CHANNEL_COUNT}",
                display="scalar",
                row=0,
                col=18,
                size_x=6,
                size_y=4,
                query=f"""
{deduped_filter_cte(filter_sql)}
select count(distinct d.channel_name) as "{LABEL_CHANNEL_COUNT}"
from deduped d
""",
            ),
        )
    return cards


def save_embed_url_to_supabase(rights_holder_name: str, embed_url: str) -> None:
    """PATCH naver_rights_holders.metabase_embed_url via Supabase REST API."""
    load_dotenv(".env")
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        print(f"  [skip] SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY not set — cannot save URL for {rights_holder_name!r}")
        return
    from urllib.parse import quote
    resp = requests.patch(
        f"{supabase_url.rstrip('/')}/rest/v1/naver_rights_holders"
        f"?rights_holder_name=eq.{quote(rights_holder_name)}",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json={"metabase_embed_url": embed_url},
        timeout=30,
    )
    if resp.ok:
        print(f"  [saved] {rights_holder_name!r} → {embed_url}")
    else:
        print(f"  [error] failed to save URL for {rights_holder_name!r}: HTTP {resp.status_code} {resp.text[:200]}")


def get_enabled_rights_holders(client: MetabaseClient, database_id: int) -> list[str]:
    try:
        rows = client.query_native(
            database_id,
            """
select distinct rights_holder_name
from public.naver_rights_holders
where naver_report_enabled is true
  and rights_holder_name is not null
  and btrim(rights_holder_name) <> ''
order by rights_holder_name
""".strip(),
        )
        result = [str(row["rights_holder_name"]) for row in rows if row.get("rights_holder_name")]
        if result:
            return result
    except Exception as exc:
        print(f"Metabase rights-holder lookup failed: {exc}")
    return get_enabled_rights_holders_from_supabase_rest()


def get_enabled_rights_holders_from_supabase_rest() -> list[str]:
    load_dotenv(".env")
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return []

    resp = requests.get(
        f"{supabase_url.rstrip('/')}/rest/v1/naver_rights_holders",
        headers={"apikey": service_key, "Authorization": f"Bearer {service_key}"},
        params={
            "select": "rights_holder_name",
            "naver_report_enabled": "eq.true",
            "order": "rights_holder_name.asc",
        },
        timeout=30,
    )
    resp.raise_for_status()
    seen: set[str] = set()
    result: list[str] = []
    for row in resp.json():
        name = str(row.get("rights_holder_name") or "").strip()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def get_default_work_titles_from_supabase_rest(enabled_rights_holders: list[str]) -> list[str]:
    load_dotenv(".env")
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return []

    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    base_url = supabase_url.rstrip("/")

    # Preferred source: current work titles on enabled Naver rights holders.
    holders_resp = requests.get(
        f"{base_url}/rest/v1/naver_rights_holders",
        headers=headers,
        params={
            "select": "current_work_title",
            "naver_report_enabled": "eq.true",
            "order": "current_work_title.asc",
        },
        timeout=30,
    )
    if holders_resp.ok:
        titles = _distinct_non_empty(row.get("current_work_title") for row in holders_resp.json())
        if titles:
            return titles

    # Fallback: use work titles that currently exist for enabled rights holders.
    if not enabled_rights_holders:
        return []
    history_resp = requests.get(
        f"{base_url}/rest/v1/v_naver_clip_report_daily_history",
        headers=headers,
        params={
            "select": "work_title,rights_holder_name",
            "order": "work_title.asc",
            "limit": "5000",
        },
        timeout=30,
    )
    if history_resp.ok:
        enabled = set(enabled_rights_holders)
        return _distinct_non_empty(
            row.get("work_title")
            for row in history_resp.json()
            if str(row.get("rights_holder_name") or "").strip() in enabled
        )
    return []


def _distinct_non_empty(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _holder_name_matches(row_holder: str, target_holder: str) -> bool:
    row_holder = row_holder.strip()
    target_holder = target_holder.strip()
    return bool(
        row_holder
        and target_holder
        and (
            row_holder == target_holder
            or row_holder in target_holder
            or target_holder in row_holder
        )
    )


def get_work_titles_by_rights_holder_from_supabase_rest(
    enabled_rights_holders: list[str],
) -> dict[str, list[str]]:
    load_dotenv(".env")
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        return {}

    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    base_url = supabase_url.rstrip("/")
    works_resp = requests.get(
        f"{base_url}/rest/v1/naver_works",
        headers=headers,
        params={
            "select": "rights_holder_name,work_title,naver_report_enabled",
            "naver_report_enabled": "eq.true",
            "order": "rights_holder_name.asc,work_title.asc",
            "limit": "5000",
        },
        timeout=30,
    )
    if works_resp.ok:
        rows = works_resp.json()
        result = {
            holder_name: _distinct_non_empty(
                row.get("work_title")
                for row in rows
                if _holder_name_matches(str(row.get("rights_holder_name") or ""), holder_name)
            )
            for holder_name in enabled_rights_holders
        }
        if any(result.values()):
            return result

    resp = requests.get(
        f"{base_url}/rest/v1/naver_rights_holders",
        headers=headers,
        params={
            "select": "rights_holder_name,current_work_title,naver_report_enabled",
            "naver_report_enabled": "eq.true",
            "order": "rights_holder_name.asc,current_work_title.asc",
        },
        timeout=30,
    )
    if not resp.ok:
        return {}
    rows = resp.json()
    return {
        holder_name: _distinct_non_empty(
            row.get("current_work_title")
            for row in rows
            if _holder_name_matches(str(row.get("rights_holder_name") or ""), holder_name)
        )
        for holder_name in enabled_rights_holders
    }


def create_collection(client: MetabaseClient) -> int:
    collection = client.post(
        "/api/collection",
        {
            "name": "B2 Naver Clip Report",
            "description": "B2 Naver Clip Report cards and dashboards",
            "color": "#509EE3",
        },
    )
    return int(collection["id"])


def create_card(
    client: MetabaseClient,
    database_id: int,
    collection_id: int,
    context: DashboardContext,
    spec: CardSpec,
) -> int:
    card = client.post(
        "/api/card",
        {
            "name": spec.name,
            "display": spec.display,
            "dataset_query": {
                "type": "native",
                "database": database_id,
                "native": {
                    "query": spec.query.strip(),
                    "template-tags": context.template_tags,
                },
            },
            "visualization_settings": spec.visualization_settings or {},
            "collection_id": collection_id,
        },
    )
    return int(card["id"])


def create_dashboard(client: MetabaseClient, collection_id: int, name: str, context: DashboardContext) -> int:
    dashboard = client.post(
        "/api/dashboard",
        {
            "name": name,
            "description": (
                "B2 Naver Clip Report. The dashboard defaults to the latest collected date "
                "and supports start date, end date, work title, and channel filters."
            ),
            "collection_id": collection_id,
            "parameters": context.parameters,
        },
    )
    dashboard_id = int(dashboard["id"])
    try:
        client.put(f"/api/dashboard/{dashboard_id}", {"parameters": context.parameters})
    except Exception:
        pass
    return dashboard_id


def parameter_mappings(context: DashboardContext, card_id: int) -> list[dict[str, Any]]:
    tags = [parameter["slug"] for parameter in context.parameters]
    return [
        {
            "parameter_id": context.param_ids[tag],
            "card_id": card_id,
            "target": ["variable", ["template-tag", tag]],
        }
        for tag in tags
    ]


def add_cards_to_dashboard(
    client: MetabaseClient,
    dashboard_id: int,
    context: DashboardContext,
    card_ids: list[tuple[int, CardSpec]],
) -> None:
    cards = [
        {
            "id": -(idx + 1),
            "card_id": card_id,
            "dashboard_id": dashboard_id,
            "row": spec.row,
            "col": spec.col,
            "size_x": spec.size_x,
            "size_y": spec.size_y,
            "parameter_mappings": parameter_mappings(context, card_id),
            "series": [],
            "visualization_settings": {},
        }
        for idx, (card_id, spec) in enumerate(card_ids)
    ]
    errors: list[str] = []
    for payload in [
        {"cards": cards, "parameters": context.parameters},
        {"dashcards": cards, "parameters": context.parameters},
    ]:
        resp = client.session.put(
            f"{client.base_url}/api/dashboard/{dashboard_id}/cards",
            json=payload,
            timeout=30,
        )
        if resp.ok:
            return
        errors.append(
            f"PUT /api/dashboard/{dashboard_id}/cards failed: "
            f"HTTP {resp.status_code} {resp.text[:1000]}"
        )
    raise RuntimeError("Failed to add cards to dashboard:\n" + "\n".join(errors))


def create_report_dashboard(
    client: MetabaseClient,
    database_id: int,
    collection_id: int,
    dashboard_name: str,
    default_work_titles: list[str],
    holder_name: str | None = None,
    holder_work_titles: list[str] | None = None,
) -> int:
    context = make_context(
        default_work_titles=[] if holder_name else default_work_titles,
        work_title_values=holder_work_titles if holder_name else default_work_titles,
    )
    dashboard_id = create_dashboard(client, collection_id, dashboard_name, context)
    created_cards: list[tuple[int, CardSpec]] = []
    enabled_rights_holders = [holder_name] if holder_name else get_enabled_rights_holders(
        client, database_id
    )
    for spec in build_cards(enabled_rights_holders, holder_name):
        card_id = create_card(client, database_id, collection_id, context, spec)
        created_cards.append((card_id, spec))
        print(f"created card: {card_id} {dashboard_name} / {spec.name}")
    add_cards_to_dashboard(client, dashboard_id, context, created_cards)
    return dashboard_id


def create_selector_dashboard(
    client: MetabaseClient,
    database_id: int,
    collection_id: int,
    dashboard_name: str,
    enabled_rights_holders: list[str],
    default_work_titles: list[str],
) -> int:
    context = make_context(
        default_work_titles=[],
        rights_holder_names=enabled_rights_holders,
    )
    dashboard_id = create_dashboard(client, collection_id, dashboard_name, context)
    created_cards: list[tuple[int, CardSpec]] = []
    for spec in build_cards(
        enabled_rights_holders,
        holder_name=None,
        use_rights_holder_parameter=True,
        include_work_channel_counts=False,
    ):
        card_id = create_card(client, database_id, collection_id, context, spec)
        created_cards.append((card_id, spec))
        print(f"created card: {card_id} {dashboard_name} / {spec.name}")
    add_cards_to_dashboard(client, dashboard_id, context, created_cards)
    return dashboard_id


def parse_args() -> argparse.Namespace:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(
        description="Create B2 Naver Clip Report Metabase dashboards."
    )
    parser.add_argument("--url", default=os.getenv("METABASE_URL", "http://localhost:3001"))
    parser.add_argument(
        "--public-url",
        default=os.getenv("METABASE_PUBLIC_URL"),
        help=(
            "Externally reachable Metabase base URL to save into Supabase, "
            "for example http://192.168.0.202:3001 or https://reports.example.com. "
            "Falls back to --url when omitted."
        ),
    )
    parser.add_argument("--email", default=os.getenv("METABASE_EMAIL"))
    parser.add_argument("--password", default=os.getenv("METABASE_PASSWORD"))
    parser.add_argument("--database-id", type=int, default=int(os.getenv("METABASE_DATABASE_ID", "2")))
    parser.add_argument("--integrated-name", default="B2 Naver Clip Report")
    parser.add_argument(
        "--mode",
        choices=["selector", "split"],
        default=os.getenv("METABASE_DASHBOARD_MODE", "selector"),
        help="selector: one dashboard with rights-holder UI filter. split: integrated + per-holder dashboards.",
    )
    parser.add_argument(
        "--suffix",
        default=os.getenv("METABASE_DASHBOARD_SUFFIX", ""),
        help="Optional suffix for test runs, e.g. ' 2026-04-30 18:00'.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.email or not args.password:
        print(
            "METABASE_EMAIL and METABASE_PASSWORD are required.\n"
            "Example:\n"
            "$env:METABASE_EMAIL='admin@example.com'\n"
            "$env:METABASE_PASSWORD='your-password'\n"
            "python scripts\\create_metabase_b2_dashboard.py",
            file=sys.stderr,
        )
        return 2

    client = MetabaseClient(args.url, args.email, args.password, args.public_url)
    collection_id = create_collection(client)
    print(f"created collection: {collection_id}")

    enabled_rights_holders = get_enabled_rights_holders(client, args.database_id)
    if not enabled_rights_holders:
        raise RuntimeError(
            "No enabled rights holders found. Check naver_rights_holders.naver_report_enabled."
        )
    print("enabled rights holders: " + ", ".join(enabled_rights_holders))

    default_work_titles = get_default_work_titles_from_supabase_rest(enabled_rights_holders)
    work_titles_by_holder = get_work_titles_by_rights_holder_from_supabase_rest(
        enabled_rights_holders
    )
    if default_work_titles:
        print("default work titles: " + ", ".join(default_work_titles))
    else:
        print("default work titles: none")
    for holder_name, titles in work_titles_by_holder.items():
        print(f"{holder_name} work titles: " + (", ".join(titles) if titles else "none"))

    urls: list[tuple[str, str]] = []
    if args.mode == "selector":
        dashboard_name = f"{args.integrated_name}{args.suffix}"
        dashboard_id = create_selector_dashboard(
            client,
            args.database_id,
            collection_id,
            dashboard_name,
            enabled_rights_holders,
            default_work_titles,
        )
        admin_url = f"{args.url.rstrip('/')}/dashboard/{dashboard_id}"
        urls.append((dashboard_name, admin_url))
        print(f"created dashboard: {dashboard_id} {dashboard_name}")
        try:
            public_url = client.enable_public_sharing(dashboard_id)
            urls.append((f"{dashboard_name} public", public_url))
            print(f"public dashboard URL: {public_url}")
        except Exception as exc:
            print(f"  [warn] could not enable public sharing: {exc}")

        print("\nDashboard URLs:")
        for name, url in urls:
            print(f"- {name}: {url}")
        return 0

    integrated_name = f"{args.integrated_name}{args.suffix}"
    integrated_id = create_report_dashboard(
        client,
        args.database_id,
        collection_id,
        integrated_name,
        default_work_titles,
        holder_name=None,
    )
    integrated_admin_url = f"{args.url.rstrip('/')}/dashboard/{integrated_id}"
    urls.append((integrated_name, integrated_admin_url))
    print(f"created dashboard: {integrated_id} {integrated_name}")

    for holder_name in enabled_rights_holders:
        dashboard_name = f"{args.integrated_name} - {holder_name}{args.suffix}"
        dashboard_id = create_report_dashboard(
            client,
            args.database_id,
            collection_id,
            dashboard_name,
            default_work_titles,
            holder_name=holder_name,
            holder_work_titles=work_titles_by_holder.get(holder_name, []),
        )
        admin_url = f"{args.url.rstrip('/')}/dashboard/{dashboard_id}"
        urls.append((dashboard_name, admin_url))
        print(f"created dashboard: {dashboard_id} {dashboard_name}")

        # Enable public sharing and persist embed URL to Supabase
        try:
            embed_url = client.enable_public_sharing(dashboard_id)
            save_embed_url_to_supabase(holder_name, embed_url)
        except Exception as exc:
            print(f"  [warn] could not enable sharing for {holder_name!r}: {exc}")

    print("\nDashboard admin URLs:")
    for name, url in urls:
        print(f"- {name}: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
