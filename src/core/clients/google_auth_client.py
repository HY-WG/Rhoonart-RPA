# -*- coding: utf-8 -*-
"""Google 인증 클라이언트.

``build_google_creds`` 는 credentials.json 포맷을 자동 감지하여
서비스 계정(Lambda/prod) 또는 OAuth2 installed-app(로컬 개발) 중 적합한
인증 객체를 반환한다.

토큰 캐시 경로: ``~/.config/rhoonart-rpa/token.json``

Example::

    from src.core.clients.google_auth_client import build_google_creds, ALL_SCOPES

    creds = build_google_creds(settings.GOOGLE_CREDENTIALS_FILE, ALL_SCOPES)
    client = gspread.authorize(creds)
"""
from __future__ import annotations

import json
import os
from typing import Any

# ---------------------------------------------------------------------------
# 공통 스코프 상수
# ---------------------------------------------------------------------------

#: 모든 핸들러에서 공유하는 Google API 스코프 목록.
ALL_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_TOKEN_FILE = os.path.expanduser("~/.config/rhoonart-rpa/token.json")


def build_google_creds(
    cred_file: str | None = None,
    scopes: list[str] | None = None,
) -> Any:
    """credentials.json 형식을 자동 감지해 Google 인증 객체를 반환한다.

    서비스 계정(``"type": "service_account"``) 이면 즉시 반환하고,
    OAuth2 installed-app 이면 토큰 캐시를 확인한 뒤 필요 시 브라우저
    인증 흐름을 시작한다.

    Args:
        cred_file: ``credentials.json`` 파일 경로.
                   ``None`` 이면 ``GOOGLE_CREDENTIALS_FILE`` 환경변수 →
                   ``'credentials.json'`` 순으로 폴백.
        scopes:    요청할 OAuth 스코프 목록.
                   ``None`` 이면 :data:`ALL_SCOPES` 를 사용한다.

    Returns:
        ``google.oauth2.credentials.Credentials`` 또는
        ``google.oauth2.service_account.Credentials`` 인스턴스.

    Raises:
        FileNotFoundError: ``cred_file`` 경로에 파일이 없을 때.
        google.auth.exceptions.TransportError: 네트워크 오류로 토큰 갱신 실패 시.
    """
    if cred_file is None:
        cred_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    if scopes is None:
        scopes = ALL_SCOPES

    with open(cred_file, encoding="utf-8") as f:
        data = json.load(f)

    # ── 서비스 계정 (Lambda / prod) ────────────────────────────────────────
    if data.get("type") == "service_account":
        from google.oauth2.service_account import Credentials
        return Credentials.from_service_account_file(cred_file, scopes=scopes)

    # ── OAuth2 installed-app (로컬 개발) ────────────────────────────────────
    import google.auth.transport.requests
    from google.oauth2.credentials import Credentials as OAuthCreds
    from google_auth_oauthlib.flow import InstalledAppFlow

    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)

    creds: Any = None
    if os.path.exists(_TOKEN_FILE):
        creds = OAuthCreds.from_authorized_user_file(_TOKEN_FILE, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_file, scopes)
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds
