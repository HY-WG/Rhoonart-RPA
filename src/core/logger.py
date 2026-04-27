import logging
import sys


def CoreLogger(name: str) -> logging.Logger:
    """구조화된 로거 팩토리. 모든 핸들러/모듈에서 동일한 포맷 사용."""
    log = logging.getLogger(name)
    if log.handlers:
        return log

    log.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    log.addHandler(handler)
    return log
