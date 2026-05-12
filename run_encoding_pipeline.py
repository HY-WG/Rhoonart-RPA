"""인코딩 자동화 파이프라인 메인 실행 파일.

인코딩 PC에서 실행:
    python run_encoding_pipeline.py

세 가지 스레드를 동시에 실행한다:
  1. Gmail 폴링 — Drive/Naver Box 링크 감지
  2. Output 감시 — 인코딩 완료 파일 업로드·삭제·알림
  3. AME 감시 — 크래시 감지·재시작, 디스크 용량 경보
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/encoding-pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline")


def _on_drive_file(file_id: str, sender: str, subject: str) -> None:
    from src.encoding.drive_downloader import handle_drive_file
    handle_drive_file(file_id, sender, subject)


def _on_drive_folder(folder_id: str, sender: str, subject: str) -> None:
    from src.encoding.drive_downloader import handle_drive_folder
    handle_drive_folder(folder_id, sender, subject)


def _on_naver_box(link: str, sender: str, subject: str) -> None:
    from src.encoding.notifier import notify_naver_box_link
    logger.info("Naver Box 링크 감지 — 수동 처리 알림: %s", link)
    notify_naver_box_link(sender, subject, link)


def _thread(name: str, target, *args) -> threading.Thread:
    t = threading.Thread(target=target, args=args, name=name, daemon=True)
    t.start()
    logger.info("스레드 시작: %s", name)
    return t


def main() -> None:
    Path("logs").mkdir(exist_ok=True)

    from src.encoding.config import ENCODE_INPUT_DIR, ENCODE_OUTPUT_DIR, ENCODE_ERROR_DIR
    for d in (ENCODE_INPUT_DIR, ENCODE_OUTPUT_DIR, ENCODE_ERROR_DIR):
        d.mkdir(parents=True, exist_ok=True)

    from src.encoding import gmail_watcher, output_watcher, ame_monitor

    threads = [
        _thread("gmail-watcher",  gmail_watcher.run_forever,
                _on_drive_file, _on_drive_folder, _on_naver_box),
        _thread("output-watcher", output_watcher.run_forever),
        _thread("ame-monitor",    ame_monitor.run_forever),
    ]

    logger.info("인코딩 파이프라인 실행 중. Ctrl+C 로 종료.")
    try:
        while all(t.is_alive() for t in threads):
            import time; time.sleep(10)
    except KeyboardInterrupt:
        logger.info("파이프라인 종료 요청")


if __name__ == "__main__":
    main()
