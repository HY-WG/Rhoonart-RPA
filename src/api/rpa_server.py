from __future__ import annotations

import importlib
import json
from datetime import datetime
from typing import Any

import pytz
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.backoffice.app import build_app as build_relief_app
from src.backoffice.dependencies import get_relief_request_service
from src.config import settings
from src.dashboard.app import build_app as build_dashboard_app
from src.dashboard.runner import build_integration_task_service

KST = pytz.timezone("Asia/Seoul")


class GenericTriggerRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


TASK_HANDLERS: dict[str, str] = {
    "A-2": "lambda.a2_work_approval_handler",
    "A-3": "lambda.a3_naver_clip_monthly_handler",
    "B-2": "lambda.b2_weekly_report_handler",
    "C-1": "lambda.c1_lead_filter_handler",
    "C-2": "lambda.c2_cold_email_handler",
    "C-3": "lambda.c3_work_register_handler",
    "C-4": "lambda.c4_coupon_notification_handler",
    "D-3": "lambda.d3_kakao_creator_onboarding_handler",
}


def _check_auth(x_rpa_token: str | None = Header(default=None)) -> None:
    if not settings.X_INTERN_TOKEN:
        return
    if x_rpa_token != settings.X_INTERN_TOKEN:
        raise HTTPException(status_code=401, detail="invalid X-RPA-Token")


def _invoke_lambda(module_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    module = importlib.import_module(module_name)
    return module.handler(payload, None)


def build_app() -> FastAPI:
    app = FastAPI(
        title="Rhoonart RPA Control Server",
        version="0.2.0",
        description=(
            "Unified local control server for legacy trigger endpoints, "
            "integration dashboard, and the D-2 relief-request backoffice."
        ),
    )

    dashboard_service = build_integration_task_service()
    dashboard_app = build_dashboard_app(service=dashboard_service)
    relief_app = build_relief_app(service=get_relief_request_service())

    app.mount("/dashboard", dashboard_app)
    app.mount("/relief", relief_app)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8" />
          <title>Rhoonart RPA Control Server</title>
          <style>
            body { font-family: "Segoe UI", "Apple SD Gothic Neo", sans-serif; margin: 40px; color: #17212b; background: #f7f4ee; }
            .card { max-width: 880px; background: white; border: 1px solid #ddd2c2; border-radius: 16px; padding: 24px; box-shadow: 0 10px 24px rgba(23,33,43,.08); }
            h1 { margin-top: 0; }
            ul { line-height: 1.8; }
            a { color: #1b6b73; text-decoration: none; font-weight: 600; }
          </style>
        </head>
        <body>
          <div class="card">
            <h1>Rhoonart RPA Control Server</h1>
            <p>This server combines the dashboard, legacy trigger APIs, and the D-2 backoffice in one place.</p>
            <ul>
              <li><a href="/dashboard/">Integration Test Dashboard</a></li>
              <li><a href="/docs">Control Server API Docs</a></li>
              <li><a href="/relief/docs">D-2 Backoffice API Docs</a></li>
            </ul>
          </div>
        </body>
        </html>
        """

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "time": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S %Z"),
            "dashboard_repository": settings.INTEGRATION_DASHBOARD_DB_TYPE,
            "auth_required": bool(settings.X_INTERN_TOKEN),
        }

    @app.post("/api/tasks/{task_id}/trigger")
    def trigger_task(
        task_id: str,
        request: GenericTriggerRequest,
        _: None = Depends(_check_auth),
    ) -> dict[str, Any]:
        module_name = TASK_HANDLERS.get(task_id.upper())
        if not module_name:
            raise HTTPException(status_code=404, detail=f"unknown task: {task_id}")
        return _invoke_lambda(module_name, request.payload)

    @app.post("/api/a2/trigger")
    def trigger_a2(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        payload = dict(request.payload)
        event = {
            "body": json.dumps(
                {
                    "type": "event_callback",
                    "event": {
                        "type": "message",
                        "channel": payload.get("slack_channel_id", "C_HTTP_TRIGGER"),
                        "ts": payload.get("slack_message_ts", "manual-0001"),
                        "text": (
                            f'\ucc44\ub110: "{payload.get("channel_name", "Test Channel")}" '
                            f'\uc2e0\uaddc \uc601\uc0c1 \uc0ac\uc6a9 \uc694\uccad\uc774 \uc788\uc2b5\ub2c8\ub2e4.\n'
                            f'{payload.get("work_title", "Test Work")}'
                        ),
                    },
                },
                ensure_ascii=False,
            )
        }
        return _invoke_lambda("lambda.a2_work_approval_handler", event)

    @app.post("/api/a3/trigger")
    def trigger_a3(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.a3_naver_clip_monthly_handler", request.payload)

    @app.post("/api/b2/trigger")
    def trigger_b2(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.b2_weekly_report_handler", request.payload)

    @app.post("/api/c1/trigger")
    def trigger_c1(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.c1_lead_filter_handler", request.payload)

    @app.post("/api/c2/trigger")
    def trigger_c2(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.c2_cold_email_handler", request.payload)

    @app.post("/api/c3/trigger")
    def trigger_c3(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.c3_work_register_handler", request.payload)

    @app.post("/api/c4/trigger")
    def trigger_c4(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.c4_coupon_notification_handler", request.payload)

    @app.post("/api/d3/trigger")
    def trigger_d3(request: GenericTriggerRequest, _: None = Depends(_check_auth)) -> dict[str, Any]:
        return _invoke_lambda("lambda.d3_kakao_creator_onboarding_handler", request.payload)

    return app


app = build_app()


if __name__ == "__main__":
    uvicorn.run("src.api.rpa_server:app", host="127.0.0.1", port=8000, reload=False)
