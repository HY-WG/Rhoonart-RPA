import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import json

import pytz

KST = pytz.timezone("Asia/Seoul")


class TaskStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILURE = "FAILURE"


class TriggerType(str, Enum):
    SLACK_WEBHOOK = "slack_webhook"
    GAS_WEBHOOK = "gas_webhook"
    HTTP = "http"
    CRON = "cron"
    MANUAL = "manual"


@dataclass
class LogEntry:
    task_id: str
    task_name: str
    trigger_type: TriggerType
    status: TaskStatus
    trigger_source: str = ""
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, str]] = None
    duration_ms: int = 0
    executed_at: datetime = field(default_factory=lambda: datetime.now(KST))
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "log_id": self.log_id,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "executed_at": self.executed_at.isoformat(),
            "trigger_type": self.trigger_type.value,
            "trigger_source": self.trigger_source,
            "status": self.status.value,
            "duration_ms": self.duration_ms,
            "result": self.result,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
