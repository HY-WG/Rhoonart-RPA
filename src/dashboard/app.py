from __future__ import annotations

import json
from html import escape
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .models import ExecutionMode, IntegrationRun, IntegrationTaskSpec
from .runner import IntegrationTaskService, build_integration_task_service


class RunTaskRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN
    approved: bool = False


def _run_to_dict(run: IntegrationRun) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "task_id": run.task_id,
        "title": run.title,
        "payload": run.payload,
        "status": run.status.value,
        "execution_mode": run.execution_mode.value,
        "requires_approval": run.requires_approval,
        "approved": run.approved,
        "started_at": run.started_at.isoformat(),
        "updated_at": run.updated_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "result": run.result,
        "error": run.error,
        "logs": run.logs,
    }


def _task_to_dict(task: IntegrationTaskSpec) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "default_payload": task.default_payload,
        "targets": task.targets,
        "trigger_mode": task.trigger_mode,
        "requires_approval": task.requires_approval,
        "supports_dry_run": task.supports_dry_run,
        "real_run_warning": task.real_run_warning,
    }


def build_app(service: IntegrationTaskService | None = None) -> FastAPI:
    app = FastAPI(title="Rhoonart Integration Test Dashboard", version="0.2.0")
    task_service = service or build_integration_task_service()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def dashboard_page() -> str:
        return _render_dashboard_html(task_service.list_task_specs())

    @app.get("/api/integration/tasks")
    def list_tasks() -> list[dict[str, Any]]:
        return [_task_to_dict(task) for task in task_service.list_task_specs()]

    @app.get("/api/integration/resources")
    def resource_summary() -> dict[str, Any]:
        return task_service.environment_summary()

    @app.get("/api/integration/runs")
    def list_runs() -> list[dict[str, Any]]:
        return [_run_to_dict(run) for run in task_service.list_runs()]

    @app.get("/api/integration/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = task_service.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return _run_to_dict(run)

    @app.post("/api/integration/tasks/{task_id}/run")
    def start_run(task_id: str, request: RunTaskRequest) -> dict[str, Any]:
        try:
            run = task_service.start_run(
                task_id,
                request.payload,
                execution_mode=request.execution_mode,
                approved=request.approved,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _run_to_dict(run)

    return app


def _render_dashboard_html(tasks: list[IntegrationTaskSpec]) -> str:
    task_cards = []
    for task in tasks:
        warning_html = (
            f'<div class="warning">{escape(task.real_run_warning)}</div>'
            if task.real_run_warning
            else ""
        )
        task_cards.append(
            f"""
            <section class="task-card" data-task-id="{escape(task.task_id)}">
              <div class="task-head">
                <div>
                  <h3>{escape(task.task_id)} - {escape(task.title)}</h3>
                  <p>{escape(task.description)}</p>
                </div>
              </div>
              <div class="meta">
                <span>Targets: {escape(", ".join(task.targets))}</span>
                <span>Trigger: {escape(task.trigger_mode)}</span>
                <span>Approval: {"required" if task.requires_approval else "none"}</span>
              </div>
              {warning_html}
              <textarea class="payload" data-task-id="{escape(task.task_id)}">{escape(json.dumps(task.default_payload, ensure_ascii=False, indent=2))}</textarea>
              <div class="action-row">
                <label class="approval-toggle">
                  <input type="checkbox" class="approval" data-task-id="{escape(task.task_id)}" />
                  real-run approval
                </label>
                <div class="button-group">
                  <button class="run-btn secondary" data-task-id="{escape(task.task_id)}" data-mode="dry_run">Dry Run</button>
                  <button class="run-btn" data-task-id="{escape(task.task_id)}" data-mode="real_run">Real Run</button>
                </div>
              </div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Rhoonart Integration Test Dashboard</title>
  <style>
    :root {{
      --bg: #f4efe8;
      --panel: #fffdf8;
      --ink: #17212b;
      --muted: #6d7a86;
      --line: #dccfbe;
      --accent: #1b6b73;
      --accent-soft: #d7ecee;
      --warn: #a1502f;
      --success: #2b6d47;
      --shadow: 0 12px 32px rgba(35, 34, 29, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top right, rgba(27,107,115,.18), transparent 28%),
        radial-gradient(circle at bottom left, rgba(161,80,47,.16), transparent 24%),
        var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", "Apple SD Gothic Neo", sans-serif;
    }}
    .page {{
      max-width: 1480px;
      margin: 0 auto;
      padding: 28px 20px 36px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(255,253,248,.94), rgba(242,245,240,.88));
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      border-radius: 24px;
      padding: 24px;
      margin-bottom: 22px;
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 32px;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 1.4fr .9fr;
      gap: 18px;
    }}
    .left, .right {{
      display: grid;
      gap: 18px;
      align-content: start;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 18px;
    }}
    .panel h2 {{
      margin: 0 0 12px;
      font-size: 20px;
    }}
    .task-grid {{
      display: grid;
      gap: 14px;
    }}
    .task-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,.88), rgba(251,248,242,.96));
    }}
    .task-head {{
      display: flex;
      gap: 12px;
      justify-content: space-between;
      align-items: start;
    }}
    .task-head h3 {{
      margin: 0 0 6px;
      font-size: 18px;
    }}
    .task-head p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 12px 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .warning {{
      border-left: 4px solid var(--warn);
      background: #fbefe8;
      color: var(--warn);
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 13px;
      line-height: 1.5;
      margin-bottom: 12px;
    }}
    .payload {{
      width: 100%;
      min-height: 154px;
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 12px;
      resize: vertical;
      background: #fff;
      color: var(--ink);
      font: 13px/1.5 Consolas, monospace;
    }}
    .action-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-top: 12px;
      flex-wrap: wrap;
    }}
    .button-group {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .approval-toggle {{
      color: var(--muted);
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .run-btn, .refresh-btn {{
      border: 0;
      background: var(--accent);
      color: white;
      padding: 10px 16px;
      border-radius: 999px;
      cursor: pointer;
      font-weight: 600;
    }}
    .run-btn.secondary {{
      background: #496976;
    }}
    .run-btn:hover, .refresh-btn:hover {{
      filter: brightness(1.05);
    }}
    .status-list {{
      display: grid;
      gap: 10px;
    }}
    .status-item {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: #fff;
      cursor: pointer;
    }}
    .status-item strong {{
      display: block;
      margin-bottom: 4px;
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
      background: var(--accent-soft);
      color: var(--accent);
    }}
    .badge.failed {{
      background: #f7ddcf;
      color: var(--warn);
    }}
    .badge.succeeded {{
      background: #d9efdf;
      color: var(--success);
    }}
    .badge.running, .badge.queued {{
      background: #dbe8f7;
      color: #245b9c;
    }}
    .log-box {{
      min-height: 280px;
      max-height: 520px;
      overflow: auto;
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 12px;
      background: #171d23;
      color: #d9e4ef;
      font: 13px/1.6 Consolas, monospace;
      white-space: pre-wrap;
    }}
    .resource-box {{
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 12px;
      background: #fff;
      font: 13px/1.6 Consolas, monospace;
      white-space: pre-wrap;
      overflow: auto;
      max-height: 260px;
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .hint {{
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 1080px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>Integration Test Dashboard</h1>
      <p>
        Control A-2, A-3, B-2, C-1, C-2, C-3, C-4, D-2, and D-3 from the browser.
        Every task supports a run record with logs, result JSON, and execution mode tracking.
      </p>
    </section>

    <div class="layout">
      <div class="left">
        <section class="panel">
          <h2>Task Controls</h2>
          <div class="task-grid">
            {"".join(task_cards)}
          </div>
        </section>
      </div>

      <div class="right">
        <section class="panel">
          <div class="toolbar">
            <h2>Run Status</h2>
            <button class="refresh-btn" id="refresh-runs">Refresh</button>
          </div>
          <div class="status-list" id="run-list"></div>
        </section>

        <section class="panel">
          <h2>Selected Run Logs</h2>
          <div class="hint">Check Google Sheets updates, email delivery, Slack notifications, and Supabase persistence through logs and result JSON.</div>
          <div class="log-box" id="run-detail">Select a run to inspect logs and result JSON.</div>
        </section>

        <section class="panel">
          <h2>Environment / Target Summary</h2>
          <div class="resource-box" id="resource-summary">Loading...</div>
        </section>
      </div>
    </div>
  </div>

  <script>
    let selectedRunId = null;

    function formatBadge(status) {{
      return `<span class="badge ${{status}}">${{status}}</span>`;
    }}

    async function loadResources() {{
      const res = await fetch('api/integration/resources');
      const data = await res.json();
      document.getElementById('resource-summary').textContent = JSON.stringify(data, null, 2);
    }}

    async function loadRuns() {{
      const res = await fetch('api/integration/runs');
      const runs = await res.json();
      const root = document.getElementById('run-list');
      root.innerHTML = '';
      for (const run of runs) {{
        const div = document.createElement('div');
        div.className = 'status-item';
        div.innerHTML = `
          <strong>${{run.task_id}} - ${{run.title}}</strong>
          <div>${{formatBadge(run.status)}}</div>
          <div class="hint">${{run.execution_mode}}</div>
          <div class="hint">${{run.run_id}}</div>
          <div class="hint">started: ${{run.started_at}}</div>
        `;
        div.onclick = () => {{
          selectedRunId = run.run_id;
          loadRun(run.run_id);
        }};
        root.appendChild(div);
      }}
      if (selectedRunId) {{
        await loadRun(selectedRunId);
      }}
    }}

    async function loadRun(runId) {{
      const res = await fetch(`api/integration/runs/${{runId}}`);
      if (!res.ok) {{
        return;
      }}
      const run = await res.json();
      document.getElementById('run-detail').textContent = JSON.stringify(run, null, 2);
    }}

    async function startRun(taskId, executionMode) {{
      const textarea = document.querySelector(`textarea[data-task-id="${{taskId}}"]`);
      const approval = document.querySelector(`input.approval[data-task-id="${{taskId}}"]`);
      let payload = {{}};
      try {{
        payload = JSON.parse(textarea.value || '{{}}');
      }} catch (error) {{
        alert(`Invalid JSON for ${{taskId}}: ${{error.message}}`);
        return;
      }}
      const res = await fetch(`api/integration/tasks/${{taskId}}/run`, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          payload,
          execution_mode: executionMode,
          approved: approval ? approval.checked : false,
        }}),
      }});
      const body = await res.json();
      if (!res.ok) {{
        alert(body.detail || 'Failed to start task');
        return;
      }}
      selectedRunId = body.run_id;
      await loadRuns();
    }}

    document.querySelectorAll('.run-btn').forEach((button) => {{
      button.addEventListener('click', () => startRun(button.dataset.taskId, button.dataset.mode));
    }});
    document.getElementById('refresh-runs').addEventListener('click', loadRuns);

    loadResources();
    loadRuns();
    setInterval(loadRuns, 3000);
  </script>
</body>
</html>"""


app = build_app()
