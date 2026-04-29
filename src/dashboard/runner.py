from __future__ import annotations

import importlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from src.backoffice.dependencies import get_relief_request_service
from src.config import settings
from src.core.repositories.supabase_integration_dashboard_repository import (
    SupabaseIntegrationDashboardRepository,
)
from src.handlers.a2_work_approval import parse_manual_request
from src.handlers.c4_coupon_notification import is_coupon_request

from .in_memory_repository import InMemoryIntegrationDashboardRepository
from .models import ExecutionMode, IntegrationRun, IntegrationRunStatus, IntegrationTaskSpec
from .repository import IIntegrationDashboardRepository

Adapter = Callable[[IntegrationRun, Callable[[str], None]], dict[str, Any]]


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_result(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict) and "statusCode" in raw and "body" in raw:
        body = raw.get("body")
        if isinstance(body, str):
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"raw_body": body}
        else:
            parsed = body
        return {
            "statusCode": raw.get("statusCode"),
            "body": parsed,
        }
    if isinstance(raw, dict):
        return raw
    return {"raw_result": str(raw)}


def _preview_only(run: IntegrationRun, note: str) -> dict[str, Any]:
    return {
        "execution_mode": run.execution_mode.value,
        "task_id": run.task_id,
        "preview_only": True,
        "note": note,
        "payload": run.payload,
    }


def _raise_for_error_result(result: dict[str, Any]) -> None:
    status_code = result.get("statusCode")
    if isinstance(status_code, int) and status_code >= 400:
        body = result.get("body")
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(str(body["error"]))
        raise RuntimeError(f"handler returned statusCode={status_code}")
    if result.get("success") is False:
        raise RuntimeError(str(result.get("message") or "task reported success=false"))
    body = result.get("body")
    if isinstance(body, dict) and body.get("success") is False:
        raise RuntimeError(str(body.get("message") or "task body reported success=false"))


def _adapter_a2(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    channel_name, work_title = parse_manual_request(
        str(run.payload.get("channel_name", "Test Channel")),
        str(run.payload.get("work_title", "Test Work")),
    )
    proposed_endpoint = "/work-approvals/request"
    proposed_url = f"https://aajtilnicgqywpmuuxtr.supabase.co/functions/v1/manuals-api{proposed_endpoint}"

    if run.execution_mode == ExecutionMode.DRY_RUN:
        log("A-2는 현재 manuals-api 실제 endpoint 대기 중인 stub입니다. channel_name/work_title 입력값만 검증합니다.")
        return {
            "execution_mode": run.execution_mode.value,
            "channel_name": channel_name,
            "work_title": work_title,
            "stub_only": True,
            "manuals_api_base_url": "https://aajtilnicgqywpmuuxtr.supabase.co/functions/v1/manuals-api",
            "proposed_endpoint": proposed_endpoint,
            "proposed_url": proposed_url,
            "next_step": "개발팀 endpoint 명세 수령 후 채널 보유 작품 조회 및 권한 부여 플로우 연결",
        }

    log("A-2 real-run도 현재는 stub only입니다. 실제 endpoint/작품 조회 API가 없어 외부 부작용 없이 종료합니다.")
    return {
        "execution_mode": run.execution_mode.value,
        "channel_name": channel_name,
        "work_title": work_title,
        "stub_only": True,
        "manuals_api_base_url": "https://aajtilnicgqywpmuuxtr.supabase.co/functions/v1/manuals-api",
        "proposed_endpoint": proposed_endpoint,
        "proposed_url": proposed_url,
        "implemented": False,
        "reason": "manuals-api 실제 endpoint 및 채널 보유 작품 조회 API 명세 대기",
    }


def _adapter_a3(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    handler = importlib.import_module("lambda.a3_naver_clip_monthly_handler").handler
    mode = run.payload.get("mode", "confirm")
    if run.execution_mode == ExecutionMode.DRY_RUN:
        mode = "confirm"
        log("A-3 dry-run은 confirm 모드로 고정합니다.")
    else:
        log(f"A-3를 mode={mode}로 실행합니다.")
    return _normalize_result(handler({"mode": mode}, None))


def _adapter_b2(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    if run.execution_mode == ExecutionMode.DRY_RUN:
        log("B-2는 아직 완전한 무해 dry-run을 지원하지 않아 설정 미리보기만 반환합니다.")
        return _preview_only(run, "B-2 currently requires a real crawl/report cycle for full validation.")

    handler = importlib.import_module("lambda.b2_weekly_report_handler").handler
    log("B-2 네이버 클립 성과보고를 real-run으로 실행합니다.")
    return _normalize_result(handler({"source": run.payload.get("source", "dashboard")}, None))


def _adapter_c1(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    if run.execution_mode == ExecutionMode.DRY_RUN:
        log("C-1 dry-run은 현재 설정 미리보기만 제공합니다. 실제 실행 시 리드 시트에 기록됩니다.")
        return _preview_only(run, "C-1 lead discovery still writes to the lead repository when executed.")

    handler = importlib.import_module("lambda.c1_lead_filter_handler").handler
    log("C-1 리드 발굴을 real-run으로 실행합니다.")
    return _normalize_result(handler(run.payload, None))


def _adapter_c2(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    if run.execution_mode == ExecutionMode.DRY_RUN:
        log("C-2 dry-run은 payload 미리보기만 제공합니다. 현재 핸들러는 실제 발송형입니다.")
        return _preview_only(run, "C-2 currently has no native no-send preview mode.")

    handler = importlib.import_module("lambda.c2_cold_email_handler").handler
    log("C-2 콜드메일 플로우를 real-run으로 실행합니다.")
    return _normalize_result(handler(run.payload, None))


def _adapter_c3(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    handler = importlib.import_module("lambda.c3_work_register_handler").handler
    payload = dict(run.payload)
    payload["dry_run"] = run.execution_mode == ExecutionMode.DRY_RUN
    log(f"C-3를 dry_run={payload['dry_run']}로 실행합니다.")
    return _normalize_result(handler(payload, None))


def _adapter_c4(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    if run.execution_mode == ExecutionMode.DRY_RUN:
        is_match = is_coupon_request(run.payload.get("text", ""))
        log("C-4 쿠폰 키워드 탐지만 검증했습니다. 시트 추가나 알림 발송은 하지 않았습니다.")
        return {
            "execution_mode": run.execution_mode.value,
            "preview_only": True,
            "is_coupon_request": is_match,
            "source": run.payload.get("source", "slack"),
        }

    handler = importlib.import_module("lambda.c4_coupon_notification_handler").handler
    log("C-4 쿠폰 알림 플로우를 real-run으로 실행합니다.")
    return _normalize_result(handler(run.payload, None))


def _adapter_d2(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    service = get_relief_request_service()
    items = run.payload.get(
        "items",
        [
            {
                "work_id": "work-1",
                "work_title": "Sample Work",
                "rights_holder_name": "Rights A",
                "channel_folder_name": run.payload.get("requester_channel_name", "Test Channel"),
            }
        ],
    )
    if run.execution_mode == ExecutionMode.DRY_RUN:
        rights_holders = sorted({item["rights_holder_name"] for item in items})
        log("D-2 미리보기만 생성했습니다. 요청 저장이나 메일 발송은 하지 않았습니다.")
        return {
            "execution_mode": run.execution_mode.value,
            "preview_only": True,
            "requester_channel_name": run.payload.get("requester_channel_name", "Test Channel"),
            "requester_email": run.payload.get("requester_email", "creator@example.com"),
            "item_count": len(items),
            "rights_holders": rights_holders,
            "auto_send_mails": bool(run.payload.get("auto_send_mails", False)),
        }

    log("D-2 저작권 소명 요청을 생성합니다.")
    request = service.create_request(
        requester_channel_name=run.payload.get("requester_channel_name", "Test Channel"),
        requester_email=run.payload.get("requester_email", "creator@example.com"),
        requester_notes=run.payload.get("requester_notes", "Integration dashboard request"),
        submitted_via=run.payload.get("submitted_via", "dashboard"),
        work_items=items,
    )
    result: dict[str, Any] = {
        "request_id": request.request_id,
        "status": request.status.value,
        "requester_channel_name": request.requester_channel_name,
    }
    if run.payload.get("auto_send_mails"):
        log("auto_send_mails=true 이므로 권리사 메일을 발송합니다.")
        send_result = service.send_rights_holder_mails(request.request_id)
        result["mail_result"] = {
            "attempted": send_result.attempted,
            "sent": send_result.sent,
            "failed": send_result.failed,
            "updated_status": send_result.updated_status.value,
        }
    return result


def _adapter_d3(run: IntegrationRun, log: Callable[[str], None]) -> dict[str, Any]:
    handler = importlib.import_module("lambda.d3_kakao_creator_onboarding_handler").handler
    dry_run = run.execution_mode == ExecutionMode.DRY_RUN
    log(f"D-3를 dry_run={dry_run}로 실행합니다.")
    return _normalize_result(handler({"dry_run": dry_run}, None))


class IntegrationTaskService:
    def __init__(
        self,
        repo: IIntegrationDashboardRepository | None = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._repo = repo or build_integration_dashboard_repository()
        self._executor = executor or ThreadPoolExecutor(max_workers=4)
        self._registry = self._build_registry()

    def list_task_specs(self) -> list[IntegrationTaskSpec]:
        return [spec for spec, _ in self._registry.values()]

    def list_runs(self, limit: int = 20) -> list[IntegrationRun]:
        return self._repo.list_runs(limit=limit)

    def get_run(self, run_id: str) -> IntegrationRun | None:
        return self._repo.get_run(run_id)

    def start_run(
        self,
        task_id: str,
        payload: dict[str, Any],
        *,
        execution_mode: ExecutionMode,
        approved: bool = False,
    ) -> IntegrationRun:
        if task_id not in self._registry:
            raise ValueError(f"unknown task_id: {task_id}")
        spec, adapter = self._registry[task_id]
        if execution_mode == ExecutionMode.REAL_RUN and spec.requires_approval and not approved:
            raise PermissionError(f"{task_id} requires approval before real execution")
        if execution_mode == ExecutionMode.DRY_RUN and not spec.supports_dry_run:
            raise ValueError(f"{task_id} does not support dry-run")

        now = _now()
        run = IntegrationRun(
            run_id=f"run-{uuid4().hex[:12]}",
            task_id=task_id,
            title=spec.title,
            payload=payload,
            status=IntegrationRunStatus.QUEUED,
            started_at=now,
            updated_at=now,
            execution_mode=execution_mode,
            requires_approval=spec.requires_approval,
            approved=approved,
        )
        self._repo.save_run(run)
        self._executor.submit(self._execute, run.run_id, adapter)
        return run

    def environment_summary(self) -> dict[str, Any]:
        return {
            "google_credentials_file": settings.GOOGLE_CREDENTIALS_FILE,
            "content_sheet_id": settings.CONTENT_SHEET_ID,
            "lead_sheet_id": settings.LEAD_SHEET_ID,
            "log_sheet_id": settings.LOG_SHEET_ID,
            "sender_email": settings.SENDER_EMAIL,
            "slack_error_channel": settings.SLACK_ERROR_CHANNEL,
            "dashboard_repository": settings.INTEGRATION_DASHBOARD_DB_TYPE,
            "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
            "tasks": [
                {
                    "task_id": spec.task_id,
                    "title": spec.title,
                    "targets": spec.targets,
                    "trigger_mode": spec.trigger_mode,
                    "requires_approval": spec.requires_approval,
                    "supports_dry_run": spec.supports_dry_run,
                    "sheet_links": spec.sheet_links,
                }
                for spec in self.list_task_specs()
            ],
        }

    def _execute(self, run_id: str, adapter: Adapter) -> None:
        run = self._repo.get_run(run_id)
        if run is None:
            return
        self._repo.update_run_status(run_id, IntegrationRunStatus.RUNNING)
        self._repo.append_log(run_id, f"[{run.task_id}] execution started in mode={run.execution_mode.value}")

        def _log(message: str) -> None:
            self._repo.append_log(run_id, message)

        try:
            result = adapter(run, _log)
            _raise_for_error_result(result)
            self._repo.append_log(run_id, f"[{run.task_id}] execution finished successfully")
            self._repo.update_run_status(run_id, IntegrationRunStatus.SUCCEEDED, result=result)
        except Exception as exc:
            self._repo.append_log(run_id, f"[{run.task_id}] execution failed: {exc}")
            self._repo.update_run_status(run_id, IntegrationRunStatus.FAILED, error=str(exc))

    def _build_registry(self) -> dict[str, tuple[IntegrationTaskSpec, Adapter]]:
        def _sheet_url(sheet_id: str) -> str:
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else ""

        def _drive_url(folder_id: str) -> str:
            return f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else ""

        log_url = _sheet_url(settings.LOG_SHEET_ID)

        return {
            "A-2": (
                IntegrationTaskSpec(
                    task_id="A-2",
                    title="A-2 작품사용신청 승인",
                    tab_group="homepage_auto",
                    description=(
                        "**현행:** Slack `#작품사용신청-알림` 채널에 크리에이터의 작품 사용 요청 메시지가 수신되면, 담당자가 수동으로 "
                        "Google Drive 권한 부여 및 승인 이메일을 작성·발송.\n\n"
                        "**구현내용:** 채널이 홈페이지에서 \"소유한 영상\" 중, \"작품사용승인\" 신청 (실제 endpoint 필요) → "
                        "채널명으로 크리에이터 이메일 조회 → Google Drive 파일에 Viewer 권한 자동 부여 → 승인 이메일 자동 발송."
                    ),
                    default_payload={
                        "channel_name": "Test Channel",
                        "work_title": "Test Work",
                        "manuals_api_base_url": "https://aajtilnicgqywpmuuxtr.supabase.co/functions/v1/manuals-api",
                        "proposed_endpoint": "/work-approvals/request",
                    },
                    targets=["Manuals API (stub)", "Google Sheets", "Google Drive", "Email"],
                    real_run_warning=(
                        "현재 A-2는 stub only 상태입니다.\n"
                        "manuals-api 실제 endpoint와 채널 보유 작품 조회 API 명세를 받은 뒤에만 권한 부여/메일 발송을 연결해야 합니다."
                    ),
                    sheet_links={
                        "크리에이터 시트": _sheet_url(settings.CREATOR_SHEET_ID),
                        "Drive 폴더": _drive_url(settings.DRIVE_FOLDER_ID),
                        "로그시트": log_url,
                    },
                ),
                _adapter_a2,
            ),
            "A-3": (
                IntegrationTaskSpec(
                    task_id="A-3",
                    title="A-3 네이버 클립 월별 집계",
                    tab_group="ops_admin",
                    description=(
                        "**현행:** 담당자가 구글폼 응답을 수동 확인 후 네이버 제출용 엑셀 파일을 직접 작성하여 이메일 발송.\n\n"
                        "**구현내용:** 정보 인입 구글 폼에서 홈페이지로 변경. 매월 말일 담당자에게 Slack으로 확인 요청 → "
                        "매월 1일 전월 구글폼 응답을 자동 취합하여 네이버 제출용 엑셀 파일을 생성하고 담당자에게 이메일 발송.\n\n"
                        "⇒ 전월 말일 담당자 확인 요청 알림. 이상 없을 시 그대로 메일 자동 전송."
                    ),
                    default_payload={"mode": "confirm"},
                    targets=["Google Sheets", "Slack", "Email"],
                    real_run_warning="send 모드로 실행하면 담당자에게 실제 월별 집계 메일이 발송됩니다.",
                    sheet_links={
                        "신청자 입력 시트": _sheet_url(settings.NAVER_APPLICANT_SHEET_ID),
                        "제출용 엑셀 원본 시트": _sheet_url(settings.NAVER_EXCEL_SHEET_ID),
                        "로그시트": log_url,
                    },
                ),
                _adapter_a3,
            ),
            "B-2": (
                IntegrationTaskSpec(
                    task_id="B-2",
                    title="B-2 네이버 클립 성과보고",
                    tab_group="ops_admin",
                    description=(
                        "**현행:** Octoparse 크롤링 후 일일이 수동 등록.\n\n"
                        "**구현내용:** Naver Clip GraphQL API로 해시태그별 클립 조회수를 자동 수집 → Google Sheets 갱신 → "
                        "권리사별 Looker Studio 대시보드 링크를 이메일 자동 발송."
                    ),
                    default_payload={"source": "dashboard"},
                    targets=["Google Sheets", "Email", "Slack"],
                    real_run_warning="성과 집계와 권리사 메일 발송이 실제로 수행됩니다.",
                    sheet_links={
                        "콘텐츠 시트": _sheet_url(settings.CONTENT_SHEET_ID),
                        "작품 관리 시트": _sheet_url(settings.CONTENT_SHEET_ID),
                        "성과 시트": _sheet_url(settings.PERFORMANCE_SHEET_ID),
                        "로그시트": log_url,
                    },
                ),
                _adapter_b2,
            ),
            "C-1": (
                IntegrationTaskSpec(
                    task_id="C-1",
                    title="C-1 리드 발굴",
                    tab_group="ops_admin",
                    description=(
                        "**구현 내용:** 신규 업로드 영상당 작품사용신청이 5개 이하일 시, 리드발굴 진행.\n"
                        "YouTube Data API v3 기반 2-Layer 구조로 드라마·영화 클립 채널을 자동 발굴·분류. "
                        "매월 1일 자동 실행하여 A/B/B? 등급 채널을 리드 시트에 upsert.\n\n"
                        "**트리거 흐름:**\n"
                        "① 신규 작품 등록\n"
                        "② 2주(7일)간 해당 작품의 '작품사용신청'이 5개 이하일 시,\n"
                        "③ '채널 부족 — 리드발굴 필요' 판단 → 관리자에게 Slack 알림 발송\n\n"
                        "**Slack 알림 포맷:**\n"
                        "{작품이름}의 이용 채널 수가 적어 리드발굴을 진행했습니다.\n"
                        "리드발굴 {TIMESTAMP} 진행,\n"
                        "{대표 TOP3 채널 이름}\n"
                        "자세한 정보는 SHEET를 확인해주세요. [시트링크]"
                    ),
                    default_payload={"_trigger_source": "dashboard"},
                    targets=["YouTube API", "Google Sheets", "Slack"],
                    real_run_warning="리드 시트에 실제 채널 데이터가 upsert됩니다.",
                    sheet_links={
                        "시드 채널 시트": _sheet_url(settings.SEED_CHANNEL_SHEET_ID),
                        "리드 시트": _sheet_url(settings.LEAD_SHEET_ID),
                        "로그시트": log_url,
                    },
                ),
                _adapter_c1,
            ),
            "C-2": (
                IntegrationTaskSpec(
                    task_id="C-2",
                    title="C-2 콜드메일 발송",
                    tab_group="ops_admin",
                    description=(
                        "**현행:** 구글 앱스크립트를 통해 대량 개인화 메일 발송중.\n\n"
                        "**구현내용:** 리드 시트에서 이메일 미발송 채널을 조회 → 채널 특성(장르·월간 조회수)에 맞게 개인화된 "
                        "콜드메일 생성 → AWS SES/SMTP 발송 → 발송 상태 시트 갱신."
                    ),
                    default_payload={"batch_size": 5, "min_monthly_views": 0, "dry_run": True},
                    targets=["Google Sheets", "Email", "Slack"],
                    requires_approval=True,
                    real_run_warning=(
                        "기본 payload는 dry_run=true 입니다.\n"
                        "실제 메일 발송은 승인 체크 + payload.dry_run=false 로 바꾼 경우에만 진행해야 합니다."
                    ),
                    sheet_links={
                        "리드 시트": _sheet_url(settings.LEAD_SHEET_ID),
                        "로그시트": log_url,
                    },
                ),
                _adapter_c2,
            ),
            "C-3": (
                IntegrationTaskSpec(
                    task_id="C-3",
                    title="C-3 작품 등록",
                    tab_group="ops_admin",
                    description=(
                        "대시보드에서 작품 제목 기준 웹서치 결과를 검토하고, 필드 값에 맞는 작품 정보를 입력해 등록합니다.\n\n"
                        "작품 제목, 권리사, 공개년도, 감독, 출연진, 플랫폼 URL, 트레일러 URL, 소스 다운로드 URL과 "
                        "가이드라인 항목까지 한 번에 확인하고 수정할 수 있습니다."
                    ),
                    default_payload={
                        "work_title": "21세기 대군부인",
                        "rights_holder_name": "웨이브",
                        "release_year": 2022,
                        "description": "작품 소개",
                        "director": "감독명",
                        "cast": "배우1, 배우2",
                        "genre": "드라마",
                        "video_type": "드라마",
                        "country": "한국",
                        "platforms": ["웨이브"],
                        "platform_video_url": "https://...",
                        "trailer_url": "https://...",
                        "source_download_url": "https://...",
                        "guideline": {
                            "source_provided_date": "2026-05-01",
                            "upload_available_date": "2026-05-10",
                            "usage_notes": "주의사항 내용",
                            "format_guide": "#신병 #드라마클립 문구 포함 필수",
                            "other_platforms": "네이버 클립 가능 / 카카오 숏폼 불가",
                            "logo_subtitle_provided": True,
                            "review_required": False,
                        },
                    },
                    targets=["Admin API", "Notion", "Slack"],
                    requires_approval=True,
                    real_run_warning="작품 메타데이터 등록과 노션 가이드 생성이 실제로 시도됩니다.",
                    sheet_links={"로그시트": log_url},
                ),
                _adapter_c3,
            ),
            "C-4": (
                IntegrationTaskSpec(
                    task_id="C-4",
                    title="C-4 쿠폰 알림",
                    tab_group="homepage_auto",
                    description=(
                        "**현행:** 크리에이터로 부터 카카오톡으로 쿠폰 신청 인입이 들어오면 관리자가 발급.\n\n"
                        "**구현 내용:** 크리에이터 측에서 웹에서 쿠폰 발급 요청 > 웹에서 바로 발급 되도록 진행."
                    ),
                    default_payload={
                        "source": "slack",
                        "creator_name": "Test Creator",
                        "text": "수익 100% 쿠폰 요청입니다.",
                    },
                    targets=["Google Sheets", "Slack", "Kakao (stub)"],
                    real_run_warning="쿠폰 요청 시트 추가와 Slack 알림이 실제로 수행됩니다.",
                    sheet_links={
                        "쿠폰 요청 시트": _sheet_url(settings.COUPON_SHEET_ID),
                        "로그시트": log_url,
                    },
                ),
                _adapter_c4,
            ),
            "D-2": (
                IntegrationTaskSpec(
                    task_id="D-2",
                    title="D-2 저작권 소명 공문 요청",
                    tab_group="ops_admin",
                    description=(
                        "**현행:** 카카오톡으로 저작권 소명 인입시, 관리자가 확인하여 수동 메일 작성 및 조취하고 있음.\n\n"
                        "**구현 내용:** 웹에 “저작권 소명 요청” 서비스 탭을 만들어, 관리자가 웹에서 소명 요청 리스트를 확인 할 수 있도록함.\n"
                        "메일 내용 또한 템플렛으로 지정하여 권리사 측으로 메일 송신.\n"
                        "회신 여부를 확인하여 완료 유무확인 및 공문 발송, 드라이브 업로드 자동화."
                    ),
                    default_payload={
                        "requester_channel_name": "Test Channel",
                        "requester_email": "creator@example.com",
                        "requester_notes": "Integration dashboard relief request",
                        "auto_send_mails": False,
                        "items": [
                            {
                                "work_id": "work-1",
                                "work_title": "Sample Work",
                                "rights_holder_name": "Rights A",
                                "channel_folder_name": "Test Channel",
                            }
                        ],
                    },
                    targets=["Relief Request Service", "Email", "Slack"],
                    requires_approval=True,
                    real_run_warning="auto_send_mails=true이면 권리사 메일이 실제로 발송됩니다.",
                    sheet_links={
                        "권리사 시트": _sheet_url(settings.RIGHTS_HOLDER_SHEET_ID),
                        "로그시트": log_url,
                    },
                ),
                _adapter_d2,
            ),
            "D-3": (
                IntegrationTaskSpec(
                    task_id="D-3",
                    title="D-3 카카오 크리에이터 온보딩",
                    tab_group="homepage_auto",
                    description=(
                        "**현행:** 카카오 오리지널 크리에이터 신규 입점 시 담당자가 구글폼 응답을 수동 취합하여 시트 입력 → "
                        "권한 요청 → 온보딩 안내 발송의 전 과정을 수동 처리.\n\n"
                        "**구현 내용:** 구글폼 응답을 '최종 리스트' 시트에 자동 입력하고 구독자 수 기반 규모 카테고리를 자동 계산 "
                        "(STEP 1 완료). STEP 2~5는 미결 사항 해소 후 단계별 구현 예정. "
                        "(단톡방 초대 및 월간 정기 정산)"
                    ),
                    default_payload={},
                    targets=["Google Sheets", "Drive"],
                    sheet_links={
                        "카카오 입력 시트": _sheet_url(settings.KAKAO_FORM_SHEET_ID),
                        "최종 리스트 시트": _sheet_url(settings.KAKAO_OUTPUT_SHEET_ID),
                        "로그시트": log_url,
                    },
                ),
                _adapter_d3,
            ),
        }


def build_integration_dashboard_repository() -> IIntegrationDashboardRepository:
    if (
        settings.INTEGRATION_DASHBOARD_DB_TYPE == "supabase"
        and settings.SUPABASE_URL
        and settings.SUPABASE_KEY
    ):
        return SupabaseIntegrationDashboardRepository(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_KEY,
        )
    return InMemoryIntegrationDashboardRepository()


def build_integration_task_service() -> IntegrationTaskService:
    return IntegrationTaskService(repo=build_integration_dashboard_repository())
