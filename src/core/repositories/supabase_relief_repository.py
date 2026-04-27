# -*- coding: utf-8 -*-
"""Supabase 기반 저작권 소명 신청 레포지토리.

D-2 저작권 소명 공문 요청 백오피스의 운영(production) 저장소 구현체.
개발/테스트 시에는 InMemoryReliefRequestRepository(src/backoffice/in_memory.py)를 사용하고
운영 환경에서 이 파일로 교체한다.

의존성:
  pip install supabase>=2.4.0

필요 환경 변수:
  SUPABASE_URL    Supabase 프로젝트 URL (예: https://xxxx.supabase.co)
  SUPABASE_KEY    Supabase service_role 키 (또는 anon 키)

Supabase 테이블 스키마 (DDL 예시):
  relief_requests        — 소명 신청 헤더
  relief_request_items   — 소명 대상 작품 행
  mail_templates         — 이메일 템플릿 (template_key PK)
  outbound_mails         — 발송 이력
  uploaded_documents     — 업로드된 파일 메타
  rights_holder_contacts — 권리사 연락처 (IRightsHolderDirectory용)

상세 DDL은 scripts/sql/d2_schema.sql 참고.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from typing import Optional

from ...models import (
    MailTemplate,
    OutboundMail,
    OutboundMailStatus,
    ReliefRequest,
    ReliefRequestItem,
    ReliefRequestStatus,
    RightsHolderContact,
    UploadedDocument,
)
from ..interfaces.repository import IReliefRequestRepository, IRightsHolderDirectory

log = logging.getLogger(__name__)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """datetime → ISO 8601 문자열 변환 헬퍼."""
    return dt.isoformat() if dt else None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """ISO 8601 문자열 → datetime 변환 헬퍼."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class SupabaseReliefRequestRepository(IReliefRequestRepository):
    """supabase-py 클라이언트 기반 저작권 소명 신청 저장소.

    Args:
        client: `supabase.create_client(url, key)` 반환값

    Example::

        import os
        from supabase import create_client
        from src.core.repositories.supabase_relief_repository import (
            SupabaseReliefRequestRepository,
        )

        client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
        repo = SupabaseReliefRequestRepository(client)
    """

    # 테이블명 상수
    _T_REQUESTS  = "relief_requests"
    _T_ITEMS     = "relief_request_items"
    _T_TEMPLATES = "mail_templates"
    _T_MAILS     = "outbound_mails"
    _T_DOCS      = "uploaded_documents"

    def __init__(self, client) -> None:
        self._db = client

    # ── IReliefRequestRepository ──────────────────────────────────────────

    def list_requests(
        self,
        status: Optional[ReliefRequestStatus] = None,
    ) -> list[ReliefRequest]:
        query = self._db.table(self._T_REQUESTS).select("*").order(
            "created_at", desc=True
        )
        if status is not None:
            query = query.eq("status", status.value)
        resp = query.execute()
        return [self._row_to_request(row) for row in (resp.data or [])]

    def get_request(self, request_id: str) -> Optional[ReliefRequest]:
        resp = (
            self._db.table(self._T_REQUESTS)
            .select("*")
            .eq("request_id", request_id)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        return self._row_to_request(rows[0]) if rows else None

    def save_request(self, request: ReliefRequest) -> None:
        data = self._request_to_row(request)
        self._db.table(self._T_REQUESTS).upsert(data, on_conflict="request_id").execute()
        log.debug("[D-2 Supabase] save_request %s", request.request_id)

    def update_request(self, request: ReliefRequest) -> None:
        data = self._request_to_row(request)
        self._db.table(self._T_REQUESTS).update(data).eq(
            "request_id", request.request_id
        ).execute()
        log.debug("[D-2 Supabase] update_request %s → %s", request.request_id, request.status)

    def list_request_items(self, request_id: str) -> list[ReliefRequestItem]:
        resp = (
            self._db.table(self._T_ITEMS)
            .select("*")
            .eq("request_id", request_id)
            .execute()
        )
        return [self._row_to_item(row) for row in (resp.data or [])]

    def replace_request_items(
        self,
        request_id: str,
        items: list[ReliefRequestItem],
    ) -> None:
        # 기존 행 삭제 후 새로 삽입 (트랜잭션 미지원 — 운영 시 DB Function 활용 권장)
        self._db.table(self._T_ITEMS).delete().eq("request_id", request_id).execute()
        if items:
            rows = [self._item_to_row(item) for item in items]
            self._db.table(self._T_ITEMS).insert(rows).execute()
        log.debug("[D-2 Supabase] replace_request_items %s: %d행", request_id, len(items))

    def get_mail_template(self, template_key: str) -> Optional[MailTemplate]:
        resp = (
            self._db.table(self._T_TEMPLATES)
            .select("*")
            .eq("template_key", template_key)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return None
        row = rows[0]
        return MailTemplate(
            template_key=row["template_key"],
            subject_template=row["subject_template"],
            body_template=row["body_template"],
            is_html=row.get("is_html", True),
        )

    def save_mail_template(self, template: MailTemplate) -> None:
        self._db.table(self._T_TEMPLATES).upsert(
            {
                "template_key": template.template_key,
                "subject_template": template.subject_template,
                "body_template": template.body_template,
                "is_html": template.is_html,
            },
            on_conflict="template_key",
        ).execute()

    def list_outbound_mails(self, request_id: str) -> list[OutboundMail]:
        resp = (
            self._db.table(self._T_MAILS)
            .select("*")
            .eq("request_id", request_id)
            .order("sent_at", desc=False)
            .execute()
        )
        return [self._row_to_mail(row) for row in (resp.data or [])]

    def save_outbound_mail(self, mail: OutboundMail) -> None:
        self._db.table(self._T_MAILS).upsert(
            self._mail_to_row(mail), on_conflict="mail_id"
        ).execute()
        log.debug("[D-2 Supabase] save_outbound_mail %s → %s", mail.mail_id, mail.status)

    def save_uploaded_document(self, document: UploadedDocument) -> None:
        self._db.table(self._T_DOCS).upsert(
            {
                "document_id": document.document_id,
                "request_id": document.request_id,
                "holder_name": document.holder_name,
                "drive_file_id": document.drive_file_id,
                "drive_file_url": document.drive_file_url,
                "stored_path": document.stored_path,
                "uploaded_at": _iso(document.uploaded_at),
            },
            on_conflict="document_id",
        ).execute()

    # ── 직렬화 헬퍼 ──────────────────────────────────────────────────────

    @staticmethod
    def _row_to_request(row: dict) -> ReliefRequest:
        return ReliefRequest(
            request_id=row["request_id"],
            requester_channel_name=row["requester_channel_name"],
            requester_email=row["requester_email"],
            requester_notes=row.get("requester_notes", ""),
            status=ReliefRequestStatus(row.get("status", "pending")),
            created_at=_parse_dt(row.get("created_at")),
            updated_at=_parse_dt(row.get("updated_at")),
            submitted_via=row.get("submitted_via", "web"),
        )

    @staticmethod
    def _request_to_row(request: ReliefRequest) -> dict:
        return {
            "request_id": request.request_id,
            "requester_channel_name": request.requester_channel_name,
            "requester_email": request.requester_email,
            "requester_notes": request.requester_notes,
            "status": request.status.value,
            "created_at": _iso(request.created_at),
            "updated_at": _iso(request.updated_at),
            "submitted_via": request.submitted_via,
        }

    @staticmethod
    def _row_to_item(row: dict) -> ReliefRequestItem:
        return ReliefRequestItem(
            request_id=row["request_id"],
            work_id=row["work_id"],
            work_title=row["work_title"],
            rights_holder_name=row["rights_holder_name"],
            channel_folder_name=row.get("channel_folder_name", ""),
        )

    @staticmethod
    def _item_to_row(item: ReliefRequestItem) -> dict:
        return {
            "request_id": item.request_id,
            "work_id": item.work_id,
            "work_title": item.work_title,
            "rights_holder_name": item.rights_holder_name,
            "channel_folder_name": item.channel_folder_name,
        }

    @staticmethod
    def _row_to_mail(row: dict) -> OutboundMail:
        return OutboundMail(
            mail_id=row["mail_id"],
            request_id=row["request_id"],
            holder_name=row["holder_name"],
            recipient_email=row["recipient_email"],
            subject=row["subject"],
            body=row.get("body", ""),
            status=OutboundMailStatus(row.get("status", "pending")),
            sent_at=_parse_dt(row.get("sent_at")),
            error_message=row.get("error_message", ""),
        )

    @staticmethod
    def _mail_to_row(mail: OutboundMail) -> dict:
        return {
            "mail_id": mail.mail_id,
            "request_id": mail.request_id,
            "holder_name": mail.holder_name,
            "recipient_email": mail.recipient_email,
            "subject": mail.subject,
            "body": mail.body,
            "status": mail.status.value,
            "sent_at": _iso(mail.sent_at),
            "error_message": mail.error_message,
        }


class SupabaseRightsHolderDirectory(IRightsHolderDirectory):
    """supabase-py 클라이언트 기반 권리사 연락처 디렉토리.

    Supabase `rights_holder_contacts` 테이블:
      holder_id (text, pk)
      holder_name (text)
      recipient_email (text)
      work_title (text)   ← 1 행 = 1 작품 (정규화 형태)
      template_key (text, default 'rights_holder_request')

    Example::

        directory = SupabaseRightsHolderDirectory(client)
        contacts = directory.resolve_contacts(["작품A", "작품B"])
    """

    _T_CONTACTS = "rights_holder_contacts"

    def __init__(self, client) -> None:
        self._db = client

    def resolve_contacts(self, work_titles: list[str]) -> list[RightsHolderContact]:
        if not work_titles:
            return []
        resp = (
            self._db.table(self._T_CONTACTS)
            .select("*")
            .in_("work_title", work_titles)
            .execute()
        )
        rows = resp.data or []

        # 권리사별로 작품 묶기
        by_holder: dict[str, dict] = {}
        for row in rows:
            hid = row["holder_id"]
            if hid not in by_holder:
                by_holder[hid] = {
                    "holder_id": hid,
                    "holder_name": row["holder_name"],
                    "recipient_email": row["recipient_email"],
                    "template_key": row.get("template_key", "rights_holder_request"),
                    "work_titles": [],
                }
            by_holder[hid]["work_titles"].append(row["work_title"])

        return [
            RightsHolderContact(
                holder_id=v["holder_id"],
                holder_name=v["holder_name"],
                recipient_email=v["recipient_email"],
                template_key=v["template_key"],
                work_titles=v["work_titles"],
            )
            for v in by_holder.values()
        ]
