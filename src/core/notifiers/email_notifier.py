"""이메일 발송 모듈 (AWS SES / SMTP 폴백)."""
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from ..interfaces.notifier import INotifier
from ..logger import CoreLogger

log = CoreLogger(__name__)


class EmailNotifier(INotifier):
    def __init__(self, sender_email: str, use_ses: bool = True) -> None:
        self._sender = sender_email
        self._use_ses = use_ses

    def send(self, recipient: str, message: str, **kwargs: Any) -> bool:
        """kwargs: subject, html(bool), attachments(list[tuple[str, bytes]])"""
        subject = kwargs.get("subject", "알림")
        html = kwargs.get("html", False)
        attachments = kwargs.get("attachments", [])

        msg = MIMEMultipart()
        msg["From"] = self._sender
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "html" if html else "plain", "utf-8"))

        for filename, data in attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)

        try:
            if self._use_ses:
                return self._send_via_ses(recipient, msg)
            return self._send_via_smtp(recipient, msg)
        except Exception as e:
            log.error("이메일 발송 실패 → %s: %s", recipient, e)
            return False

    def send_error(self, task_id: str, error: Exception, context: Optional[dict] = None) -> bool:
        log.warning("EmailNotifier.send_error 미지원. Slack을 사용하세요.")
        return False

    def _send_via_ses(self, recipient: str, msg: MIMEMultipart) -> bool:
        import boto3
        client = boto3.client("ses", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
        client.send_raw_email(
            Source=self._sender,
            Destinations=[recipient],
            RawMessage={"Data": msg.as_string()},
        )
        log.info("SES 발송 성공 → %s", recipient)
        return True

    def _send_via_smtp(self, recipient: str, msg: MIMEMultipart) -> bool:
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER", self._sender), os.getenv("SMTP_PASSWORD", ""))
            server.sendmail(self._sender, recipient, msg.as_string())
        log.info("SMTP 발송 성공 → %s", recipient)
        return True
