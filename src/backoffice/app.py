from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

from ..models import ReliefRequestStatus
from ..services import ReliefRequestService
from .dependencies import get_relief_request_service
from .schemas import (
    OutboundMailModel,
    ReliefRequestCreateModel,
    ReliefRequestDetailModel,
    ReliefRequestItemModel,
    ReliefRequestSummaryModel,
    SendRightsHolderMailRequest,
    SendRightsHolderMailResponse,
)


def build_app(
    service: ReliefRequestService | None = None,
    slack_notifier: Optional[Any] = None,  # INotifier — 신규 신청 시 관리자 Slack 알림
) -> FastAPI:
    app = FastAPI(title="루나트 저작권 소명 관리 API", version="0.1.0")

    _slack = slack_notifier  # 클로저 캡처

    def _get_service() -> ReliefRequestService:
        return service or get_relief_request_service()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/admin/relief-requests", response_model=list[ReliefRequestSummaryModel])
    def list_relief_requests(
        status: str | None = Query(default=None),
        relief_service: ReliefRequestService = Depends(_get_service),
    ) -> list[ReliefRequestSummaryModel]:
        try:
            parsed_status = ReliefRequestStatus(status) if status else None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid status: {status}") from exc
        return [
            ReliefRequestSummaryModel(
                request_id=request.request_id,
                requester_channel_name=request.requester_channel_name,
                requester_email=request.requester_email,
                requester_notes=request.requester_notes,
                status=request.status.value,
                created_at=request.created_at,
                updated_at=request.updated_at,
                submitted_via=request.submitted_via,
            )
            for request in relief_service.list_requests(status=parsed_status)
        ]

    @app.post("/api/relief-requests", response_model=ReliefRequestSummaryModel)
    def create_relief_request(
        payload: ReliefRequestCreateModel,
        relief_service: ReliefRequestService = Depends(_get_service),
    ) -> ReliefRequestSummaryModel:
        request = relief_service.create_request(
            requester_channel_name=payload.requester_channel_name,
            requester_email=payload.requester_email,
            requester_notes=payload.requester_notes,
            submitted_via=payload.submitted_via,
            work_items=[item.model_dump() for item in payload.items],
        )
        # D-2 인입 알림: Slack으로 관리자에게 신규 신청 알림
        if _slack is not None:
            try:
                work_titles = ", ".join(item.work_title for item in payload.items)
                # INotifier.send 의 recipient 는 채널 ID 또는 이름.
                # _slack 구현체가 SlackNotifier 일 경우 error_channel 을 사용하고,
                # 그렇지 않으면 "admin" 으로 폴백합니다.
                notify_channel = getattr(_slack, "_error_channel", "admin")
                _slack.send(
                    recipient=notify_channel,
                    message=(
                        f":incoming_envelope: *새 저작권 소명 신청 접수*\n"
                        f"• 채널: *{request.requester_channel_name}*\n"
                        f"• 이메일: {request.requester_email}\n"
                        f"• 신청 작품: {work_titles}\n"
                        f"• 신청 ID: `{request.request_id}`\n"
                        f"• 메모: {request.requester_notes or '(없음)'}"
                    ),
                )
            except Exception:
                pass  # 알림 실패는 메인 플로우에 영향 없음
        return ReliefRequestSummaryModel(
            request_id=request.request_id,
            requester_channel_name=request.requester_channel_name,
            requester_email=request.requester_email,
            requester_notes=request.requester_notes,
            status=request.status.value,
            created_at=request.created_at,
            updated_at=request.updated_at,
            submitted_via=request.submitted_via,
        )

    @app.get("/api/admin/relief-requests/{request_id}", response_model=ReliefRequestDetailModel)
    def get_relief_request(
        request_id: str,
        relief_service: ReliefRequestService = Depends(_get_service),
    ) -> ReliefRequestDetailModel:
        try:
            detail = relief_service.get_request_detail(request_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ReliefRequestDetailModel(
            request_id=detail.request.request_id,
            requester_channel_name=detail.request.requester_channel_name,
            requester_email=detail.request.requester_email,
            requester_notes=detail.request.requester_notes,
            status=detail.request.status.value,
            created_at=detail.request.created_at,
            updated_at=detail.request.updated_at,
            submitted_via=detail.request.submitted_via,
            items=[
                ReliefRequestItemModel(
                    work_id=item.work_id,
                    work_title=item.work_title,
                    rights_holder_name=item.rights_holder_name,
                    channel_folder_name=item.channel_folder_name,
                )
                for item in detail.items
            ],
            outbound_mails=[
                OutboundMailModel(
                    mail_id=mail.mail_id,
                    holder_name=mail.holder_name,
                    recipient_email=mail.recipient_email,
                    subject=mail.subject,
                    status=mail.status.value,
                    sent_at=mail.sent_at,
                    error_message=mail.error_message,
                )
                for mail in detail.outbound_mails
            ],
        )

    @app.post(
        "/api/admin/relief-requests/{request_id}/send-mails",
        response_model=SendRightsHolderMailResponse,
    )
    def send_rights_holder_mails(
        request_id: str,
        payload: SendRightsHolderMailRequest,
        relief_service: ReliefRequestService = Depends(_get_service),
    ) -> SendRightsHolderMailResponse:
        try:
            result = relief_service.send_rights_holder_mails(
                request_id=request_id,
                template_key=payload.template_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return SendRightsHolderMailResponse(
            request_id=result.request_id,
            attempted=result.attempted,
            sent=result.sent,
            failed=result.failed,
            updated_status=result.updated_status.value,
        )

    return app


app = build_app()
