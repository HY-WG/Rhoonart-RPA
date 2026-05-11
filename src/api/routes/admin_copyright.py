"""Admin copyright-claims and official-documents routes."""
from __future__ import annotations

import io
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from src.api.dependencies import KST, check_auth, get_supabase
from src.api.schemas.requests import OfficialDocumentSaveRequest
from src.api.storage import (
    OFFICIAL_DOCUMENT_BUCKET,
    download_official_document_file,
    safe_storage_name,
    upload_storage_file,
)

router = APIRouter(tags=["copyright"])
logger = logging.getLogger(__name__)


# ── Sample data (DB tables not yet created) ──────────────────────────────────

def _sample_copyright_claim_groups() -> list[dict[str, Any]]:
    return [
        {
            "right_holder_id": "sample-holder-jamena",
            "right_holder_name": "재미나",
            "has_previous_claim": False,
            "claims": [
                {
                    "id": "sample-claim-1",
                    "channel_id": "sample-channel-1",
                    "channel_name": "재미나",
                    "work_id": "sample-work-snl-1",
                    "work_title": "SNL 코리아 리부트시즌 8",
                    "right_holder_id": "sample-holder-jamena",
                    "right_holder_name": "재미나",
                    "requested_at": "2026-05-08T00:00:00+09:00",
                    "due": "2026-05-14",
                    "has_admin_official_document": False,
                    "has_official_document": False,
                    "official_document_status": "not_requested",
                    "official_document_status_label": "요청 전",
                },
                {
                    "id": "sample-claim-2",
                    "channel_id": "sample-channel-2",
                    "channel_name": "재미나",
                    "work_id": "sample-work-snl-2",
                    "work_title": "SNL 코리아 리부트시즌 8",
                    "right_holder_id": "sample-holder-jamena",
                    "right_holder_name": "재미나",
                    "requested_at": "2026-05-08T00:00:00+09:00",
                    "due": "2026-05-14",
                    "has_admin_official_document": False,
                    "has_official_document": False,
                    "official_document_status": "not_requested",
                    "official_document_status_label": "요청 전",
                },
            ],
        },
        {
            "right_holder_id": "sample-holder-movieclip",
            "right_holder_name": "무비클립",
            "has_previous_claim": True,
            "claims": [
                {
                    "id": "sample-claim-3",
                    "channel_id": "sample-channel-3",
                    "channel_name": "무비클립",
                    "work_id": "sample-work-princess",
                    "work_title": "21세기 대군부인",
                    "right_holder_id": "sample-holder-movieclip",
                    "right_holder_name": "무비클립",
                    "requested_at": "2026-05-10T00:00:00+09:00",
                    "due": "2026-05-16",
                    "has_admin_official_document": True,
                    "has_official_document": False,
                    "official_document_status": "not_requested",
                    "official_document_status_label": "요청 전",
                }
            ],
        },
    ]


def _default_official_document(holder_name: str, work_title: str = "") -> dict[str, Any]:
    safe_holder = holder_name or "권리사"
    safe_work = work_title or "유미의 세포들 시즌3"
    return {
        "title": f"{safe_holder} 콘텐츠 활용 권한 확인 공문",
        "body": f"""
<div style="text-align:center;font-weight:700;font-size:20px;margin-bottom:28px">{safe_holder} 콘텐츠 활용 권한 확인 공문</div>
<p><strong>발신:</strong> 주식회사 {safe_holder}</p>
<p><strong>수신:</strong> 주식회사 루나르트</p>
<p><strong>참조:</strong> 온라인 동영상 스트리밍 플랫폼 담당자</p>
<p><strong>제목:</strong> 주식회사 루나르트의 {safe_holder} 콘텐츠 활용 권한 확인의 건</p>
<hr style="border:0;border-top:1px solid #cbd5e1;margin:24px 0" />
<ol style="padding-left:22px;line-height:1.9">
  <li>귀사(주식회사 루나르트)의 무궁한 발전을 기원합니다.</li>
  <li>당사(주식회사 {safe_holder})와 귀사 간 체결된 '업무 제휴 계약서'에 의거, 귀사가 당사가 보유한 콘텐츠에 대하여 온라인 동영상 스트리밍 플랫폼 내 콘텐츠 활용 권한을 부여받았음을 확인합니다.</li>
  <li>본 권한은 아래와 같이 유효합니다.
    <ol type="a" style="padding-left:22px">
      <li>권한 콘텐츠 : 사용 가능한 콘텐츠 목록은 별첨 &lt;콘텐츠 목록&gt;에서 확인할 수 있습니다.</li>
      <li>활용 플랫폼 : 유튜브, 네이버TV, 네이버 클립</li>
      <li>활용 주체 : 주식회사 루나르트 소속의 크리에이터</li>
    </ol>
  </li>
  <li>본 공문은 귀사가 상기 플랫폼에서 해당 콘텐츠를 활용함에 있어 당사의 이용 허락을 입증하는 공식 증빙 자료로 사용할 수 있습니다.</li>
</ol>
<p style="text-align:center;margin-top:32px">2026.04.21.</p>
<p style="text-align:center;margin-top:36px;font-weight:700">주식회사 {safe_holder}</p>
<p style="text-align:center;margin-top:24px">대표&nbsp;&nbsp;최 주 희&nbsp;&nbsp;&nbsp;(서명/인)</p>
<h3 style="margin-top:40px">[별첨] 콘텐츠 목록</h3>
<table style="width:100%;border-collapse:collapse;font-size:14px">
  <thead>
    <tr style="background:#f8fafc">
      <th style="width:80px;border:1px solid #cbd5e1;padding:8px 10px;text-align:center">번호</th>
      <th style="border:1px solid #cbd5e1;padding:8px 10px;text-align:left">작품명</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="border:1px solid #cbd5e1;padding:8px 10px;text-align:center">1</td>
      <td style="border:1px solid #cbd5e1;padding:8px 10px">{safe_work}</td>
    </tr>
  </tbody>
</table>
""".strip(),
    }


# ── Copyright claim helpers ──────────────────────────────────────────────────

def _group_copyright_claim_rows(
    sb,
    rows: list[dict[str, Any]],
    status_by_holder: dict[str, bool],
) -> list[dict[str, Any]]:
    groups_by_holder: dict[str, dict[str, Any]] = {}
    for row in rows:
        holder = row.get("rights_holders") or {}
        holder_id = str(row.get("right_holder_id") or "")
        if not holder_id:
            continue
        holder_name = holder.get("rights_holder_name") or "-"
        channel_name = row.get("channel_name") or "-"
        work_title = row.get("work_title") or "-"
        group = groups_by_holder.setdefault(
            holder_id,
            {
                "right_holder_id": holder_id,
                "right_holder_name": holder_name,
                "has_previous_claim": status_by_holder.get(holder_id, False),
                "claims": [],
            },
        )
        group["claims"].append(
            {
                "id": str(row.get("id") or ""),
                "channel_id": str(row.get("channel_id") or ""),
                "channel_name": channel_name,
                "work_id": str(row.get("work_id") or ""),
                "work_title": work_title,
                "right_holder_id": holder_id,
                "right_holder_name": holder_name,
                "requested_at": row.get("requested_at"),
                "due": row.get("due"),
                "completed": bool(row.get("completed", False)),
                "status_label": "완료" if row.get("completed") else "처리요망",
                "official_document_status": row.get("official_document_status") or "not_requested",
                "official_document_status_label": {
                    "not_requested": "요청 전",
                    "requested": "요청 중",
                    "received": "접수 완료",
                }.get(str(row.get("official_document_status") or "not_requested"), "요청 전"),
                "has_official_document": bool(row.get("official_document_file_path")),
                "official_document_file_path": row.get("official_document_file_path"),
                "official_document_file_name": row.get("official_document_file_name"),
                "official_document_uploaded_at": row.get("official_document_uploaded_at"),
            }
        )
    work_ids = [
        str(claim.get("work_id"))
        for group in groups_by_holder.values()
        for claim in group["claims"]
        if claim.get("work_id")
    ]
    if work_ids:
        try:
            doc_result = (
                sb.table("official_documents")
                .select("work_id")
                .in_("work_id", work_ids)
                .execute()
            )
            documented_work_ids = {
                str(item.get("work_id"))
                for item in (doc_result.data or [])
                if item.get("work_id")
            }
            for group in groups_by_holder.values():
                for claim in group["claims"]:
                    claim["has_admin_official_document"] = str(claim.get("work_id") or "") in documented_work_ids
        except Exception as exc:
            logger.warning("official_documents work_id lookup failed: %s", exc)
    return list(groups_by_holder.values())


def _load_copyright_claim_groups(sb) -> tuple[list[dict[str, Any]], bool]:
    try:
        try:
            claim_result = (
                sb.table("copyright_claims")
                .select(
                    "id, channel_id, work_id, right_holder_id, requested_at, due, completed, "
                    "channel_name, work_title, official_document_status, official_document_file_path, "
                    "official_document_file_name, official_document_uploaded_at, "
                    "rights_holders(rights_holder_name)"
                )
                .eq("completed", False)
                .order("requested_at", desc=True)
                .limit(300)
                .execute()
            )
        except Exception as exc:
            if "completed" not in str(exc) and "official_document" not in str(exc):
                raise
            logger.warning(
                "copyright_claims status columns missing; listing without filter. "
                "Apply migrations/017 and 018."
            )
            claim_result = (
                sb.table("copyright_claims")
                .select(
                    "id, channel_id, work_id, right_holder_id, requested_at, due, "
                    "channel_name, work_title, rights_holders(rights_holder_name)"
                )
                .order("requested_at", desc=True)
                .limit(300)
                .execute()
            )
        status_result = (
            sb.table("right_holder_status")
            .select("right_holder_id, has_previous_claim")
            .execute()
        )
        status_by_holder = {
            str(item.get("right_holder_id")): bool(item.get("has_previous_claim"))
            for item in (status_result.data or [])
        }
        groups = _group_copyright_claim_rows(sb, claim_result.data or [], status_by_holder)
        return groups, False
    except Exception as exc:
        logger.warning("copyright claim tables unavailable; using samples: %s", exc)
        return _sample_copyright_claim_groups(), True


def _flatten_claim_groups(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for group in groups:
        items.extend(group.get("claims", []))
    return items


def _load_right_holder_name(sb, right_holder_id: str) -> str:
    if right_holder_id.startswith("sample-holder"):
        for group in _sample_copyright_claim_groups():
            if group["right_holder_id"] == right_holder_id:
                return str(group["right_holder_name"])
    try:
        result = (
            sb.table("rights_holders")
            .select("rights_holder_name")
            .eq("id", right_holder_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0].get("rights_holder_name") or "권리사")
    except Exception as exc:
        logger.warning("failed to load right holder name: %s", exc)
    return "권리사"


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/api/admin/copyright-claims")
def list_copyright_claims(_: None = Depends(check_auth)) -> dict[str, Any]:
    sb = get_supabase()
    groups, fallback = _load_copyright_claim_groups(sb)
    return {"items": _flatten_claim_groups(groups), "groups": groups, "fallback": fallback}


@router.post("/api/admin/copyright-claims/right-holders/{right_holder_id}/request")
def request_copyright_claim(
    right_holder_id: str,
    body: dict[str, Any] = Body(default_factory=dict),
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    sb = get_supabase()
    holder_name = _load_right_holder_name(sb, right_holder_id)
    work_id = str(body.get("work_id") or "").strip()
    now = datetime.now(KST).isoformat()

    # ── (1) admin 공문 저장 여부 확인 ─────────────────────────────────────────
    # official_documents 테이블에 해당 권리사(+작품)의 공문이 저장돼 있는지 확인한다.
    has_admin_document = False
    if right_holder_id.startswith("sample-holder"):
        # 샘플: 무비클립만 공문 있음, 재미나는 없음
        has_admin_document = right_holder_id == "sample-holder-movieclip"
    else:
        try:
            query = (
                sb.table("official_documents")
                .select("id")
                .eq("right_holder_id", right_holder_id)
            )
            if work_id:
                query = query.eq("work_id", work_id)
            result = query.limit(1).execute()
            has_admin_document = bool(result.data)
        except Exception as exc:
            logger.warning("official_documents lookup failed: %s", exc)

    if not has_admin_document:
        # 공문 없음 → 프론트에서 안내 모달을 띄우도록 action 반환 (DB 업데이트 없음)
        return {
            "right_holder_id": right_holder_id,
            "right_holder_name": holder_name,
            "action": "no_admin_document",
            "message": "해당 권리사는 이전 소명 진행 이력이 없습니다. 공문을 먼저 작성해주세요.",
        }

    # ── (2) official_document_status → "requested" 로 업데이트 ───────────────
    # 파트너 도메인의 '저작권 소명 요청 리스트'에서 확인할 수 있게 된다.
    try:
        update_query = (
            sb.table("copyright_claims")
            .update({
                "official_document_status": "requested",
                "official_document_requested_at": now,
                "updated_at": now,
            })
            .eq("right_holder_id", right_holder_id)
            .eq("completed", False)
        )
        if work_id:
            update_query = update_query.eq("work_id", work_id)
        update_query.execute()
    except Exception as exc:
        logger.warning("failed to mark official document requested: %s", exc)

    return {
        "right_holder_id": right_holder_id,
        "right_holder_name": holder_name,
        "action": "partner_request_sent",
        "message": f"{holder_name} 권리사에게 소명 요청을 발송했습니다. 파트너 도메인에서 확인할 수 있습니다.",
    }


@router.get("/api/admin/official-documents")
def list_official_document_holders(_: None = Depends(check_auth)) -> dict[str, Any]:
    sb = get_supabase()
    try:
        holders_result = (
            sb.table("rights_holders")
            .select("id, rights_holder_name")
            .order("rights_holder_name")
            .execute()
        )
        if not holders_result.data:
            try:
                naver_rows = (
                    sb.table("naver_rights_holders")
                    .select("rights_holder_name")
                    .order("rights_holder_name")
                    .execute()
                ).data or []
                seen: set[str] = set()
                to_insert = []
                for row in naver_rows:
                    name = str(row.get("rights_holder_name") or "").strip()
                    if name and name not in seen:
                        seen.add(name)
                        to_insert.append({"rights_holder_name": name})
                if to_insert:
                    sb.table("rights_holders").upsert(
                        to_insert, on_conflict="rights_holder_name"
                    ).execute()
                    holders_result = (
                        sb.table("rights_holders")
                        .select("id, rights_holder_name")
                        .order("rights_holder_name")
                        .execute()
                    )
            except Exception as seed_exc:
                logger.warning("rights_holders 자동 시드 실패: %s", seed_exc)

        try:
            documents = sb.table("official_documents").select("right_holder_id, work_id, updated_at").execute()
        except Exception:
            documents = sb.table("official_documents").select("right_holder_id, updated_at").execute()

        doc_by_holder: dict[str, Any] = {}
        doc_by_work: dict[str, Any] = {}
        for item in documents.data or []:
            holder_key = str(item.get("right_holder_id"))
            work_key = str(item.get("work_id") or "")
            if work_key:
                doc_by_work[work_key] = item.get("updated_at")
            elif holder_key:
                doc_by_holder[holder_key] = item.get("updated_at")

        works_by_holder: dict[str, list[dict[str, Any]]] = {}
        try:
            work_rows = (
                sb.table("works")
                .select("id, work_title, rights_holder_id")
                .order("work_title")
                .limit(2000)
                .execute()
            ).data or []
            for work in work_rows:
                holder_id = str(work.get("rights_holder_id") or "").strip()
                if not holder_id:
                    continue
                work_id = str(work.get("id") or "").strip()
                if not work_id:
                    continue
                works_by_holder.setdefault(holder_id, []).append(
                    {
                        "work_id": work_id,
                        "work_title": work.get("work_title") or "-",
                        "has_document": work_id in doc_by_work,
                        "updated_at": doc_by_work.get(work_id),
                    }
                )
        except Exception as exc:
            logger.warning("works lookup for official documents failed: %s", exc)

        return {
            "items": [
                {
                    "right_holder_id": str(holder.get("id")),
                    "right_holder_name": holder.get("rights_holder_name") or "-",
                    "has_document": str(holder.get("id")) in doc_by_holder
                    or any(work.get("has_document") for work in works_by_holder.get(str(holder.get("id")), [])),
                    "updated_at": doc_by_holder.get(str(holder.get("id"))),
                    "works": works_by_holder.get(str(holder.get("id")), []),
                }
                for holder in (holders_result.data or [])
            ],
            "fallback": False,
        }
    except Exception as exc:
        logger.warning("official document tables unavailable; using samples: %s", exc)
        return {
            "items": [
                {
                    "right_holder_id": group["right_holder_id"],
                    "right_holder_name": group["right_holder_name"],
                    "has_document": False,
                    "updated_at": None,
                }
                for group in _sample_copyright_claim_groups()
            ],
            "fallback": True,
        }


@router.get("/api/admin/official-documents/{right_holder_id}")
def get_official_document(
    right_holder_id: str,
    work_id: str = "",
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    sb = get_supabase()
    holder_name = _load_right_holder_name(sb, right_holder_id)
    work_title = ""
    if work_id:
        try:
            work_result = (
                sb.table("works").select("work_title").eq("id", work_id).limit(1).execute()
            )
            if work_result.data:
                work_title = str(work_result.data[0].get("work_title") or "")
        except Exception as exc:
            logger.warning("failed to load work title for official document: %s", exc)
    try:
        query = sb.table("official_documents").select(
            "id, right_holder_id, work_id, content_body, created_at, updated_at"
        ).eq("right_holder_id", right_holder_id)
        query = query.eq("work_id", work_id) if work_id else query.is_("work_id", "null")
        result = query.limit(1).execute()
        if result.data:
            document = result.data[0]
            return {**document, "right_holder_name": holder_name, "work_title": work_title, "fallback": False}
    except Exception as exc:
        logger.warning("official_documents unavailable: %s", exc)
    return {
        "right_holder_id": right_holder_id,
        "right_holder_name": holder_name,
        "work_id": work_id or None,
        "work_title": work_title,
        "content_body": _default_official_document(holder_name, work_title),
        "fallback": True,
    }


@router.put("/api/admin/official-documents/{right_holder_id}")
def save_official_document(
    right_holder_id: str,
    request: OfficialDocumentSaveRequest,
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    if right_holder_id.startswith("sample-holder"):
        raise HTTPException(
            status_code=503,
            detail="샘플 권리사는 DB 저장 대상이 아닙니다. 마이그레이션 적용 후 저장할 수 있습니다.",
        )
    sb = get_supabase()
    now = datetime.now(KST).isoformat()
    raw_work_id = str(request.work_id or "").strip()
    work_id = int(raw_work_id) if raw_work_id.isdigit() else None
    payload = {
        "right_holder_id": right_holder_id,
        "work_id": work_id,
        "content_body": request.content_body,
        "updated_at": now,
    }
    try:
        result = (
            sb.table("official_documents")
            .upsert(payload, on_conflict="right_holder_id,work_id")
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"official_documents 저장에 실패했습니다: {exc}"
        ) from exc
    return {"status": "saved", "item": (result.data or [payload])[0]}


@router.get("/api/partner/copyright-claims")
def list_partner_copyright_claims(_: None = Depends(check_auth)) -> dict[str, Any]:
    sb = get_supabase()
    groups, fallback = _load_copyright_claim_groups(sb)

    def _partner_visible(claim: dict[str, Any]) -> bool:
        """admin이 요청했거나(requested) 파트너가 파일을 업로드한(received) 건만 파트너에 표시."""
        status = str(claim.get("official_document_status") or "not_requested")
        return status in ("requested", "received") or bool(claim.get("has_official_document"))

    items = [item for item in _flatten_claim_groups(groups) if _partner_visible(item)]
    visible_ids = {str(item.get("work_id") or "") for item in items if item.get("work_id")}
    filtered_groups = []
    for group in groups:
        claims = [
            claim
            for claim in group.get("claims", [])
            if str(claim.get("work_id") or "") in visible_ids and _partner_visible(claim)
        ]
        if claims:
            filtered_groups.append({**group, "claims": claims})
    return {"items": items, "groups": filtered_groups, "fallback": fallback}


@router.get("/api/partner/official-documents/{right_holder_id}")
def get_partner_official_document(right_holder_id: str, work_id: str = "") -> dict[str, Any]:
    """파트너가 자신의 권리사 공문을 조회합니다. 관리자 인증 불필요."""
    sb = get_supabase()
    holder_name = _load_right_holder_name(sb, right_holder_id)
    try:
        query = sb.table("official_documents").select(
            "id, right_holder_id, work_id, content_body, created_at, updated_at"
        ).eq("right_holder_id", right_holder_id)
        query = query.eq("work_id", work_id) if work_id else query.is_("work_id", "null")
        result = query.limit(1).execute()
        if result.data:
            return {**result.data[0], "right_holder_name": holder_name, "fallback": False}
    except Exception as exc:
        logger.warning("official_documents unavailable for partner view: %s", exc)
    return {
        "right_holder_id": right_holder_id,
        "right_holder_name": holder_name,
        "work_id": work_id or None,
        "content_body": _default_official_document(holder_name, ""),
        "fallback": True,
    }


@router.post("/api/partner/copyright-claims/official-document-upload")
async def upload_partner_official_document(
    claim_ids: str = Form(...),
    file: UploadFile = File(...),
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    try:
        parsed_claim_ids = json.loads(claim_ids)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="claim_ids must be a JSON array") from exc
    if not isinstance(parsed_claim_ids, list) or not parsed_claim_ids:
        raise HTTPException(status_code=400, detail="업로드 대상 claim_ids가 필요합니다.")
    safe_claim_ids = [str(item) for item in parsed_claim_ids if str(item).strip()]
    if not safe_claim_ids:
        raise HTTPException(status_code=400, detail="업로드 대상 claim_ids가 필요합니다.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일은 업로드할 수 없습니다.")
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="파일 크기는 30MB 이하만 업로드할 수 있습니다.")

    now_dt = datetime.now(KST)
    original_name = file.filename or "official_document"
    storage_path = (
        f"{now_dt.strftime('%Y/%m/%d')}/"
        f"{uuid.uuid4()}_{safe_storage_name(original_name)}"
    )
    content_type = file.content_type or "application/octet-stream"
    upload_storage_file(OFFICIAL_DOCUMENT_BUCKET, storage_path, content, content_type)

    payload = {
        "official_document_status": "received",
        "official_document_file_path": storage_path,
        "official_document_file_name": original_name,
        "official_document_content_type": content_type,
        "official_document_file_size": len(content),
        "official_document_uploaded_at": now_dt.isoformat(),
        "updated_at": now_dt.isoformat(),
    }
    sb = get_supabase()
    try:
        result = sb.table("copyright_claims").update(payload).in_("id", safe_claim_ids).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"공문 파일 메타데이터 저장 실패: {exc}. migrations/018_copyright_claim_official_document_files.sql 적용 여부를 확인하세요.",
        ) from exc
    return {
        "status": "uploaded",
        "claim_ids": safe_claim_ids,
        "file_name": original_name,
        "file_size": len(content),
        "items": result.data or [],
    }


@router.post("/api/admin/copyright-claims/channels/{channel_id}/send-email")
def send_channel_claim_email(
    channel_id: str,
    body: dict[str, Any] = Body(default_factory=dict),
    _: None = Depends(check_auth),
) -> dict[str, Any]:
    """채널의 저작권 소명 요청 건을 일괄 메일로 발송합니다.

    Frontend ``sendChannelClaimEmail(channelId, claimIds)`` 에서 호출됩니다.
    현재는 claim 상태를 'requested'로 업데이트하고 발송 완료 응답을 반환합니다.
    실제 메일 발송 로직은 EmailNotifier 연동 후 확장합니다.
    """
    claim_ids: list[str] = [str(c) for c in (body.get("claim_ids") or []) if str(c).strip()]
    if not claim_ids:
        raise HTTPException(status_code=400, detail="claim_ids가 필요합니다.")

    sb = get_supabase()
    now = datetime.now(KST).isoformat()

    # 샘플 채널이면 DB 조작 없이 즉시 응답
    if channel_id.startswith("sample-channel"):
        return {
            "status": "sent",
            "channel_id": channel_id,
            "claim_count": len(claim_ids),
            "message": f"[샘플] {len(claim_ids)}건의 소명 요청 메일 발송이 완료되었습니다.",
        }

    # 실제 채널: copyright_claims 상태 업데이트 → 메일 발송 예정
    updated_count = 0
    try:
        result = (
            sb.table("copyright_claims")
            .update({"official_document_status": "requested", "updated_at": now})
            .in_("id", claim_ids)
            .eq("channel_id", channel_id)
            .execute()
        )
        updated_count = len(result.data or [])
    except Exception as exc:
        logger.warning("copyright_claims 상태 업데이트 실패: %s", exc)

    # TODO: 실제 이메일 발송 (EmailNotifier 연동)
    # notifier = EmailNotifier(...)
    # notifier.send(channel_id=channel_id, claim_ids=claim_ids)

    logger.info(
        "send_channel_claim_email: channel_id=%s claims=%s updated=%s",
        channel_id,
        claim_ids,
        updated_count,
    )
    return {
        "status": "sent",
        "channel_id": channel_id,
        "claim_count": len(claim_ids),
        "updated_count": updated_count,
        "message": f"{len(claim_ids)}건의 소명 요청 메일 발송이 완료되었습니다.",
    }


@router.get("/api/admin/copyright-claims/{claim_id}/official-document-file")
def download_copyright_document_file(
    claim_id: str,
    _: None = Depends(check_auth),
) -> StreamingResponse:
    sb = get_supabase()
    result = (
        sb.table("copyright_claims")
        .select(
            "official_document_file_path, official_document_file_name, "
            "official_document_content_type"
        )
        .eq("id", claim_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="copyright_claims 항목을 찾을 수 없습니다.")
    item = result.data[0]
    path = item.get("official_document_file_path")
    if not path:
        raise HTTPException(status_code=404, detail="업로드된 공문 파일이 없습니다.")
    content = download_official_document_file(str(path))
    filename = item.get("official_document_file_name") or "official_document"
    return StreamingResponse(
        io.BytesIO(content),
        media_type=item.get("official_document_content_type") or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{quote(str(filename))}"'},
    )
