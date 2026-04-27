# -*- coding: utf-8 -*-
"""NullNotifier — 알림 발송을 무시하는 INotifier 구현체.

사용 목적:
  - Slack / 이메일 미설정 환경(로컬 개발, 테스트)에서 INotifier 의존성을 주입.
  - send / send_error 호출이 항상 True 를 반환하므로 호출 코드에서 분기 불필요.
  - 테스트에서는 NullNotifier.sent 목록을 조회하여 발송 여부를 검증할 수 있음.

Example::

    from src.core.notifiers.null_notifier import NullNotifier

    notifier = NullNotifier()
    notifier.send("recipient", "message")
    print(notifier.sent)   # [{"recipient": ..., "message": ...}]
"""
from __future__ import annotations

from typing import Any, Optional

from ..interfaces.notifier import INotifier


class NullNotifier(INotifier):
    """알림 발송을 무시하는 INotifier 구현체.

    발송 기록을 ``sent`` 리스트에 누적합니다 (테스트 검증용).
    """

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send(self, recipient: str, message: str, **kwargs: Any) -> bool:
        self.sent.append({"recipient": recipient, "message": message, **kwargs})
        return True

    def send_error(
        self, task_id: str, error: Exception, context: Optional[dict] = None
    ) -> bool:
        self.sent.append({
            "task_id": task_id,
            "error": str(error),
            "context": context,
        })
        return True

    def reply(self, *args: Any, **kwargs: Any) -> bool:
        return True
