"""Slack 알림 모듈."""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_client():
    from slack_sdk import WebClient
    from src.encoding.config import SLACK_BOT_TOKEN
    return WebClient(token=SLACK_BOT_TOKEN)


def _send(text: str, channel: Optional[str] = None) -> None:
    from src.encoding.config import SLACK_CHANNEL
    try:
        _get_client().chat_postMessage(channel=channel or SLACK_CHANNEL, text=text)
    except Exception as exc:
        logger.error("Slack 알림 실패: %s", exc)


def notify_drive_link_found(sender: str, filename: str, size_mb: float) -> None:
    _send(f"📥 *Drive 영상 링크 감지*\n발신자: {sender}\n파일명: {filename}\n용량: {size_mb:.0f} MB\n→ AME 대기열에 투입합니다.")


def notify_download_failed(sender: str, link: str, reason: str) -> None:
    _send(f"⚠️ *Drive 다운로드 실패*\n발신자: {sender}\n링크: {link}\n사유: {reason}\n→ 수동 처리가 필요합니다.")


def notify_naver_box_link(sender: str, subject: str, link: str) -> None:
    _send(f"📦 *Naver Box 링크 수신* (수동 다운로드 필요)\n발신자: {sender}\n제목: {subject}\n링크: {link}")


def notify_encoding_complete(filename: str, drive_link: str) -> None:
    _send(f"✅ *인코딩 완료*\n파일명: {filename}\n드라이브: {drive_link}")


def notify_ame_crashed() -> None:
    _send("🚨 *AME 크래시 감지* — 자동 재시작을 시도합니다.")


def notify_ame_restarted(success: bool) -> None:
    if success:
        _send("🔄 AME 재시작 완료.")
    else:
        _send("🚨 AME 재시작 실패 — 수동 확인이 필요합니다.")


def notify_disk_low(free_gb: float, path: str) -> None:
    _send(f"💾 *디스크 용량 부족 경고*\n경로: {path}\n여유 공간: {free_gb:.1f} GB\n→ 오래된 파일을 정리해주세요.")
