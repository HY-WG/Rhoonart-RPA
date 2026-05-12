"""인코딩 파이프라인 설정값."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── 폴더 경로 (인코딩 PC 기준) ──────────────────────────────────────────────
ENCODE_INPUT_DIR  = Path(os.getenv("ENCODE_INPUT_DIR",  r"C:\rhoonart-encode\input"))
ENCODE_OUTPUT_DIR = Path(os.getenv("ENCODE_OUTPUT_DIR", r"C:\rhoonart-encode\output"))
ENCODE_ERROR_DIR  = Path(os.getenv("ENCODE_ERROR_DIR",  r"C:\rhoonart-encode\_error"))

# ── Google ───────────────────────────────────────────────────────────────────
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE", r"C:\rhoonart-encode\credentials\service_account.json"
)
# 인코딩 완료 후 업로드할 Google Drive 폴더 ID
UPLOAD_DRIVE_FOLDER_ID = os.getenv("UPLOAD_DRIVE_FOLDER_ID", "")

# Gmail OAuth 자격증명 (인코딩 PC에 배치)
GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", r"C:\rhoonart-encode\credentials\gmail_oauth.json")
GMAIL_TOKEN_FILE       = os.getenv("GMAIL_TOKEN_FILE",       r"C:\rhoonart-encode\credentials\gmail_token.json")
# 메일 폴링 간격 (초)
GMAIL_POLL_INTERVAL = int(os.getenv("GMAIL_POLL_INTERVAL", "120"))

# ── Slack ────────────────────────────────────────────────────────────────────
SLACK_BOT_TOKEN   = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL     = os.getenv("SLACK_ENCODE_CHANNEL", "#encoding-log")

# ── AME ─────────────────────────────────────────────────────────────────────
AME_PROCESS_NAME  = "Adobe Media Encoder.exe"
AME_EXE_PATH      = os.getenv(
    "AME_EXE_PATH",
    r"C:\Program Files\Adobe\Adobe Media Encoder 2024\Adobe Media Encoder.exe",
)
AME_CHECK_INTERVAL = int(os.getenv("AME_CHECK_INTERVAL", "300"))  # 5분

# ── 파일 크기 기준 ───────────────────────────────────────────────────────────
# 이 값 이상이면 대용량 영상으로 판단하여 AME로 넘김 (bytes)
LARGE_FILE_THRESHOLD_BYTES = int(os.getenv("LARGE_FILE_THRESHOLD_MB", "200")) * 1024 * 1024

# 인코딩 완료 감지: output 폴더에서 이 초 이상 변경 없으면 완료로 판단
OUTPUT_STABLE_SECONDS = int(os.getenv("OUTPUT_STABLE_SECONDS", "10"))

VIDEO_MIME_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/mpeg", "video/x-ms-wmv",
    "video/webm", "video/3gpp",
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".mxf", ".mpg", ".mpeg", ".wmv", ".webm"}
