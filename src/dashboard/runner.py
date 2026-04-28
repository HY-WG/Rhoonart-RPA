from __future__ import annotations

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from src.backoffice.dependencies import get_relief_request_service
from src.config import settings
from src.core.repositories.supabase_integration_dashboard_repository import (
    SupabaseIntegrationDashboardRepository,
)
from src.handlers.a2_work_approval import parse_slack_message
from src.handlers.c4_coupon_notification import is_coupon_request

from .in_memory_repository import InMemoryIntegrationDashboardRepository
from .models import ExecutionMode, IntegrationRun, IntegrationRunStatus, IntegrationTaskSpec
from .repository import IIntegrationDashboardRepository

Adapter = Callable[[IntegrationRun, Callable[[str], None]], dict[str, Any]]


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict) and "statusCode" in raw and "body" in raw:
        body = raw.get("body")
        if isinstance(body, str):
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw_body": body}
        else:
            parsed = body
        return {
            "statusCode": raw.get("statusCode"),
            "body": parsed,
        }
    if isinstance(raw, dict):
        return raw
    return {"raw_result": str(raw)}


def _preview_only(run: IntegrationRun, note: str) -> dict[str, Any]:
    return {
        "execution_mode": run.execution_mode.value,
        "task_id": run.task_id,
        "preview_only": True,
        "note": note,
        "payload": run.payload,
    }


def _raise_for_error_result(result: dict[str, Any]) -> None:
    status_code = result.get("statusCode")
    if isinstance(status_code, int) and status_code >= 400:
        body = result.get("body")
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(str(body["error"]))
        raise RuntimeError(f"handler returned statusCode={status_code}")
    if result.get("success") is False:
        raise RuntimeError(str(result.get("message") or "task reported success=false"))
    body = result.get("body")
    if isinstance(body, dict) and body.get("success") is False:
        raise RuntimeError(str(body.get("message") or "task body reported success=false"))


def _adapter_a2(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    slack_text = (
        f'\ucc44\ub110: "{run.payload.get("channel_name", "Test Channel")}" '
        f'\uc2e0\uaddc \uc601\uc0c1 \uc0ac\uc6a9 \uc694\uccad\uc774 \uc788\uc2b5\ub2c8\ub2e4.\n'
        f'{run.payload.get("work_title", "Test Work")}'
    )
    if run.execution_mode == ExecutionMode.DRY_RUN:
        channel_name, work_title = parse_slack_message(slack_text)
        log("Validated Slack parsing pattern for A-2 without changing Drive permissions or sending mail.")
        return {
            "execution_mode": run.execution_mode.value,
            "channel_name": channel_name,
            "work_title": work_title,
            "preview_only": True,
        }

    thread_ts = str(run.payload.get("slack_message_ts", "")).strip()
    if not thread_ts or thread_ts.startswith("dashboard-a2-"):
        raise ValueError(
            "A-2 real-run requires a real Slack message ts in payload.slack_message_ts."
        )

    handler = importlib.import_module("lambda.a2_work_approval_handler").handler
    event = {
        "body": json.dumps(
            {
                "type": "event_callback",
                "event": {
                    "type": "message",
                    "channel": run.payload.get("slack_channel_id", "C_HTTP_TRIGGER"),
                    "ts": thread_ts,
                    "text": slack_text,
                },
            },
            ensure_ascii=False,
        )
    }
    log(f"Dispatching real A-2 approval flow through the lambda entrypoint with thread_ts={thread_ts}.")
    return _normalize_result(handler(event, None))


def _adapter_a3(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    handler = importlib.import_module("lambda.a3_naver_clip_monthly_handler").handler
    mode = run.payload.get("mode", "confirm")
    if run.execution_mode == ExecutionMode.DRY_RUN:
        mode = "confirm"
        log("Dry run selected; forcing A-3 into confirm mode.")
    else:
        log(f"Running A-3 in mode={mode}.")
    return _normalize_result(handler({"mode": mode}, None))


def _adapter_b2(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    if run.execution_mode == ExecutionMode.DRY_RUN:
        log("B-2 does not support a side-effect-free dry run yet; returning a preview summary.")
        return _preview_only(run, "B-2 currently requires a real crawl/report cycle for full validation.")

    handler = importlib.import_module("lambda.b2_weekly_report_handler").handler
    log("Running B-2 weekly report in real mode.")
    return _normalize_result(handler({"source": run.payload.get("source", "dashboard")}, None))


def _adapter_c1(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    if run.execution_mode == ExecutionMode.DRY_RUN:
        log("C-1 dry run is a configuration preview because the current handler always writes leads.")
        return _preview_only(run, "C-1 lead discovery still writes to the lead repository when executed.")

    handler = importlib.import_module("lambda.c1_lead_filter_handler").handler
    log("Running C-1 lead discovery in real mode.")
    return _normalize_result(handler(run.payload, None))


def _adapter_c2(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    if run.execution_mode == ExecutionMode.DRY_RUN:
        log("C-2 dry run is limited to payload preview because the current handler sends email.")
        return _preview_only(run, "C-2 currently has no native no-send preview mode.")

    handler = importlib.import_module("lambda.c2_cold_email_handler").handler
    log("Running C-2 cold email flow in real mode.")
    return _normalize_result(handler(run.payload, None))


def _adapter_c3(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    handler = importlib.import_module("lambda.c3_work_register_handler").handler
    payload = dict(run.payload)
    payload["dry_run"] = run.execution_mode == ExecutionMode.DRY_RUN
    log(f"Running C-3 with dry_run={payload['dry_run']}.")
    return _normalize_result(handler(payload, None))


def _adapter_c4(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    if run.execution_mode == ExecutionMode.DRY_RUN:
        is_match = is_coupon_request(run.payload.get("text", ""))
        log("Validated coupon keyword detection without appending sheets rows or sending notifications.")
        return {
            "execution_mode": run.execution_mode.value,
            "preview_only": True,
            "is_coupon_request": is_match,
            "source": run.payload.get("source", "slack"),
        }

    handler = importlib.import_module("lambda.c4_coupon_notification_handler").handler
    log("Running C-4 coupon notification flow in real mode.")
    return _normalize_result(handler(run.payload, None))


def _adapter_d2(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    service = get_relief_request_service()
    items = run.payload.get(
        "items",
        [
            {
                "work_id": "work-1",
                "work_title": "Sample Work",
                "rights_holder_name": "Rights A",
                "channel_folder_name": run.payload.get("requester_channel_name", "Test Channel"),
            }
        ],
    )
    if run.execution_mode == ExecutionMode.DRY_RUN:
        rights_holders = sorted({item["rights_holder_name"] for item in items})
        log("Prepared D-2 preview without persisting requests or sending rights-holder mail.")
        return {
            "execution_mode": run.execution_mode.value,
            "preview_only": True,
            "requester_channel_name": run.payload.get("requester_channel_name", "Test Channel"),
            "requester_email": run.payload.get("requester_email", "creator@example.com"),
            "item_count": len(items),
            "rights_holders": rights_holders,
            "auto_send_mails": bool(run.payload.get("auto_send_mails", False)),
        }

    log("Creating relief request through the D-2 service.")
    request = service.create_request(
        requester_channel_name=run.payload.get("requester_channel_name", "Test Channel"),
        requester_email=run.payload.get("requester_email", "creator@example.com"),
        requester_notes=run.payload.get("requester_notes", "Integration dashboard request"),
        submitted_via=run.payload.get("submitted_via", "dashboard"),
        work_items=items,
    )
    result: dict[str, Any] = {
        "request_id": request.request_id,
        "status": request.status.value,
        "requester_channel_name": request.requester_channel_name,
    }
    if run.payload.get("auto_send_mails"):
        log("auto_send_mails=true, dispatching rights-holder mail.")
        send_result = service.send_rights_holder_mails(request.request_id)
        result["mail_result"] = {
            "attempted": send_result.attempted,
            "sent": send_result.sent,
            "failed": send_result.failed,
            "updated_status": send_result.updated_status.value,
        }
    return result


def _adapter_d3(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    handler = importlib.import_module("lambda.d3_kakao_creator_onboarding_handler").handler
    dry_run = run.execution_mode == ExecutionMode.DRY_RUN
    log(f"Running D-3 with dry_run={dry_run}.")
    return _normalize_result(handler({"dry_run": dry_run}, None))


class IntegrationTaskService:
    def __init__(
        self,
        repo: IIntegrationDashboardRepository | None = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._repo = repo or build_integration_dashboard_repository()
        self._executor = executor or ThreadPoolExecutor(max_workers=4)
        self._registry = self._build_registry()

    def list_task_specs(self) -> list[IntegrationTaskSpec]:
        return [spec for spec, _ in self._registry.values()]

    def list_runs(self, limit: int = 20) -> list[IntegrationRun]:
        return self._repo.list_runs(limit=limit)

    def get_run(self, run_id: str) -> IntegrationRun | None:
        return self._repo.get_run(run_id)

    def start_run(
        self,
        task_id: str,
        payload: dict[str, Any],
        *,
        execution_mode: ExecutionMode,
        approved: bool = False,
    ) -> IntegrationRun:
        if task_id not in self._registry:
            raise ValueError(f"unknown task_id: {task_id}")
        spec, adapter = self._registry[task_id]
        if execution_mode == ExecutionMode.REAL_RUN and spec.requires_approval and not approved:
            raise PermissionError(f"{task_id} requires approval before real execution")
        if execution_mode == ExecutionMode.DRY_RUN and not spec.supports_dry_run:
            raise ValueError(f"{task_id} does not support dry-run")

        now = _now()
        run = IntegrationRun(
            run_id=f"run-{uuid4().hex[:12]}",
            task_id=task_id,
            title=spec.title,
            payload=payload,
            status=IntegrationRunStatus.QUEUED,
            started_at=now,
            updated_at=now,
            execution_mode=execution_mode,
            requires_approval=spec.requires_approval,
            approved=approved,
        )
        self._repo.save_run(run)
        self._executor.submit(self._execute, run.run_id, adapter)
        return run

    def environment_summary(self) -> dict[str, Any]:
        return {
            "google_credentials_file": settings.GOOGLE_CREDENTIALS_FILE,
            "content_sheet_id": settings.CONTENT_SHEET_ID,
            "lead_sheet_id": settings.LEAD_SHEET_ID,
            "log_sheet_id": settings.LOG_SHEET_ID,
            "sender_email": settings.SENDER_EMAIL,
            "slack_error_channel": settings.SLACK_ERROR_CHANNEL,
            "dashboard_repository": settings.INTEGRATION_DASHBOARD_DB_TYPE,
            "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
            "tasks": [
                {
                    "task_id": spec.task_id,
                    "targets": spec.targets,
                    "trigger_mode": spec.trigger_mode,
                    "requires_approval": spec.requires_approval,
                    "supports_dry_run": spec.supports_dry_run,
                }
                for spec in self.list_task_specs()
            ],
        }

    def _execute(self, run_id: str, adapter: Adapter) -> None:
        run = self._repo.get_run(run_id)
        if run is None:
            return
        self._repo.update_run_status(run_id, IntegrationRunStatus.RUNNING)
        self._repo.append_log(
            run_id,
            f"[{run.task_id}] execution started in mode={run.execution_mode.value}",
        )

        def _log(message: str) -> None:
            self._repo.append_log(run_id, message)

        try:
            result = adapter(run, _log)
            _raise_for_error_result(result)
            self._repo.append_log(run_id, f"[{run.task_id}] execution finished successfully")
            self._repo.update_run_status(
                run_id,
                IntegrationRunStatus.SUCCEEDED,
                result=result,
            )
        except Exception as exc:
            self._repo.append_log(run_id, f"[{run.task_id}] execution failed: {exc}")
            self._repo.update_run_status(
                run_id,
                IntegrationRunStatus.FAILED,
                error=str(exc),
            )

    def _build_registry(self) -> dict[str, tuple[IntegrationTaskSpec, Adapter]]:
        return {
            "A-2": (
                IntegrationTaskSpec(
                    task_id="A-2",
                    title="A-2 Work Approval",
                    description="Validate or execute the work-approval flow from a Slack-style request. Real thread reply verification needs an actual Slack message ts.",
                    default_payload={
                        "channel_name": "Test Channel",
                        "work_title": "Test Work",
                        "slack_channel_id": settings.A2_TEST_SLACK_CHANNEL_ID,
                        "slack_message_ts": settings.A2_TEST_SLACK_THREAD_TS or "",
                    },
                    targets=["Google Sheets", "Google Drive", "Email", "Slack"],
                    real_run_warning="Drive permissions and approval email delivery will run for real. For Slack thread reply testing, replace slack_message_ts with a real Slack message ts such as 1777346971.414089.",
                ),
                _adapter_a2,
            ),
            "A-3": (
                IntegrationTaskSpec(
                    task_id="A-3",
                    title="A-3 Naver Clip Monthly",
                    description="Run the monthly confirm or send flow for Naver Clip requests.",
                    default_payload={"mode": "confirm"},
                    targets=["Google Sheets", "Slack", "Email"],
                    real_run_warning="Using send mode will deliver the real monthly attachment email.",
                ),
                _adapter_a3,
            ),
            "B-2": (
                IntegrationTaskSpec(
                    task_id="B-2",
                    title="B-2 Weekly Report",
                    description="Run or preview the weekly performance report workflow.",
                    default_payload={"source": "dashboard"},
                    targets=["Google Sheets", "Email", "Slack"],
                    real_run_warning="Running this task may aggregate data and send weekly reports.",
                ),
                _adapter_b2,
            ),
            "C-1": (
                IntegrationTaskSpec(
                    task_id="C-1",
                    title="C-1 Lead Discovery",
                    description="Control YouTube Shorts lead discovery and sheet upserts.",
                    default_payload={"_trigger_source": "dashboard"},
                    targets=["YouTube API", "Google Sheets", "Slack"],
                    real_run_warning="Running this task performs actual lead upserts into the lead sheet.",
                ),
                _adapter_c1,
            ),
            "C-2": (
                IntegrationTaskSpec(
                    task_id="C-2",
                    title="C-2 Cold Email",
                    description="Control the filtered lead cold-email workflow.",
                    default_payload={"batch_size": 5, "min_monthly_views": 0},
                    targets=["Google Sheets", "Email", "Slack"],
                    requires_approval=True,
                    real_run_warning="Running this task sends real outbound cold email.",
                ),
                _adapter_c2,
            ),
            "C-3": (
                IntegrationTaskSpec(
                    task_id="C-3",
                    title="C-3 Work Registration",
                    description="Control the work registration flow across Admin API and Notion.",
                    default_payload={
                        "work_title": "Test Work",
                        "rights_holder_name": "Test Rights Holder",
                        "release_year": 2025,
                        "description": "Integration dashboard registration test",
                        "director": "Test Director",
                        "cast": "Actor A, Actor B",
                        "genre": "Drama",
                        "video_type": "Drama",
                        "country": "Korea",
                        "platforms": ["wavve"],
                    },
                    targets=["Admin API", "Notion", "Slack"],
                    requires_approval=True,
                    real_run_warning="Running this task may create live work metadata and guidelines.",
                ),
                _adapter_c3,
            ),
            "C-4": (
                IntegrationTaskSpec(
                    task_id="C-4",
                    title="C-4 Coupon Notification",
                    description="Control the coupon notification flow from Slack or completion events.",
                    default_payload={
                        "source": "slack",
                        "creator_name": "Test Creator",
                        "text": "\uc218\uc775 100% \ucfe0\ud3f0 \uc694\uccad\ud569\ub2c8\ub2e4.",
                    },
                    targets=["Google Sheets", "Slack", "Kakao (stub)"],
                    real_run_warning="Running this task writes the coupon sheet row and sends a Slack DM.",
                ),
                _adapter_c4,
            ),
            "D-2": (
                IntegrationTaskSpec(
                    task_id="D-2",
                    title="D-2 Relief Request Backoffice",
                    description="Preview or execute the relief-request creation and rights-holder mail flow.",
                    default_payload={
                        "requester_channel_name": "Test Channel",
                        "requester_email": "creator@example.com",
                        "requester_notes": "Integration dashboard relief request",
                        "auto_send_mails": False,
                        "items": [
                            {
                                "work_id": "work-1",
                                "work_title": "Sample Work",
                                "rights_holder_name": "Rights A",
                                "channel_folder_name": "Test Channel",
                            }
                        ],
                    },
                    targets=["Relief Request Service", "Email", "Slack"],
                    requires_approval=True,
                    real_run_warning="If auto_send_mails=true, rights-holder email will be delivered for real.",
                ),
                _adapter_d2,
            ),
            "D-3": (
                IntegrationTaskSpec(
                    task_id="D-3",
                    title="D-3 Kakao Creator Onboarding",
                    description="Control the Google Form to final-sheet onboarding workflow.",
                    default_payload={},
                    targets=["Google Sheets", "Drive"],
                ),
                _adapter_d3,
            ),
        }


def build_integration_dashboard_repository() -> IIntegrationDashboardRepository:
    if (
        settings.INTEGRATION_DASHBOARD_DB_TYPE == "supabase"
        and settings.SUPABASE_URL
        and settings.SUPABASE_KEY
    ):
        return SupabaseIntegrationDashboardRepository(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_KEY,
        )
    return InMemoryIntegrationDashboardRepository()


def build_integration_task_service() -> IntegrationTaskService:
    return IntegrationTaskService()
