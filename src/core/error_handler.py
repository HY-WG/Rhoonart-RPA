import logging
import time
import traceback
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional

import pytz

from ..models import LogEntry, TaskStatus, TriggerType

KST = pytz.timezone("Asia/Seoul")
logger = logging.getLogger(__name__)


def task_handler(
    task_id: str,
    task_name: str,
    trigger_type: TriggerType,
    trigger_source: str = "",
    log_repo=None,       # ILogRepository — 순환참조 방지를 위해 타입 힌트 생략
    slack_notifier=None, # INotifier
):
    """모든 Lambda 핸들러에 적용하는 공통 데코레이터.

    성공/실패 여부와 무관하게 LogEntry를 로그 시트에 기록하고,
    실패 시 Slack 에러 알림을 발송한다.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_ms = int(time.time() * 1000)
            executed_at = datetime.now(KST)
            try:
                result = func(*args, **kwargs)
                duration_ms = int(time.time() * 1000) - start_ms
                entry = LogEntry(
                    task_id=task_id,
                    task_name=task_name,
                    trigger_type=trigger_type,
                    trigger_source=trigger_source,
                    status=TaskStatus.SUCCESS,
                    result=result if isinstance(result, dict) else {"value": str(result)},
                    duration_ms=duration_ms,
                    executed_at=executed_at,
                )
                _safe_write_log(log_repo, entry)
                return result
            except Exception as exc:
                duration_ms = int(time.time() * 1000) - start_ms
                tb = traceback.format_exc()
                logger.error("[%s] 실패: %s\n%s", task_id, exc, tb)
                entry = LogEntry(
                    task_id=task_id,
                    task_name=task_name,
                    trigger_type=trigger_type,
                    trigger_source=trigger_source,
                    status=TaskStatus.FAILURE,
                    error={
                        "code": type(exc).__name__,
                        "message": str(exc),
                        "traceback": tb[:500],
                    },
                    duration_ms=duration_ms,
                    executed_at=executed_at,
                )
                _safe_write_log(log_repo, entry)
                _safe_send_error(slack_notifier, task_id, exc)
                raise

        return wrapper
    return decorator


def _safe_write_log(log_repo, entry: LogEntry) -> None:
    if log_repo is None:
        return
    try:
        log_repo.write_log(entry)
    except Exception as e:
        logger.error("로그 기록 실패: %s", e)


def _safe_send_error(slack_notifier, task_id: str, exc: Exception) -> None:
    if slack_notifier is None:
        return
    try:
        slack_notifier.send_error(task_id, exc)
    except Exception as e:
        logger.error("Slack 에러 알림 실패: %s", e)
