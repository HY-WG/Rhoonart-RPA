"""A-2 task handler — 작품 사용요청 승인 자동화.

build_event wraps the API payload into the Slack event-callback body
that the A-2 Lambda expects.
"""
from __future__ import annotations

import json
from typing import Any

from src.core.interfaces.task_handler import ITaskHandler, TaskMeta


class A2TaskHandler(ITaskHandler):
    @property
    def meta(self) -> TaskMeta:
        return TaskMeta(
            task_id="A-2",
            task_name="작품 사용요청 승인 자동화",
            lambda_module="lambda.a2_work_approval_handler",
        )

    def build_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Wrap API payload into the Slack event-callback structure."""
        p = dict(payload)
        return {
            "body": json.dumps(
                {
                    "type": "event_callback",
                    "event": {
                        "type": "message",
                        "channel": p.get("slack_channel_id", "C_HTTP_TRIGGER"),
                        "ts": p.get("slack_message_ts", "manual-0001"),
                        "text": (
                            f'채널: "{p.get("channel_name", "Test Channel")}" '
                            f"신규 영상 사용 요청이 있습니다.\n"
                            f'{p.get("work_title", "Test Work")}'
                        ),
                    },
                },
                ensure_ascii=False,
            )
        }
