# -*- coding: utf-8 -*-
"""공유 의존성 빌더.

Google 인증 자동 감지:
  - service_account 형식  -> Credentials.from_service_account_file()  (Lambda/prod)
  - OAuth2 installed 형식 -> InstalledAppFlow + 토큰 캐시              (로컬 개발)

토큰 캐시 경로: ~/.config/rhoonart-rpa/token.json
"""
from __future__ import annotations

import json
import os
from typing import Any

_TOKEN_FILE = os.path.expanduser("~/.config/rhoonart-rpa/token.json")

# 모든 핸들러에서 필요한 공통 스코프
ALL_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def build_google_creds(
    cred_file: str | None = None,
    scopes: list[str] | None = None,
) -> Any:
    """credentials.json 형식을 자동 감지해 Google 인증 객체 반환.

    Args:
        cred_file: credentials.json 경로.
                   None 이면 GOOGLE_CREDENTIALS_FILE 환경변수 또는 'credentials.json'.
        scopes:    OAuth 스코프 목록. None 이면 ALL_SCOPES 사용.

    Returns:
        google.oauth2.credentials.Credentials (service account or OAuth2)
    """
    if cred_file is None:
        cred_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    if scopes is None:
        scopes = ALL_SCOPES

    with open(cred_file, encoding="utf-8") as f:
        data = json.load(f)

    if data.get("type") == "service_account":
        from google.oauth2.service_account import Credentials
        return Credentials.from_service_account_file(cred_file, scopes=scopes)

    # ── OAuth2 installed app 형식 ────────────────────────────────────────────
    import google.auth.transport.requests
    from google.oauth2.credentials import Credentials as OAuthCreds
    from google_auth_oauthlib.flow import InstalledAppFlow

    os.makedirs(os.path.dirname(_TOKEN_FILE), exist_ok=True)

    creds = None
    if os.path.exists(_TOKEN_FILE):
        creds = OAuthCreds.from_authorized_user_file(_TOKEN_FILE, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_file, scopes)
            # run_local_server: 브라우저 인증 1회 후 토큰 캐시
            creds = flow.run_local_server(port=0)
        with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds
