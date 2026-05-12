"""Google Drive 파일/폴더 다운로드 — AME input 폴더로 저장."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def _build_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from src.encoding.config import GOOGLE_SERVICE_ACCOUNT_FILE

    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def _get_file_metadata(service, file_id: str) -> dict:
    return service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,size,parents"
    ).execute()


def _is_video(mime_type: str, name: str) -> bool:
    from src.encoding.config import VIDEO_MIME_TYPES, VIDEO_EXTENSIONS
    if mime_type in VIDEO_MIME_TYPES:
        return True
    return Path(name).suffix.lower() in VIDEO_EXTENSIONS


def _is_large(size_bytes: int) -> bool:
    from src.encoding.config import LARGE_FILE_THRESHOLD_BYTES
    return size_bytes >= LARGE_FILE_THRESHOLD_BYTES


def _download_file(service, file_id: str, dest_path: Path) -> None:
    """Drive 파일을 dest_path 로 다운로드."""
    from googleapiclient.http import MediaIoBaseDownload
    import io

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=32 * 1024 * 1024)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.info("  다운로드 %.0f%%", status.progress() * 100)


def handle_drive_file(file_id: str, sender: str, subject: str) -> None:
    """Drive 파일 ID를 받아 영상 여부·용량 판단 후 input 폴더로 다운로드."""
    from src.encoding.config import ENCODE_INPUT_DIR
    from src.encoding import notifier

    service = _build_drive_service()
    try:
        meta = _get_file_metadata(service, file_id)
    except Exception as exc:
        msg = f"메타데이터 조회 실패: {exc}"
        logger.error(msg)
        notifier.notify_download_failed(sender, f"id={file_id}", msg)
        return

    name      = meta.get("name", "unknown")
    mime_type = meta.get("mimeType", "")
    size      = int(meta.get("size", 0))
    size_mb   = size / 1024 / 1024

    logger.info("Drive 파일: %s | mime=%s | %.0f MB", name, mime_type, size_mb)

    if not _is_video(mime_type, name):
        logger.info("영상 파일 아님 — 건너뜀: %s", name)
        return

    if not _is_large(size):
        logger.info("소용량(%.0f MB) — AME 불필요, 건너뜀: %s", size_mb, name)
        return

    notifier.notify_drive_link_found(sender, name, size_mb)

    dest = ENCODE_INPUT_DIR / name
    if dest.exists():
        logger.info("이미 존재하는 파일 — 건너뜀: %s", dest)
        return

    logger.info("다운로드 시작: %s → %s", name, dest)
    try:
        _download_file(service, file_id, dest)
        logger.info("다운로드 완료: %s", dest)
    except Exception as exc:
        notifier.notify_download_failed(sender, name, str(exc))
        if dest.exists():
            dest.unlink()


def handle_drive_folder(folder_id: str, sender: str, subject: str) -> None:
    """Drive 폴더 내 영상 파일을 모두 처리."""
    service = _build_drive_service()
    try:
        result = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id,name,mimeType,size)",
            pageSize=50,
        ).execute()
    except Exception as exc:
        logger.error("폴더 목록 조회 실패 (id=%s): %s", folder_id, exc)
        return

    files = result.get("files", [])
    logger.info("폴더 내 파일 %d건 확인 (folder_id=%s)", len(files), folder_id)
    for f in files:
        handle_drive_file(f["id"], sender, subject)
