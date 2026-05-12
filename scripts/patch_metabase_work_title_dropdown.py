from __future__ import annotations

import os
import sys
from typing import Any

from dotenv import load_dotenv

from create_metabase_b2_dashboard import (
    MetabaseClient,
    category_values_config,
    get_default_work_titles_from_supabase_rest,
    get_enabled_rights_holders,
    get_work_titles_by_rights_holder_from_supabase_rest,
)


def _holder_from_dashboard_name(name: str) -> str | None:
    prefix = "B2 Naver Clip Report - "
    if name.startswith(prefix):
        return name[len(prefix) :].strip()
    return None


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


def _titles_for_holder(
    holder_name: str | None,
    titles_by_holder: dict[str, list[str]],
) -> list[str]:
    if not holder_name:
        return []
    direct = titles_by_holder.get(holder_name)
    if direct:
        return direct
    for row_holder, titles in titles_by_holder.items():
        if titles and _holder_name_matches(row_holder, holder_name):
            return titles
    return []


def _update_work_parameter(parameters: list[dict[str, Any]], titles: list[str]) -> bool:
    changed = False
    for parameter in parameters:
        if parameter.get("slug") != "work_title":
            continue
        config = category_values_config(titles)
        next_values = {
            "type": "category",
            "sectionId": "string",
            "values_source_type": "static-list",
            "values_source_config": config,
        }
        for key, value in next_values.items():
            if parameter.get(key) != value:
                parameter[key] = value
                changed = True
        if "isMultiSelect" in parameter:
            parameter.pop("isMultiSelect", None)
            changed = True
    return changed


def _update_card_work_template_tag(client: MetabaseClient, card_id: int) -> bool:
    resp = client.session.get(f"{client.base_url}/api/card/{card_id}", timeout=30)
    client._raise(resp, f"GET /api/card/{card_id} failed")
    card = resp.json()
    dataset_query = card.get("dataset_query") or {}
    changed = False

    stages = dataset_query.get("stages") or []
    for stage in stages:
        tags = stage.get("template-tags") or {}
        tag = tags.get("work_title")
        if tag and tag.get("widget-type") != "category":
            tag["widget-type"] = "category"
            changed = True

    native = dataset_query.get("native") or {}
    tags = native.get("template-tags") or native.get("template_tags") or {}
    tag = tags.get("work_title")
    if tag and tag.get("widget-type") != "category":
        tag["widget-type"] = "category"
        changed = True

    if not changed:
        return False

    client.put(f"/api/card/{card_id}", {"dataset_query": dataset_query})
    return True


def main() -> int:
    load_dotenv(".env")
    base_url = os.getenv("METABASE_URL", "http://localhost:3001")
    email = os.getenv("METABASE_EMAIL")
    password = os.getenv("METABASE_PASSWORD")
    database_id = int(os.getenv("METABASE_DATABASE_ID", "2"))
    if not email or not password:
        print("METABASE_EMAIL and METABASE_PASSWORD are required.", file=sys.stderr)
        return 2

    client = MetabaseClient(base_url, email, password)
    enabled_holders = get_enabled_rights_holders(client, database_id)
    default_titles = get_default_work_titles_from_supabase_rest(enabled_holders)
    titles_by_holder = get_work_titles_by_rights_holder_from_supabase_rest(enabled_holders)

    resp = client.session.get(f"{client.base_url}/api/dashboard", timeout=30)
    client._raise(resp, "GET /api/dashboard failed")
    dashboards = [
        item
        for item in resp.json()
        if str(item.get("name") or "").startswith("B2 Naver Clip Report")
        and not item.get("archived")
    ]

    for dashboard in dashboards:
        dashboard_id = int(dashboard["id"])
        name = str(dashboard.get("name") or "")
        holder_name = _holder_from_dashboard_name(name)
        titles = _titles_for_holder(holder_name, titles_by_holder) if holder_name else default_titles
        if not titles:
            print(f"skip dashboard {dashboard_id} {name}: no work titles")
            continue

        detail_resp = client.session.get(
            f"{client.base_url}/api/dashboard/{dashboard_id}",
            timeout=30,
        )
        client._raise(detail_resp, f"GET /api/dashboard/{dashboard_id} failed")
        detail = detail_resp.json()
        parameters = detail.get("parameters") or []
        if _update_work_parameter(parameters, titles):
            client.put(f"/api/dashboard/{dashboard_id}", {"parameters": parameters})
            print(f"patched dashboard parameter: {dashboard_id} {name}")
        else:
            print(f"dashboard parameter already ok: {dashboard_id} {name}")

        patched_cards = 0
        for dashcard in detail.get("dashcards") or detail.get("ordered_cards") or []:
            card_id = dashcard.get("card_id") or (dashcard.get("card") or {}).get("id")
            if card_id and _update_card_work_template_tag(client, int(card_id)):
                patched_cards += 1
        print(f"patched cards: {dashboard_id} {name} count={patched_cards}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
