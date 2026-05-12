"""Gmail 메일 감시 — Drive/Naver Box 링크 추출 후 처리."""
from __future__ import annotations

import base64
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 링크 패턴 ────────────────────────────────────────────────────────────────
_DRIVE_FILE_RE  = re.compile(r"https://drive\.google\.com/(?:file/d/|open\?id=)([\w-]+)")
_DRIVE_FOLDER_RE = re.compile(r"https://drive\.google\.com/drive/folders/([\w-]+)")
_NAVER_BOX_RE   = re.compile(r"https://(?:mybox|drive)\.naver\.com/\S+")


def _build_gmail_service():
    """OAuth 기반 Gmail 서비스 클라이언트 반환."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from src.encoding.config import GMAIL_CREDENTIALS_FILE, GMAIL_TOKEN_FILE

    scopes = ["https://www.googleapis.com/auth/gmail.readonly",
              "https://www.googleapis.com/auth/gmail.modify"]
    creds = None
    token_path = Path(GMAIL_TOKEN_FILE)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS_FILE, scopes)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: dict) -> str:
    """메일 페이로드에서 텍스트 본문 추출."""
    parts = payload.get("parts", [])
    if not parts:
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore") if data else ""

    text = ""
    for part in parts:
        mime = part.get("mimeType", "")
        if mime in ("text/plain", "text/html"):
            data = part.get("body", {}).get("data", "")
            text += base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore") if data else ""
        elif mime.startswith("multipart/"):
            text += _decode_body(part)
    return text


def _extract_links(body: str) -> dict:
    """본문에서 Drive 파일/폴더, Naver Box 링크 추출."""
    return {
        "drive_file_ids": list(dict.fromkeys(_DRIVE_FILE_RE.findall(body))),
        "drive_folder_ids": list(dict.fromkeys(_DRIVE_FOLDER_RE.findall(body))),
        "naver_box_links": list(dict.fromkeys(_NAVER_BOX_RE.findall(body))),
    }


def _get_sender(headers: list[dict]) -> str:
    for h in headers:
        if h.get("name", "").lower() == "from":
            return h["value"]
    return "unknown"


def _get_subject(headers: list[dict]) -> str:
    for h in headers:
        if h.get("name", "").lower() == "subject":
            return h["value"]
    return "(제목 없음)"


def _mark_as_processed(service, msg_id: str) -> None:
    """처리 완료 메일에 라벨 추가 (ENCODE_PROCESSED)."""
    try:
        # 라벨 없으면 생성
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
        label_id = next((l["id"] for l in labels if l["name"] == "ENCODE_PROCESSED"), None)
        if not label_id:
            label = service.users().labels().create(
                userId="me", body={"name": "ENCODE_PROCESSED", "labelListVisibility": "labelShow"}
            ).execute()
            label_id = label["id"]
        service.users().messages().modify(
            userId="me", id=msg_id,
            body={"addLabelIds": [label_id], "removeLabelIds": ["UNREAD"]}
        ).execute()
    except Exception as exc:
        logger.warning("메일 라벨 처리 실패: %s", exc)


def poll_once(on_drive_file, on_drive_folder, on_naver_box) -> None:
    """미처리 메일 1회 폴링.

    Args:
        on_drive_file:   (file_id, sender, subject) 콜백
        on_drive_folder: (folder_id, sender, subject) 콜백
        on_naver_box:    (link, sender, subject) 콜백
    """
    service = _build_gmail_service()
    # ENCODE_PROCESSED 라벨이 없는 메일만 조회
    query = "-label:ENCODE_PROCESSED"
    result = service.users().messages().list(userId="me", q=query, maxResults=20).execute()
    messages = result.get("messages", [])
    logger.info("미처리 메일 %d건 확인", len(messages))

    for msg_meta in messages:
        msg_id = msg_meta["id"]
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            sender  = _get_sender(headers)
            subject = _get_subject(headers)
            body    = _decode_body(payload)
            links   = _extract_links(body)

            has_link = False
            for file_id in links["drive_file_ids"]:
                on_drive_file(file_id, sender, subject)
                has_link = True
            for folder_id in links["drive_folder_ids"]:
                on_drive_folder(folder_id, sender, subject)
                has_link = True
            for naver_link in links["naver_box_links"]:
                on_naver_box(naver_link, sender, subject)
                has_link = True

            if has_link:
                _mark_as_processed(service, msg_id)
                logger.info("메일 처리 완료: %s — %s", sender, subject)
        except Exception as exc:
            logger.error("메일 처리 실패 (id=%s): %s", msg_id, exc)


def run_forever(on_drive_file, on_drive_folder, on_naver_box) -> None:
    """지정 간격으로 메일 폴링을 반복 실행."""
    from src.encoding.config import GMAIL_POLL_INTERVAL
    logger.info("Gmail 감시 시작 (간격: %ds)", GMAIL_POLL_INTERVAL)
    while True:
        try:
            poll_once(on_drive_file, on_drive_folder, on_naver_box)
        except Exception as exc:
            logger.error("폴링 오류: %s", exc)
        time.sleep(GMAIL_POLL_INTERVAL)
