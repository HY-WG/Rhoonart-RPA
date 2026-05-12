# -*- coding: utf-8 -*-
"""Backward-compatibility shim — 실제 구현은 src.core.clients.google_auth_client 에 있다.

기존 ``lambda/`` 및 ``scripts/`` 코드가 이 경로를 참조하므로 re-export만 유지한다.
신규 코드는 반드시 아래 경로에서 직접 임포트하라::

    from src.core.clients.google_auth_client import build_google_creds, ALL_SCOPES
"""
from src.core.clients.google_auth_client import ALL_SCOPES, build_google_creds  # noqa: F401

__all__ = ["ALL_SCOPES", "build_google_creds"]
