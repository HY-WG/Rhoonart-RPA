import traceback
from typing import Any, Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ..interfaces.notifier import INotifier
from ..logger import CoreLogger

log = CoreLogger(__name__)


class SlackNotifier(INotifier):
    def __init__(self, token: str, error_channel: str) -> None:
        self._client = WebClient(token=token)
        self._error_channel = error_channel

    def send(self, recipient: str, message: str, **kwargs: Any) -> bool:
        """recipient: 채널 ID 또는 #채널명."""
        try:
            self._client.chat_postMessage(
                channel=recipient,
                text=message,
                **{k: v for k, v in kwargs.items() if k in ("blocks", "thread_ts", "username")},
            )
            return True
        except SlackApiError as e:
            log.error("Slack 발송 실패 → %s: %s", recipient, e.response["error"])
            return False

    def send_error(self, task_id: str, error: Exception, context: Optional[dict] = None) -> bool:
        tb = traceback.format_exc()
        text = (
            f":rotating_light: *[{task_id}] 자동화 실패*\n"
            f"```{type(error).__name__}: {error}\n\n{tb[:800]}```"
        )
        if context:
            text += f"\n*Context:* `{context}`"
        return self.send(self._error_channel, text)

    def reply_to_thread(self, channel: str, thread_ts: str, message: str) -> bool:
        return self.send(channel, message, thread_ts=thread_ts)
