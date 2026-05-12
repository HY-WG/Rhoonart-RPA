"""Unit tests for ITaskHandler implementations and TASK_REGISTRY.

These tests are fully isolated — no network, no Supabase, no Lambda invocations.
The ``invoker`` callable is always replaced with a stub that returns a fixed dict.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.core.interfaces.task_handler import ITaskHandler, TaskMeta
from src.tasks.registry import TASK_REGISTRY


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stub_invoker(module_name: str, event: dict[str, Any]) -> dict[str, Any]:
    """Fake invoker: records the call and returns a minimal success dict."""
    return {"status": "ok", "invoked": module_name, "event": event}


# ── Registry tests ────────────────────────────────────────────────────────────

class TestTaskRegistry:
    EXPECTED_IDS = {"A-2", "A-3", "B-2", "C-1", "C-2", "C-3", "C-4", "D-3"}

    def test_all_expected_task_ids_registered(self):
        assert set(TASK_REGISTRY.keys()) == self.EXPECTED_IDS

    def test_all_handlers_implement_interface(self):
        for task_id, handler in TASK_REGISTRY.items():
            assert isinstance(handler, ITaskHandler), f"{task_id} is not ITaskHandler"

    def test_all_meta_task_ids_match_registry_keys(self):
        for key, handler in TASK_REGISTRY.items():
            assert handler.meta.task_id == key, (
                f"Registry key {key!r} does not match meta.task_id {handler.meta.task_id!r}"
            )

    def test_all_lambda_modules_start_with_lambda_prefix(self):
        for handler in TASK_REGISTRY.values():
            assert handler.meta.lambda_module.startswith("lambda."), (
                f"{handler.meta.task_id}: unexpected module {handler.meta.lambda_module!r}"
            )

    def test_meta_is_immutable(self):
        """TaskMeta is a frozen dataclass — attributes must not be assignable."""
        meta = TaskMeta("X-1", "Test", "lambda.test")
        with pytest.raises((AttributeError, TypeError)):
            meta.task_id = "Y-2"  # type: ignore[misc]


# ── Default behaviour (passthrough handler) ────────────────────────────────────

class TestITaskHandlerDefaults:
    """Verify base-class defaults using a minimal concrete subclass."""

    class _PassthroughHandler(ITaskHandler):
        @property
        def meta(self) -> TaskMeta:
            return TaskMeta("T-1", "테스트", "lambda.test_handler")

    def setup_method(self):
        self.handler = self._PassthroughHandler()

    def test_build_event_passthrough(self):
        payload = {"key": "value"}
        assert self.handler.build_event(payload) is payload

    def test_post_invoke_passthrough(self):
        result = {"status": "ok"}
        assert self.handler.post_invoke(result, {}) is result

    def test_execute_calls_invoker_with_built_event(self):
        payload = {"foo": "bar"}
        result = self.handler.execute(payload, invoker=_stub_invoker)
        assert result["invoked"] == "lambda.test_handler"
        assert result["event"] == payload

    def test_execute_returns_post_invoke_result(self):
        called = {}

        class _CustomHandler(ITaskHandler):
            @property
            def meta(self):
                return TaskMeta("T-2", "커스텀", "lambda.custom")

            def post_invoke(self, result, payload):
                called["post_invoke"] = True
                return {**result, "augmented": True}

        h = _CustomHandler()
        result = h.execute({}, invoker=_stub_invoker)
        assert called.get("post_invoke") is True
        assert result["augmented"] is True


# ── A-2: Slack event wrapping ─────────────────────────────────────────────────

class TestA2Handler:
    def setup_method(self):
        self.handler = TASK_REGISTRY["A-2"]

    def test_build_event_wraps_payload_in_slack_body(self):
        payload = {"channel_name": "테스트채널", "work_title": "테스트작품"}
        event = self.handler.build_event(payload)
        assert "body" in event
        body = json.loads(event["body"])
        assert body["type"] == "event_callback"
        assert "테스트채널" in body["event"]["text"]
        assert "테스트작품" in body["event"]["text"]

    def test_build_event_uses_defaults_for_missing_fields(self):
        event = self.handler.build_event({})
        body = json.loads(event["body"])
        assert body["event"]["channel"] == "C_HTTP_TRIGGER"
        assert body["event"]["ts"] == "manual-0001"

    def test_build_event_uses_custom_slack_channel(self):
        payload = {"slack_channel_id": "C_CUSTOM", "slack_message_ts": "ts-123"}
        event = self.handler.build_event(payload)
        body = json.loads(event["body"])
        assert body["event"]["channel"] == "C_CUSTOM"
        assert body["event"]["ts"] == "ts-123"

    def test_execute_passes_wrapped_event_to_invoker(self):
        received = {}

        def _capture(module, event):
            received["module"] = module
            received["event"] = event
            return {"status": "ok"}

        self.handler.execute({"channel_name": "채널A"}, invoker=_capture)
        assert received["module"] == "lambda.a2_work_approval_handler"
        assert "body" in received["event"]  # event is wrapped


# ── A-3: post_invoke Supabase logging ─────────────────────────────────────────

class TestA3Handler:
    def setup_method(self):
        self.handler = TASK_REGISTRY["A-3"]

    def test_post_invoke_logs_to_supabase(self, monkeypatch):
        mock_sb = MagicMock()
        monkeypatch.setattr(
            "src.tasks.a3_handler.get_supabase",
            lambda: mock_sb,
        )
        result = {"status": "ok"}
        out = self.handler.post_invoke(result, {})
        assert out is result  # original result returned unchanged
        mock_sb.table.assert_called_with("naver_new_channel_monthly_report")

    def test_post_invoke_swallows_supabase_errors(self, monkeypatch):
        monkeypatch.setattr(
            "src.tasks.a3_handler.get_supabase",
            lambda: (_ for _ in ()).throw(RuntimeError("DB down")),
        )
        # Must not raise — failure is logged and result returned unchanged
        result = {"status": "ok"}
        out = self.handler.post_invoke(result, {})
        assert out is result

    def test_execute_calls_invoker_then_supabase(self, monkeypatch):
        mock_sb = MagicMock()
        monkeypatch.setattr("src.tasks.a3_handler.get_supabase", lambda: mock_sb)
        result = self.handler.execute({}, invoker=_stub_invoker)
        assert result["status"] == "ok"
        mock_sb.table.assert_called_with("naver_new_channel_monthly_report")


# ── Passthrough handlers ───────────────────────────────────────────────────────

@pytest.mark.parametrize("task_id,expected_module", [
    ("B-2", "lambda.b2_weekly_report_handler"),
    ("C-1", "lambda.c1_lead_filter_handler"),
    ("C-2", "lambda.c2_cold_email_handler"),
    ("C-4", "lambda.c4_coupon_notification_handler"),
    ("D-3", "lambda.d3_kakao_creator_onboarding_handler"),
])
class TestPassthroughHandlers:
    def test_build_event_is_passthrough(self, task_id, expected_module):
        handler = TASK_REGISTRY[task_id]
        payload = {"a": 1}
        assert handler.build_event(payload) is payload

    def test_execute_invokes_correct_module(self, task_id, expected_module):
        handler = TASK_REGISTRY[task_id]
        result = handler.execute({"x": 1}, invoker=_stub_invoker)
        assert result["invoked"] == expected_module


# ── C-3: post_invoke saves work to Supabase ──────────────────────────────────

class TestC3Handler:
    def setup_method(self):
        self.handler = TASK_REGISTRY["C-3"]

    def _make_mock_sb(self):
        sb = MagicMock()
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.order.return_value = sb
        sb.limit.return_value = sb
        sb.insert.return_value = sb
        sb.update.return_value = sb
        sb.upsert.return_value = sb
        result = MagicMock()
        result.data = [{"id": 1, "work_title": "테스트작품"}]
        sb.execute.return_value = result
        return sb

    def test_post_invoke_saves_work_and_attaches_to_result(self, monkeypatch):
        mock_sb = self._make_mock_sb()
        monkeypatch.setattr("src.tasks.c3_handler.get_supabase", lambda: mock_sb)
        result = {"status": "ok"}
        out = self.handler.post_invoke(result, {"work_title": "테스트작품"})
        assert "supabase_work" in out

    def test_post_invoke_attaches_error_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            "src.tasks.c3_handler.get_supabase",
            lambda: (_ for _ in ()).throw(RuntimeError("DB error")),
        )
        result = {"status": "ok"}
        out = self.handler.post_invoke(result, {"work_title": "테스트작품"})
        assert "supabase_work_error" in out

    def test_post_invoke_raises_on_missing_work_title(self, monkeypatch):
        mock_sb = self._make_mock_sb()
        monkeypatch.setattr("src.tasks.c3_handler.get_supabase", lambda: mock_sb)
        result = {"status": "ok"}
        out = self.handler.post_invoke(result, {})  # empty payload → work_title missing
        # ValueError is caught → error attached, not raised
        assert "supabase_work_error" in out
        assert "work_title" in out["supabase_work_error"]
