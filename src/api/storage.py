"""Supabase Storage helpers shared across route modules."""
from __future__ import annotations

import logging
import re
import unicodedata
from urllib.parse import quote

import requests as http_requests
from fastapi import HTTPException

from src.config import settings

logger = logging.getLogger(__name__)

OFFICIAL_DOCUMENT_BUCKET = "official-documents"
NAVER_REVENUE_BUCKET = "naver-revenue-settlements"


def _supabase_storage_headers(content_type: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _ensure_storage_bucket(bucket: str) -> None:
    url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/bucket"
    response = http_requests.post(
        url,
        headers=_supabase_storage_headers("application/json"),
        json={"id": bucket, "name": bucket, "public": False},
        timeout=10,
    )
    if response.status_code not in {200, 201, 409}:
        logger.warning("storage bucket check failed: %s %s", response.status_code, response.text[:300])


def upload_storage_file(bucket: str, path: str, content: bytes, content_type: str) -> None:
    """Upload content to bucket/path via Supabase Storage REST API."""
    _ensure_storage_bucket(bucket)
    url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{bucket}/{quote(path, safe='/')}"
    response = http_requests.post(
        url,
        headers={**_supabase_storage_headers(content_type), "x-upsert": "true"},
        data=content,
        timeout=30,
    )
    if response.status_code not in {200, 201}:
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {response.text[:500]}")


def download_official_document_file(path: str) -> bytes:
    """Download a file from the official-documents bucket."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{OFFICIAL_DOCUMENT_BUCKET}/{quote(path, safe='/')}"
    response = http_requests.get(url, headers=_supabase_storage_headers(), timeout=30)
    if response.status_code != 200:
        raise HTTPException(status_code=404, detail="업로드된 공문 파일을 찾을 수 없습니다.")
    return response.content


def clean_filename(value: str) -> str:
    """Sanitize a display filename without making it a storage key."""
    allowed = []
    for char in value.strip():
        if char.isalnum() or char in {" ", ".", "-", "_", "(", ")"}:
            allowed.append(char)
        else:
            allowed.append("_")
    return "".join(allowed).strip(" .") or "upload"


def safe_storage_name(value: str) -> str:
    """Return an ASCII object-key-safe filename for Supabase Storage."""
    cleaned = clean_filename(value)
    ascii_name = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("ascii")
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_name).strip("._-")
    return ascii_name[:120] or "document"
