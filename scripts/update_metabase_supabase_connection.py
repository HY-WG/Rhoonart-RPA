"""Update Metabase database #2 Supabase/Postgres connection password.

Usage:
  python scripts/update_metabase_supabase_connection.py --db-password "<SUPABASE_DB_PASSWORD>"

The Metabase login values are read from .env:
  METABASE_EMAIL
  METABASE_PASSWORD
"""

from __future__ import annotations

import argparse
import os

import requests
from dotenv import load_dotenv


DEFAULT_METABASE_URL = "http://localhost:3000"
DEFAULT_DATABASE_ID = 2


def main() -> int:
    load_dotenv(".env")

    parser = argparse.ArgumentParser(
        description="Update the Supabase/Postgres password stored in Metabase."
    )
    parser.add_argument("--url", default=os.getenv("METABASE_URL", DEFAULT_METABASE_URL))
    parser.add_argument("--database-id", type=int, default=DEFAULT_DATABASE_ID)
    parser.add_argument("--db-password", required=True)
    parser.add_argument(
        "--host",
        default="aws-1-ap-southeast-1.pooler.supabase.com",
        help="Supabase pooler host stored in Metabase.",
    )
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--dbname", default="postgres")
    parser.add_argument("--user", default="postgres.vxbclahogwjkegggdefi")
    args = parser.parse_args()

    email = os.getenv("METABASE_EMAIL")
    password = os.getenv("METABASE_PASSWORD")
    if not email or not password:
        raise RuntimeError("METABASE_EMAIL and METABASE_PASSWORD are required in .env.")

    base_url = args.url.rstrip("/")
    session = requests.Session()
    login_resp = session.post(
        f"{base_url}/api/session",
        json={"username": email, "password": password},
        timeout=30,
    )
    login_resp.raise_for_status()
    session.headers.update({"X-Metabase-Session": login_resp.json()["id"]})

    current_resp = session.get(f"{base_url}/api/database/{args.database_id}", timeout=30)
    current_resp.raise_for_status()
    current = current_resp.json()

    details = dict(current.get("details") or {})
    details.update(
        {
            "host": args.host,
            "port": args.port,
            "dbname": args.dbname,
            "user": args.user,
            "password": args.db_password,
            "ssl": True,
            "ssl-mode": "require",
        }
    )

    payload = {
        "name": current.get("name") or "Roonart-RPA",
        "engine": current.get("engine") or "postgres",
        "details": details,
        "auto_run_queries": current.get("auto_run_queries", True),
        "is_full_sync": current.get("is_full_sync", True),
    }
    update_resp = session.put(
        f"{base_url}/api/database/{args.database_id}",
        json=payload,
        timeout=30,
    )
    update_resp.raise_for_status()

    print(f"Updated Metabase database {args.database_id}: {payload['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
