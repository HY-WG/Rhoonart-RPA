from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from src.dashboard.app import build_app
from src.dashboard.models import ExecutionMode, IntegrationRunStatus, IntegrationTaskSpec
from src.dashboard.runner import IntegrationTaskService


def _wait_for_completion(service: IntegrationTaskService, run_id: str, timeout: float = 2.0):
    started = time.time()
    while time.time() - started < timeout:
        run = service.get_run(run_id)
        if run and run.status in (IntegrationRunStatus.SUCCEEDED, IntegrationRunStatus.FAILED):
            return run
        time.sleep(0.05)
    raise AssertionError(f"run did not complete in time: {run_id}")


def test_runner_executes_registered_task_and_stores_logs() -> None:
    service = IntegrationTaskService(executor=ThreadPoolExecutor(max_workers=1))
    service._registry = {
        "X-1": (
            IntegrationTaskSpec(
                task_id="X-1",
                title="Example Task",
                description="Example adapter",
                default_payload={"value": 1},
            ),
            lambda run, log: (log("adapter called"), {"echo": run.payload})[1],
        )
    }

    run = service.start_run("X-1", {"value": 99}, execution_mode=ExecutionMode.DRY_RUN)
    completed = _wait_for_completion(service, run.run_id)

    assert completed.status == IntegrationRunStatus.SUCCEEDED
    assert completed.execution_mode == ExecutionMode.DRY_RUN
    assert completed.result == {"echo": {"value": 99}}
    assert any("adapter called" in message for message in completed.logs)


def test_real_run_requires_approval_when_task_demands_it() -> None:
    service = IntegrationTaskService(executor=ThreadPoolExecutor(max_workers=1))
    service._registry = {
        "X-APPROVAL": (
            IntegrationTaskSpec(
                task_id="X-APPROVAL",
                title="Approval Task",
                description="Needs approval",
                default_payload={},
                requires_approval=True,
            ),
            lambda run, log: {"ok": True},
        )
    }

    try:
        service.start_run(
            "X-APPROVAL",
            {},
            execution_mode=ExecutionMode.REAL_RUN,
            approved=False,
        )
    except PermissionError as exc:
        assert "requires approval" in str(exc)
    else:
        raise AssertionError("expected PermissionError")


def test_dashboard_routes_expose_task_and_run_state() -> None:
    service = IntegrationTaskService(executor=ThreadPoolExecutor(max_workers=1))
    service._registry = {
        "X-2": (
            IntegrationTaskSpec(
                task_id="X-2",
                title="Route Example",
                description="Route adapter",
                default_payload={"sample": True},
            ),
            lambda run, log: {"ok": True, "payload": run.payload},
        )
    }
    app = build_app(service=service)
    client = TestClient(app)

    tasks_response = client.get("/api/integration/tasks")
    assert tasks_response.status_code == 200
    assert tasks_response.json()[0]["task_id"] == "X-2"

    run_response = client.post(
        "/api/integration/tasks/X-2/run",
        json={
            "payload": {"sample": False},
            "execution_mode": "dry_run",
            "approved": False,
        },
    )
    assert run_response.status_code == 200

    run_id = run_response.json()["run_id"]
    completed = _wait_for_completion(service, run_id)
    detail_response = client.get(f"/api/integration/runs/{run_id}")

    assert completed.status == IntegrationRunStatus.SUCCEEDED
    assert detail_response.status_code == 200
    assert detail_response.json()["execution_mode"] == "dry_run"
    assert detail_response.json()["result"]["ok"] is True

    page_response = client.get("/")
    assert page_response.status_code == 200
    assert "dashboard.js" in page_response.text

    asset_response = client.get("/assets/dashboard.js")
    assert asset_response.status_code == 200
    assert "내 채널" in asset_response.text


def test_dashboard_b2_task_exposes_no_mail_measurement_defaults() -> None:
    service = IntegrationTaskService(executor=ThreadPoolExecutor(max_workers=1))
    b2_spec = next(spec for spec in service.list_task_specs() if spec.task_id == "B-2")

    assert b2_spec.default_payload["send_notifications"] is False
    assert "send_notifications=false" in b2_spec.real_run_warning

    app = build_app(service=service)
    client = TestClient(app)

    tasks_response = client.get("/api/integration/tasks")
    assert tasks_response.status_code == 200
    b2_payload = next(task for task in tasks_response.json() if task["task_id"] == "B-2")
    assert b2_payload["default_payload"]["send_notifications"] is False

    asset_response = client.get("/assets/dashboard.js")
    assert asset_response.status_code == 200
    assert "crawl_seconds" in asset_response.text
    assert "elapsed_seconds" in asset_response.text


def test_runner_marks_business_failure_as_failed() -> None:
    service = IntegrationTaskService(executor=ThreadPoolExecutor(max_workers=1))
    service._registry = {
        "X-BIZ-FAIL": (
            IntegrationTaskSpec(
                task_id="X-BIZ-FAIL",
                title="Business Failure",
                description="Returns success=false",
                default_payload={},
            ),
            lambda run, log: {"success": False, "message": "business failed"},
        )
    }

    run = service.start_run("X-BIZ-FAIL", {}, execution_mode=ExecutionMode.DRY_RUN)
    completed = _wait_for_completion(service, run.run_id)

    assert completed.status == IntegrationRunStatus.FAILED
    assert completed.error == "business failed"
