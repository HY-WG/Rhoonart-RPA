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
    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
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


def make_context(default_work_titles: list[str]) -> DashboardContext:
    today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
    work_title_default: str | list[str] | None = None
    if len(default_work_titles) == 1:
        work_title_default = default_work_titles[0]
    elif len(default_work_titles) > 1:
        work_title_default = default_work_titles

    param_ids = {
        "start_date": str(uuid.uuid4()),
        "end_date": str(uuid.uuid4()),
        "work_title": str(uuid.uuid4()),
        "channel_name": str(uuid.uuid4()),
    }
    parameters = [
        {
            "id": param_ids["start_date"],
            "name": LABEL_START_DATE,
            "slug": "start_date",
            "type": "date/single",
            "sectionId": "date",
            "default": today,
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
            "required": False,
        },
        "channel_name": {
            "id": str(uuid.uuid4()),
            "name": "channel_name",
            "display-name": LABEL_CHANNEL_NAME,
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


def base_filter(enabled_rights_holders: list[str], holder_name: str | None = None) -> str:
    holder_clause = rights_holder_match_clause(
        [holder_name] if holder_name else enabled_rights_holders
    )

    return f"""
from public.v_b2_clip_reports_daily_history h
where h.checked_date_kst::date >= coalesce(
  [[{{{{start_date}}}}::date,]]
  current_date
)
and h.checked_date_kst::date <= coalesce(
  [[{{{{end_date}}}}::date,]]
  current_date
)
[[and h.work_title = {{{{work_title}}}}]]
[[and h.channel_name = {{{{channel_name}}}}]]
{holder_clause}
"""


def build_cards(enabled_rights_holders: list[str], holder_name: str | None = None) -> list[CardSpec]:
    filter_sql = base_filter(enabled_rights_holders, holder_name)
    prefix = f"{holder_name} " if holder_name else ""
    return [
        CardSpec(
            name=f"{prefix}{LABEL_VIEW_COUNT}",
            display="scalar",
            row=0,
            col=0,
            size_x=6,
            size_y=4,
            query=f"""
select coalesce(sum(h.view_count), 0) as "{LABEL_VIEW_COUNT}"
{filter_sql}
""",
        ),
        CardSpec(
            name=f"{prefix}{LABEL_VIDEO_COUNT}",
            display="scalar",
            row=0,
            col=6,
            size_x=6,
            size_y=4,
            query=f"""
select count(distinct h.video_url) as "{LABEL_VIDEO_COUNT}"
{filter_sql}
""",
        ),
        CardSpec(
            name=f"{prefix}{LABEL_WORK_COUNT}",
            display="scalar",
            row=0,
            col=12,
            size_x=6,
            size_y=4,
            query=f"""
select count(distinct h.work_title) as "{LABEL_WORK_COUNT}"
{filter_sql}
""",
        ),
        CardSpec(
            name=f"{prefix}{LABEL_CHANNEL_COUNT}",
            display="scalar",
            row=0,
            col=18,
            size_x=6,
            size_y=4,
            query=f"""
select count(distinct h.channel_name) as "{LABEL_CHANNEL_COUNT}"
{filter_sql}
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
select
  h.channel_name as "{LABEL_CHANNEL_NAME}",
  sum(h.view_count) as "{LABEL_VIEW_COUNT}",
  count(distinct h.video_url) as "{LABEL_VIDEO_COUNT}"
{filter_sql}
group by h.channel_name
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
select
  h.checked_date_kst::date as "{LABEL_PERIOD}",
  sum(h.view_count) as "{LABEL_VIEW_COUNT}",
  count(distinct h.video_url) as "{LABEL_VIDEO_COUNT}"
{filter_sql}
group by h.checked_date_kst::date
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
select
  h.checked_date_kst::date as "{LABEL_PERIOD}",
  h.work_title as "{LABEL_WORK_TITLE}",
  h.channel_name as "{LABEL_CHANNEL_NAME}",
  h.clip_title as "{LABEL_TITLE}",
  h.video_url as "{LABEL_VIDEO_URL}",
  h.uploaded_at as "{LABEL_UPLOADED_AT}",
  h.view_count as "{LABEL_VIEW_COUNT}",
  h.rights_holder_name as "{LABEL_RIGHTS_HOLDER}",
  h.identifier as "identifier"
{filter_sql}
order by "{LABEL_PERIOD}" desc, "{LABEL_VIEW_COUNT}" desc, "{LABEL_WORK_TITLE}" asc, "{LABEL_CHANNEL_NAME}" asc
limit 1000
""",
        ),
    ]


def get_enabled_rights_holders(client: MetabaseClient, database_id: int) -> list[str]:
    try:
        rows = client.query_native(
            database_id,
            """
select distinct rights_holder_name
from public.b2_rights_holders
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
        f"{supabase_url.rstrip('/')}/rest/v1/b2_rights_holders",
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

    # Preferred source: content catalog rows explicitly enabled for Naver reporting.
    catalog_resp = requests.get(
        f"{base_url}/rest/v1/b2_content_catalog",
        headers=headers,
        params={
            "select": "content_name",
            "naver_report_enabled": "eq.true",
            "order": "content_name.asc",
        },
        timeout=30,
    )
    if catalog_resp.ok:
        titles = _distinct_non_empty(row.get("content_name") for row in catalog_resp.json())
        if titles:
            return titles

    # Fallback until b2_content_catalog.naver_report_enabled is applied:
    # use work titles that currently exist for enabled rights holders.
    if not enabled_rights_holders:
        return []
    history_resp = requests.get(
        f"{base_url}/rest/v1/v_b2_clip_reports_daily_history",
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
    return [
        {
            "parameter_id": context.param_ids[tag],
            "card_id": card_id,
            "target": ["variable", ["template-tag", tag]],
        }
        for tag in ["start_date", "end_date", "work_title", "channel_name"]
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
) -> int:
    context = make_context(default_work_titles)
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create integrated and rights-holder B2 Naver Clip Report dashboards."
    )
    parser.add_argument("--url", default=os.getenv("METABASE_URL", "http://localhost:3001"))
    parser.add_argument("--email", default=os.getenv("METABASE_EMAIL"))
    parser.add_argument("--password", default=os.getenv("METABASE_PASSWORD"))
    parser.add_argument("--database-id", type=int, default=int(os.getenv("METABASE_DATABASE_ID", "2")))
    parser.add_argument("--integrated-name", default="B2 Naver Clip Report")
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

    client = MetabaseClient(args.url, args.email, args.password)
    collection_id = create_collection(client)
    print(f"created collection: {collection_id}")

    enabled_rights_holders = get_enabled_rights_holders(client, args.database_id)
    if not enabled_rights_holders:
        raise RuntimeError(
            "No enabled rights holders found. Check b2_rights_holders.naver_report_enabled."
        )
    print("enabled rights holders: " + ", ".join(enabled_rights_holders))

    default_work_titles = get_default_work_titles_from_supabase_rest(enabled_rights_holders)
    if default_work_titles:
        print("default work titles: " + ", ".join(default_work_titles))
    else:
        print("default work titles: none")

    urls: list[tuple[str, str]] = []
    integrated_name = f"{args.integrated_name}{args.suffix}"
    integrated_id = create_report_dashboard(
        client,
        args.database_id,
        collection_id,
        integrated_name,
        default_work_titles,
        holder_name=None,
    )
    urls.append((integrated_name, f"{args.url.rstrip('/')}/dashboard/{integrated_id}"))
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
        )
        urls.append((dashboard_name, f"{args.url.rstrip('/')}/dashboard/{dashboard_id}"))
        print(f"created dashboard: {dashboard_id} {dashboard_name}")

    print("\nDashboard URLs:")
    for name, url in urls:
        print(f"- {name}: {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
