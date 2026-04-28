# Integration Test Dashboard

## Goal

Provide a browser-operated control plane for the following automation modules:

- A-2
- A-3
- B-2
- C-1
- C-2
- C-3
- C-4
- D-2
- D-3

Each task can be triggered from the browser with a JSON payload editor, and each execution is tracked with:

- run status
- structured result payload
- runtime logs
- target system summary

## Run locally

```bash
uvicorn src.dashboard.app:app --port 8010 --reload
```

or

```bash
python -m src.api.integration_dashboard_server
```

Open:

- `http://localhost:8010/`

## Architecture

The dashboard is intentionally split into layers:

- `src/dashboard/models.py`
  - execution metadata and task specs
- `src/dashboard/repository.py`
  - repository contract for run persistence
- `src/dashboard/in_memory_repository.py`
  - current run store implementation
- `src/dashboard/runner.py`
  - task registry, async execution, adapter normalization
- `src/dashboard/app.py`
  - FastAPI routes and browser UI

This allows the run log store to move from in-memory to Supabase without changing the browser code.

## Current visibility model

The dashboard surfaces three types of visibility:

- task targets from configuration
- execution log trail captured by the runner
- normalized handler result payloads

For tasks that write to Google Sheets or send outbound messages, the handler result and logs are meant to show the immediate outcome, while the linked Sheets/mail systems remain the source of truth.

## Future extensions

- Supabase-backed run repository
- Google Sheets delta inspection after each run
- richer outbound delivery status and retry state
- saved payload presets per task
- approval workflow gates before production-side actions
