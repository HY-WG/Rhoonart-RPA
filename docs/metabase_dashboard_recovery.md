# Metabase Dashboard Recovery

This note documents how to recreate the Naver Clip Metabase dashboards when a
local Metabase instance is reset.

## Current Architecture

The frontend does not read Metabase URLs directly from `.env`.

The flow is:

1. `scripts/create_metabase_b2_dashboard.py` creates Metabase collections,
   dashboards, cards, filters, and public dashboard URLs.
2. For per-rights-holder dashboards, the script saves each public URL to
   Supabase column `naver_rights_holders.metabase_embed_url`.
3. The backend endpoint `GET /api/admin/reports/metabase` reads
   `naver_rights_holders.metabase_embed_url`.
4. The frontend page fetches that backend API and renders the selected URL in an
   iframe.

Important files:

- Dashboard generator: `scripts/create_metabase_b2_dashboard.py`
- Work-title dropdown patcher: `scripts/patch_metabase_work_title_dropdown.py`
- Public URL host/port rewriter: `scripts/update_metabase_public_urls.py`
- Frontend page: `web/app/admin/reports/naver-clip/page.tsx`
- Frontend API function: `web/lib/api.ts`
- Frontend types: `web/lib/types.ts`
- Backend endpoint: `src/api/rpa_server.py`
- Supabase URL column migration:
  `migrations/011_naver_rights_holders_metabase_url.sql`
- Supabase repository method:
  `src/core/repositories/supabase_b2_repository.py`

## Dashboard Shape

`scripts/create_metabase_b2_dashboard.py` defines the dashboard layout.

Main functions:

- `make_context`: dashboard filters/parameters
- `build_cards`: card SQL, visualization type, and grid layout
- `create_collection`: Metabase collection
- `create_card`: Metabase question/card
- `create_dashboard`: Metabase dashboard
- `add_cards_to_dashboard`: dashboard card placement

The generated cards are:

- View count
- Video count
- Work count
- Channel count
- View/video count by channel
- Daily view trend
- Video-level detail table

The dashboard filters include:

- start date
- end date
- rights holder
- work title
- channel name

## Recreate Dashboards

Run these commands from the repository root:

```powershell
cd C:\Users\mung9\IdeaProjects\rhoonart-rpa
```

Make sure Metabase is running on port `3000`:

```powershell
wsl docker start metabase
wsl docker logs -f metabase
```

Wait until the logs show:

```text
Metabase Initialization COMPLETE
```

Create the dashboards:

```powershell
python scripts\create_metabase_b2_dashboard.py `
  --url http://localhost:3000 `
  --public-url http://localhost:3000 `
  --database-id 2 `
  --mode split
```

Why `--mode split`:

- It creates one integrated dashboard.
- It creates one dashboard per enabled rights holder.
- It enables public sharing for each rights-holder dashboard.
- It saves each public dashboard URL to
  `naver_rights_holders.metabase_embed_url`, which is what the frontend uses.

Patch the work-title dropdown behavior:

```powershell
$env:METABASE_URL='http://localhost:3000'
$env:METABASE_DATABASE_ID='2'
python scripts\patch_metabase_work_title_dropdown.py
```

## Verify Saved Frontend URLs

Check the Supabase URLs that the frontend will receive:

```powershell
@'
from dotenv import load_dotenv
import os, requests

load_dotenv(".env")
base = os.getenv("SUPABASE_URL").rstrip("/")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
resp = requests.get(
    f"{base}/rest/v1/naver_rights_holders",
    headers={"apikey": key, "Authorization": f"Bearer {key}"},
    params={
        "select": "rights_holder_name,naver_report_enabled,metabase_embed_url",
        "naver_report_enabled": "eq.true",
        "order": "rights_holder_name.asc",
    },
    timeout=30,
)
resp.raise_for_status()
for row in resp.json():
    print(row)
'@ | python -
```

The enabled rows should have non-empty `metabase_embed_url` values.

## Frontend URL Flow

The frontend page is:

```text
web/app/admin/reports/naver-clip/page.tsx
```

It calls:

```text
fetchMetabaseReport()
```

defined in:

```text
web/lib/api.ts
```

That function calls the backend endpoint:

```text
GET /api/admin/reports/metabase
```

implemented in:

```text
src/api/rpa_server.py
```

The backend reads:

```text
naver_rights_holders.metabase_embed_url
```

from Supabase and sends it to the frontend as each report's `embed_url`.

## Prevent Future Resets

The local Metabase Docker container should use a persistent volume.

Without a volume, Metabase stores its application database inside the container.
If the container is removed or recreated, collections, dashboards, cards, users,
and settings can disappear.

Recommended run shape:

```powershell
wsl docker run -d `
  --name metabase `
  -p 3000:3000 `
  -v metabase-data:/metabase-data `
  -e MB_DB_FILE=/metabase-data/metabase.db `
  -e MAX_SESSION_AGE=525600 `
  -e MB_SESSION_COOKIES=false `
  metabase/metabase
```

For an existing non-volume container, back up the DB before replacing it:

```powershell
wsl docker cp metabase:/metabase.db ./metabase-db-backup
```

Then migrate the copied DB into a Docker volume before starting the new
container.

## Useful Checks

Check port `3000`:

```powershell
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
```

Check Metabase container:

```powershell
wsl docker ps -a --filter name=metabase
```

Check whether the container has a volume:

```powershell
wsl docker inspect metabase --format 'Mounts={{json .Mounts}}'
```

If `Mounts=[]`, the container is not using persistent storage.
