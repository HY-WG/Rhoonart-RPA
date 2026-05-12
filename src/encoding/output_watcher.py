"""인코딩 output 폴더 감시 — 완료 감지 후 Drive 업로드·원본 삭제·Slack 알림."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

# 파일별 마지막 수정 시각 추적
_file_last_modified: dict[Path, float] = {}


def _build_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from src.encoding.config import GOOGLE_SERVICE_ACCOUNT_FILE

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)


def _upload_to_drive(file_path: Path) -> str:
    """Drive 업로드 후 공유 링크 반환."""
    from googleapiclient.http import MediaFileUpload
    from src.encoding.config import UPLOAD_DRIVE_FOLDER_ID

    service = _build_drive_service()
    mime = "video/mp4" if file_path.suffix.lower() == ".mp4" else "application/octet-stream"
    file_meta = {"name": file_path.name}
    if UPLOAD_DRIVE_FOLDER_ID:
        file_meta["parents"] = [UPLOAD_DRIVE_FOLDER_ID]

    media = MediaFileUpload(str(file_path), mimetype=mime, resumable=True, chunksize=32 * 1024 * 1024)
    uploaded = service.files().create(body=file_meta, media_body=media, fields="id,webViewLink").execute()
    file_id = uploaded.get("id", "")

    # 링크 공개 설정 (뷰어 권한)
    service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    link = uploaded.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
    logger.info("Drive 업로드 완료: %s → %s", file_path.name, link)
    return link


def _delete_source(input_dir: Path, output_file: Path) -> None:
    """output 파일명으로 추정되는 input 원본 파일 삭제."""
    stem = output_file.stem
    from src.encoding.config import VIDEO_EXTENSIONS
    for ext in VIDEO_EXTENSIONS:
        candidate = input_dir / (stem + ext)
        if candidate.exists():
            candidate.unlink()
            logger.info("원본 삭제: %s", candidate)
            return
    logger.warning("원본 파일을 찾지 못했습니다 (stem=%s)", stem)


def _process_completed_file(file_path: Path) -> None:
    from src.encoding.config import ENCODE_INPUT_DIR, VIDEO_EXTENSIONS
    from src.encoding import notifier

    if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
        return

    logger.info("인코딩 완료 파일 처리 시작: %s", file_path.name)
    try:
        drive_link = _upload_to_drive(file_path)
        _delete_source(ENCODE_INPUT_DIR, file_path)
        notifier.notify_encoding_complete(file_path.name, drive_link)
    except Exception as exc:
        logger.error("후처리 실패 (%s): %s", file_path.name, exc)


class _OutputHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        _file_last_modified[Path(event.src_path)] = time.time()

    def on_created(self, event):
        if event.is_directory:
            return
        _file_last_modified[Path(event.src_path)] = time.time()


def _check_stable_files() -> None:
    """OUTPUT_STABLE_SECONDS 동안 변경 없는 파일 = 인코딩 완료로 판단."""
    from src.encoding.config import OUTPUT_STABLE_SECONDS
    now = time.time()
    completed = [
        p for p, t in list(_file_last_modified.items())
        if now - t >= OUTPUT_STABLE_SECONDS and p.exists()
    ]
    for file_path in completed:
        del _file_last_modified[file_path]
        _process_completed_file(file_path)


def run_forever() -> None:
    from src.encoding.config import ENCODE_OUTPUT_DIR, OUTPUT_STABLE_SECONDS

    ENCODE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(_OutputHandler(), str(ENCODE_OUTPUT_DIR), recursive=False)
    observer.start()
    logger.info("Output 폴더 감시 시작: %s", ENCODE_OUTPUT_DIR)

    try:
        while True:
            _check_stable_files()
            time.sleep(5)
    finally:
        observer.stop()
        observer.join()
