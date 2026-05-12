"""AME 프로세스 감시 — 크래시 감지 후 자동 재시작 + 디스크 용량 감시."""
from __future__ import annotations

import logging
import shutil
import subprocess
import time

logger = logging.getLogger(__name__)

_DISK_WARN_FREE_GB = 20.0  # 여유 공간 이 값 미만 시 경고


def _is_ame_running() -> bool:
    import psutil
    from src.encoding.config import AME_PROCESS_NAME
    return any(
        p.name().lower() == AME_PROCESS_NAME.lower()
        for p in psutil.process_iter(["name"])
    )


def _start_ame() -> bool:
    from src.encoding.config import AME_EXE_PATH
    try:
        subprocess.Popen([AME_EXE_PATH], shell=False)
        time.sleep(15)  # AME 초기화 대기
        return _is_ame_running()
    except Exception as exc:
        logger.error("AME 실행 실패: %s", exc)
        return False


def _check_disk(path: str) -> None:
    from src.encoding import notifier
    try:
        usage = shutil.disk_usage(path)
        free_gb = usage.free / 1024 ** 3
        if free_gb < _DISK_WARN_FREE_GB:
            logger.warning("디스크 여유 공간 부족: %.1f GB (%s)", free_gb, path)
            notifier.notify_disk_low(free_gb, path)
    except Exception as exc:
        logger.error("디스크 용량 확인 실패: %s", exc)


def run_forever() -> None:
    from src.encoding.config import AME_CHECK_INTERVAL, ENCODE_INPUT_DIR
    from src.encoding import notifier

    logger.info("AME 감시 시작 (간격: %ds)", AME_CHECK_INTERVAL)
    while True:
        try:
            if not _is_ame_running():
                logger.warning("AME 프로세스 없음 — 재시작 시도")
                notifier.notify_ame_crashed()
                success = _start_ame()
                notifier.notify_ame_restarted(success)
                if not success:
                    logger.error("AME 재시작 실패")
            else:
                logger.debug("AME 정상 실행 중")

            _check_disk(str(ENCODE_INPUT_DIR.drive or "C:\\"))
        except Exception as exc:
            logger.error("AME 감시 오류: %s", exc)

        time.sleep(AME_CHECK_INTERVAL)
