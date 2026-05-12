from __future__ import annotations

import argparse
import os
from urllib.parse import quote, urlparse

import requests
from dotenv import load_dotenv


def public_path(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.path.startswith("/public/dashboard/"):
        raise ValueError(f"Not a Metabase public dashboard URL: {url}")
    return parsed.path


def main() -> int:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(
        description="Rewrite naver_rights_holders.metabase_embed_url to an external Metabase base URL."
    )
    parser.add_argument(
        "--public-url",
        default=os.getenv("METABASE_PUBLIC_URL"),
        required=not bool(os.getenv("METABASE_PUBLIC_URL")),
        help="Externally reachable Metabase base URL, e.g. http://192.168.0.202:3001",
    )
    args = parser.parse_args()

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")

    base_url = supabase_url.rstrip("/")
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    public_base = args.public_url.rstrip("/")

    resp = requests.get(
        f"{base_url}/rest/v1/naver_rights_holders",
        headers=headers,
        params={
            "select": "rights_holder_name,metabase_embed_url",
            "metabase_embed_url": "not.is.null",
            "order": "rights_holder_name.asc",
        },
        timeout=30,
    )
    resp.raise_for_status()

    seen: set[str] = set()
    for row in resp.json():
        rights_holder_name = str(row.get("rights_holder_name") or "").strip()
        embed_url = str(row.get("metabase_embed_url") or "").strip()
        if not rights_holder_name or not embed_url or rights_holder_name in seen:
            continue
        seen.add(rights_holder_name)
        new_url = f"{public_base}{public_path(embed_url)}"
        patch_resp = requests.patch(
            f"{base_url}/rest/v1/naver_rights_holders"
            f"?rights_holder_name=eq.{quote(rights_holder_name)}",
            headers=headers,
            json={"metabase_embed_url": new_url},
            timeout=30,
        )
        patch_resp.raise_for_status()
        print(f"{rights_holder_name}: {new_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
