"""카카오 알림톡 발송 모듈 (A-1).

카카오 비즈니스 채널 API(비즈플러그인)를 사용한다.
"""
import os
from typing import Any, Optional

import requests

from ..interfaces.notifier import INotifier
from ..logger import CoreLogger

log = CoreLogger(__name__)


class KakaoNotifier(INotifier):
    def __init__(self, api_key: str, sender_key: str, base_url: str = "https://kakaoapi.aligo.in") -> None:
        self._api_key = api_key
        self._sender_key = sender_key
        self._base_url = base_url

    def send(self, recipient: str, message: str, **kwargs: Any) -> bool:
        """recipient: 수신자 전화번호 (01012345678 형식).

        kwargs:
            template_code (str): 알림톡 템플릿 코드
            name (str): 수신자 이름
        """
        payload = {
            "apikey": self._api_key,
            "userid": os.getenv("KAKAO_USER_ID", ""),
            "senderkey": self._sender_key,
            "tpl_code": kwargs.get("template_code", ""),
            "sender": os.getenv("KAKAO_SENDER_PHONE", ""),
            "receiver_1": recipient,
            "recvname_1": kwargs.get("name", ""),
            "msg_1": message,
            "failover": "N",
        }
        try:
            resp = requests.post(f"{self._base_url}/akv10/alimtalk/send/", data=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != "0":
                log.error("알림톡 발송 실패: %s", result.get("message"))
                return False
            log.info("알림톡 발송 성공 → %s", recipient)
            return True
        except Exception as e:
            log.error("알림톡 API 호출 실패: %s", e)
            return False

    def send_error(self, task_id: str, error: Exception, context: Optional[dict] = None) -> bool:
        log.warning("KakaoNotifier.send_error 미지원. Slack을 사용하세요.")
        return False
