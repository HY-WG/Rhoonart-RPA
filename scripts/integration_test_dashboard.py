# -*- coding: utf-8 -*-
"""루나트 통합 테스트 대시보드.

9개 자동화 모듈을 브라우저에서 버튼 클릭 한 번으로 실행하고
실시간 로그 스트리밍 + 결과 JSON 을 확인합니다.

사용법:
    python scripts/integration_test_dashboard.py
    →  http://localhost:8888

환경변수 (선택):
    YOUTUBE_API_KEY        C-1 리드 발굴 실행 시 필요
    GOOGLE_CREDENTIALS_FILE  A-2, C-4 등 실 시트 접근 시 필요
    BACKOFFICE_PORT        D-2 링크 포트 (기본 8002)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pytz
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# ── 경로 설정 ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.core.notifiers.null_notifier import NullNotifier
from src.handlers.a2_work_approval import run as _a2_run
from src.handlers.a3_naver_clip_monthly import run as _a3_run, RunMode
from src.handlers.b2_weekly_report import run as _b2_run
from src.handlers.c1_lead_filter import run as _c1_run
from src.handlers.c2_cold_email import run as _c2_run
from src.handlers.c3_work_register import run as _c3_run
from src.handlers.c4_coupon_notification import run_on_slack_message as _c4_run
from src.handlers.d3_kakao_creator_onboarding import run as _d3_run
from src.models.work import Work
from src.core.clients.admin_api_client import StubAdminAPIClient
from tests.fakes import (
    FakeDriveService,
    FakeFormRepo,
    FakeLeadRepo,
    FakeLogRepo,
    FakeNotifier,
    FakePerformanceRepo,
    FakeRightsHolder,
    FakeSheetsClient,
    FakeSpreadsheet,
    FakeWorksheet,
)

KST = pytz.timezone("Asia/Seoul")
_BACKOFFICE_PORT = int(os.environ.get("BACKOFFICE_PORT", "8002"))

# ── 작업 정의 ──────────────────────────────────────────────────────────────────
TASKS: list[dict] = [
    {
        "key": "b2",
        "id":  "B-2",
        "name": "주간 성과 보고",
        "desc": "네이버 클립 크롤링 → 성과 시트 업데이트 → 권리사 이메일 발송",
        "tag": "성과",
        "params": [],
    },
    {
        "key": "c1",
        "id":  "C-1",
        "name": "리드 발굴",
        "desc": "YouTube Shorts 채널 탐색 → A/B/C 등급 분류 → 리드 시트 upsert",
        "tag": "리드",
        "params": [
            {"name": "api_key", "label": "YouTube API Key",
             "placeholder": "AIzaSy... (없으면 YOUTUBE_API_KEY 환경변수)", "default": ""},
        ],
    },
    {
        "key": "a2",
        "id":  "A-2",
        "name": "작품사용신청 승인",
        "desc": "Slack 메시지 → 크리에이터 이메일 조회 → Drive 권한 부여 → 이메일 발송",
        "tag": "승인",
        "params": [
            {"name": "message_text", "label": "Slack 메시지",
             "default": '채널: "테스트채널" 의 신규 영상 사용 요청이 있습니다.\n신병'},
        ],
    },
    {
        "key": "a3",
        "id":  "A-3",
        "name": "네이버 클립 월별",
        "desc": "구글폼 응답 취합 → 네이버 제출용 엑셀 생성 → 담당자 이메일 발송",
        "tag": "월별",
        "params": [
            {"name": "mode",          "label": "모드 (confirm/send)", "default": "send"},
            {"name": "manager_email", "label": "담당자 이메일",        "default": "test@example.com"},
        ],
    },
    {
        "key": "c2",
        "id":  "C-2",
        "name": "콜드메일 발송",
        "desc": "리드 시트에서 미발송 리드 조회 → 개인화 이메일 발송 → 상태 업데이트",
        "tag": "이메일",
        "params": [
            {"name": "batch_size", "label": "배치 크기", "default": "3"},
        ],
    },
    {
        "key": "c3",
        "id":  "C-3",
        "name": "신규 작품 등록",
        "desc": "레이블리 어드민에 작품 기본정보 등록 → 가이드라인 자동 설정",
        "tag": "등록",
        "params": [
            {"name": "work_title",         "label": "작품명",       "default": "신병"},
            {"name": "rights_holder_name", "label": "권리사명",     "default": "웨이브"},
            {"name": "dry_run",            "label": "Dry Run",      "default": "true"},
        ],
    },
    {
        "key": "d2",
        "id":  "D-2",
        "name": "저작권 소명 관리 API",
        "desc": "FastAPI 백오피스 — 소명 신청 접수·관리·권리사 메일 발송",
        "tag": "API",
        "params": [],
        "link": f"http://localhost:{_BACKOFFICE_PORT}/docs",
    },
    {
        "key": "d3",
        "id":  "D-3",
        "name": "카카오 온보딩 점검",
        "desc": "구글폼 응답 → 최종 리스트 시트 자동 입력 + 규모 카테고리 계산",
        "tag": "온보딩",
        "params": [
            {"name": "dry_run", "label": "Dry Run", "default": "true"},
        ],
    },
    {
        "key": "c4",
        "id":  "C-4",
        "name": "수익 쿠폰 신청 알림",
        "desc": "Slack 쿠폰 키워드 감지 → 처리 목록 기록 → 담당자 DM 발송",
        "tag": "쿠폰",
        "params": [
            {"name": "creator_name", "label": "크리에이터명", "default": "테스트 채널"},
            {"name": "message",      "label": "Slack 메시지", "default": "수익 100% 쿠폰 신청합니다"},
        ],
    },
]

# ── 실행 상태 ──────────────────────────────────────────────────────────────────
class RunState:
    def __init__(self, run_id: str, task_key: str) -> None:
        self.run_id       = run_id
        self.task_key     = task_key
        self.status       = "running"   # running | success | error
        self.result: Optional[dict] = None
        self.error: Optional[str]   = None
        self.log_lines: list[str]   = []
        self.started_at  = datetime.now(KST)
        self.finished_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "run_id":      self.run_id,
            "task_key":    self.task_key,
            "status":      self.status,
            "result":      self.result,
            "error":       self.error,
            "log_lines":   self.log_lines,
            "started_at":  self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class _ListHandler(logging.Handler):
    """logging.Handler → RunState.log_lines 에 추가."""

    def __init__(self, lines: list[str]) -> None:
        super().__init__()
        self._lines = lines

    def emit(self, record: logging.LogRecord) -> None:
        ts  = datetime.now(KST).strftime("%H:%M:%S")
        lvl = record.levelname[:4]
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        self._lines.append(f"[{ts}] {lvl}  {record.name.split('.')[-1]} — {msg}")


# ── 테스트 픽스처 헬퍼 ─────────────────────────────────────────────────────────

def _fake_lead_repo_with_data() -> FakeLeadRepo:
    from datetime import date
    from src.models.lead import Lead, Genre, EmailSentStatus
    leads = [
        Lead(
            channel_id="ch-test-1",
            channel_name="드라마클립채널",
            channel_url="https://youtube.com/@test1",
            platform="youtube",
            genre=Genre.DRAMA_MOVIE,
            monthly_shorts_views=5_000_000,
            subscribers=80_000,
            email="creator1@example.com",
            email_sent_status=EmailSentStatus.NOT_SENT,
            discovered_at=datetime.now(KST),
        ),
        Lead(
            channel_id="ch-test-2",
            channel_name="영화하이라이트",
            channel_url="https://youtube.com/@test2",
            platform="youtube",
            genre=Genre.DRAMA_MOVIE,
            monthly_shorts_views=3_000_000,
            subscribers=45_000,
            email="creator2@example.com",
            email_sent_status=EmailSentStatus.NOT_SENT,
            discovered_at=datetime.now(KST),
        ),
    ]
    return FakeLeadRepo(leads=leads, upsert_result=2)


def _fake_creator_sheets_client(channel_name: str, email: str) -> FakeSheetsClient:
    ws = FakeWorksheet(
        headers=["채널명", "이메일", "계약상태"],
        rows=[[channel_name, email, "계약완료"]],
    )
    return FakeSheetsClient({"fake-creator-sheet": FakeSpreadsheet(ws)})


def _fake_drive_with_file(work_title: str) -> FakeDriveService:
    return FakeDriveService(files=[
        {
            "id": "file-test-001",
            "name": f"{work_title} 원본 소스",
            "webViewLink": "https://drive.google.com/file/d/file-test-001/view",
        }
    ])


# ── Task 실행 함수 ─────────────────────────────────────────────────────────────

def _run_b2(run: RunState, params: dict) -> dict:
    """B-2: FakePerformanceRepo(contents=[]) → 크롤링 즉시 스킵, 결과 0건."""
    perf_repo = FakePerformanceRepo(
        contents=[],
        rights_holders=[
            FakeRightsHolder(holder_id="h1", name="웨이브x루나르트",   email="test-wavve@example.com",      dashboard_url="https://lookerstudio.google.com/test1"),
            FakeRightsHolder(holder_id="h2", name="판씨네마x루나르트", email="test-pans@example.com",       dashboard_url="https://lookerstudio.google.com/test2"),
        ],
    )
    return _b2_run(
        perf_repo=perf_repo,
        log_repo=FakeLogRepo(),
        email_notifier=NullNotifier(),
        slack_notifier=NullNotifier(),
    )


def _run_c1(run: RunState, params: dict) -> dict:
    """C-1: YouTube API Key 필수. 미설정 시 즉시 오류."""
    api_key = (
        params.get("api_key")
        or os.environ.get("YOUTUBE_API_KEY", "")
    )
    if not api_key:
        raise RuntimeError(
            "YOUTUBE_API_KEY 가 필요합니다. "
            "대시보드 params 에 입력하거나 .env 에 YOUTUBE_API_KEY 를 설정하세요."
        )
    from unittest.mock import patch
    with patch(
        "src.handlers.c1_lead_filter.load_seed_urls_from_sheet",
        return_value=["https://www.youtube.com/@test_seed"],
    ):
        return _c1_run(
            lead_repo=_fake_lead_repo_with_data(),
            log_repo=FakeLogRepo(),
            slack_notifier=NullNotifier(),
            api_key=api_key,
            seed_sheet_id="fake-seed-sheet",
            max_channels=20,
        )


def _run_a2(run: RunState, params: dict) -> dict:
    """A-2: FakeSheetsClient + FakeDriveService 로 전체 플로우 검증."""
    msg = params.get(
        "message_text",
        '채널: "테스트채널" 의 신규 영상 사용 요청이 있습니다.\n신병',
    )
    # Slack 파싱으로 채널명·작품명 추출 (미리 확인)
    from src.handlers.a2_work_approval import parse_slack_message
    try:
        channel_name, work_title = parse_slack_message(msg)
    except ValueError as e:
        raise RuntimeError(f"Slack 메시지 파싱 실패: {e}") from e

    slack_notifier = FakeNotifier()

    return _a2_run(
        slack_channel_id="C_TEST",
        slack_message_ts="1700000000.000001",
        slack_message_text=msg,
        sheets_client=_fake_creator_sheets_client(channel_name, "creator@example.com"),
        drive_service=_fake_drive_with_file(work_title),
        email_notifier=NullNotifier(),
        slack_notifier=slack_notifier,
        creator_sheet_id="fake-creator-sheet",
        drive_folder_id="fake-folder",
        sender_email="test@example.com",
    )


def _run_a3(run: RunState, params: dict) -> dict:
    """A-3: FakeFormRepo(3개 신청자) 로 confirm/send 양 모드 검증."""
    mode_str = params.get("mode", "send")
    try:
        mode = RunMode(mode_str)
    except ValueError:
        raise RuntimeError(f"지원하지 않는 모드: {mode_str!r} (confirm / send)")

    manager_email = params.get("manager_email", "test@example.com")
    year, month   = datetime.now(KST).year, datetime.now(KST).month

    applicants = [
        {"채널명": "채널A", "유튜브 채널 URL": "https://youtube.com/@a", "연락처이메일": "a@ex.com"},
        {"채널명": "채널B", "유튜브 채널 URL": "https://youtube.com/@b", "연락처이메일": "b@ex.com"},
        {"채널명": "채널C", "유튜브 채널 URL": "https://youtube.com/@c", "연락처이메일": "c@ex.com"},
    ]
    return _a3_run(
        form_repo=FakeFormRepo(applicants=applicants),
        log_repo=FakeLogRepo(),
        slack_notifier=NullNotifier(),
        email_notifier=NullNotifier(),
        mode=mode,
        manager_email=manager_email,
        target_year=year,
        target_month=month,
    )


def _run_c2(run: RunState, params: dict) -> dict:
    """C-2: FakeLeadRepo(2개 리드) + NullNotifier → 발송 시뮬레이션."""
    try:
        batch_size = int(params.get("batch_size", 3))
    except ValueError:
        batch_size = 3

    return _c2_run(
        lead_repo=_fake_lead_repo_with_data(),
        log_repo=FakeLogRepo(),
        email_notifier=NullNotifier(),
        slack_notifier=NullNotifier(),
        batch_size=batch_size,
    )


def _run_c3(run: RunState, params: dict) -> dict:
    """C-3: StubAdminAPIClient + dry_run=True → 작품 등록 시뮬레이션."""
    dry_run    = str(params.get("dry_run", "true")).lower() != "false"
    work_title = params.get("work_title", "신병") or "신병"
    rights     = params.get("rights_holder_name", "웨이브") or "웨이브"

    work = Work(
        work_title=work_title,
        rights_holder_name=rights,
        release_year=2022,
        genre="드라마",
        cast="배우1, 배우2",
    )
    from src.models.work_guideline import WorkGuideline
    guideline = WorkGuideline(
        usage_notes="가이드라인 테스트",
        review_required=True,
    )
    return _c3_run(
        work=work,
        guideline=guideline,
        admin_client=StubAdminAPIClient(),
        dry_run=dry_run,
    )


def _run_d3(run: RunState, params: dict) -> dict:
    """D-3: FakeWorksheet(폼 4건, 기존 1건) → 중복 제외 3건 추가."""
    dry_run = str(params.get("dry_run", "true")).lower() != "false"
    form_headers = [
        "타임스탬프", "채널명", "유튜브 채널 URL",
        "카카오 숏폼 채널명", "구독자 수", "장르",
        "담당자명", "담당자 이메일", "담당자 연락처",
    ]
    form_rows = [
        ["2024/05/01 오후 3:05:00", "신규채널A", "https://yt.com/@a", "a_kakao", "150000", "드라마", "홍길동", "a@ex.com", "010-1234-5678"],
        ["2024/05/01 오후 3:10:00", "기존채널Z", "https://yt.com/@z", "z_kakao", "50000",  "영화",  "김철수", "z@ex.com", "010-9999-0000"],
        ["2024/05/01 오후 3:15:00", "신규채널B", "https://yt.com/@b", "b_kakao", "25000",  "드라마", "이영희", "b@ex.com", "010-5555-6666"],
        ["2024/05/01 오후 3:20:00", "신규채널C", "https://yt.com/@c", "c_kakao", "1200000","예능",  "박민준", "c@ex.com", "010-7777-8888"],
    ]
    form_ws = FakeWorksheet(headers=form_headers, rows=form_rows)

    out_headers = [
        "신청일시", "채널명", "유튜브 채널 URL",
        "카카오 숏폼 채널명", "구독자 수", "규모", "장르",
        "담당자명", "담당자 이메일", "담당자 연락처",
    ]
    out_rows = [["2024/04/01", "기존채널Z", "https://yt.com/@z", "z_kakao", "50000", "마이크로", "영화", "김철수", "z@ex.com", "010-9999-0000"]]
    output_ws = FakeWorksheet(headers=out_headers, rows=out_rows)

    return _d3_run(form_ws=form_ws, output_ws=output_ws, dry_run=dry_run)


def _run_c4(run: RunState, params: dict) -> dict:
    """C-4: 쿠폰 키워드가 있는 메시지 → FakeNotifier 로 DM 시뮬레이션."""
    creator_name = params.get("creator_name", "테스트 채널")
    message      = params.get("message", "수익 100% 쿠폰 신청합니다")
    notifier     = FakeNotifier()

    with _patch_c4_sheets():
        return _c4_run(
            creator_name=creator_name,
            slack_message_text=message,
            sheets_client=None,        # _patch_c4_sheets 가 sheets 접근을 패치
            coupon_sheet_id="fake-coupon-sheet",
            coupon_sheet_tab="쿠폰신청",
            slack_notifier=notifier,
            admin_slack_user_id="U_TEST",
            labelive_admin_url="https://labelive.io/admin",
        )


def _patch_c4_sheets():
    """C-4 내부의 Google Sheets append 호출을 무시하는 패처."""
    from unittest.mock import patch
    return patch(
        "src.handlers.c4_coupon_notification._append_to_coupon_sheet",
        return_value=True,
    )


# ── Task 라우터 ────────────────────────────────────────────────────────────────
_RUNNERS: dict[str, Any] = {
    "b2": _run_b2,
    "c1": _run_c1,
    "a2": _run_a2,
    "a3": _run_a3,
    "c2": _run_c2,
    "c3": _run_c3,
    "d3": _run_d3,
    "c4": _run_c4,
}


def _execute_task(task_key: str, run: RunState, params: dict) -> None:
    """백그라운드 스레드에서 실행. 로그를 run.log_lines 에 수집."""
    handler = _ListHandler(run.log_lines)
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        runner = _RUNNERS.get(task_key)
        if runner is None:
            raise ValueError(f"알 수 없는 task_key: {task_key!r}")
        run.result = runner(run, params)
        run.status = "success"
        run.log_lines.append(
            f"[{datetime.now(KST).strftime('%H:%M:%S')}] ✅  완료 → {json.dumps(run.result, ensure_ascii=False)}"
        )
    except Exception as exc:
        run.error  = str(exc)
        run.status = "error"
        run.log_lines.append(
            f"[{datetime.now(KST).strftime('%H:%M:%S')}] ❌  오류 → {exc}"
        )
    finally:
        root.removeHandler(handler)
        run.finished_at = datetime.now(KST)


# ── FastAPI 앱 ─────────────────────────────────────────────────────────────────
app     = FastAPI(title="루나트 통합 테스트 대시보드")
_runs:  dict[str, RunState]  = {}
_pool   = ThreadPoolExecutor(max_workers=2)
_lock   = threading.Lock()


class RunRequest(BaseModel):
    params: dict = {}


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(content=_HTML)


@app.post("/api/run/{task_key}")
async def run_task(task_key: str, body: RunRequest) -> dict:
    task = next((t for t in TASKS if t["key"] == task_key), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task_key={task_key!r} 없음")
    if task.get("link"):
        raise HTTPException(status_code=400, detail="외부 링크 작업은 실행 불필요")

    run_id = uuid.uuid4().hex[:8]
    run    = RunState(run_id=run_id, task_key=task_key)
    with _lock:
        _runs[run_id] = run

    _pool.submit(_execute_task, task_key, run, body.params)
    return {"run_id": run_id, "task_key": task_key}


@app.get("/api/stream/{run_id}")
async def stream_logs(run_id: str) -> StreamingResponse:
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail=f"run_id={run_id!r} 없음")
    run = _runs[run_id]

    async def generate():
        last_idx = 0
        while True:
            # 새 로그 라인 방출
            while last_idx < len(run.log_lines):
                line = run.log_lines[last_idx]
                yield f"data: {json.dumps({'type': 'log', 'msg': line}, ensure_ascii=False)}\n\n"
                last_idx += 1

            if run.status != "running":
                yield (
                    f"data: {json.dumps({'type': 'done', 'status': run.status, 'result': run.result, 'error': run.error}, ensure_ascii=False)}\n\n"
                )
                break
            await asyncio.sleep(0.15)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/runs")
async def list_runs() -> list[dict]:
    return [r.to_dict() for r in _runs.values()]


@app.get("/api/tasks")
async def list_tasks() -> list[dict]:
    return TASKS


# ── HTML 템플릿 ────────────────────────────────────────────────────────────────
_TASKS_JSON = json.dumps(TASKS, ensure_ascii=False)

_HTML = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>루나트 통합 테스트 대시보드</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  .card-idle    {{ border-color: #e5e7eb; }}
  .card-running {{ border-color: #3b82f6; box-shadow: 0 0 0 2px #bfdbfe; animation: pulse 1.5s infinite; }}
  .card-success {{ border-color: #10b981; }}
  .card-error   {{ border-color: #ef4444; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:.7}} }}
  .log-line {{ font-family: 'Consolas','Courier New',monospace; font-size:12px; white-space: pre-wrap; word-break: break-all; }}
  .badge-A {{ background:#dcfce7; color:#166534; }}
  .badge-B {{ background:#dbeafe; color:#1e40af; }}
  .badge-API {{ background:#f3e8ff; color:#6b21a8; }}
  details > summary {{ cursor: pointer; user-select: none; }}
</style>
</head>
<body class="bg-gray-100 min-h-screen">

<!-- 헤더 -->
<header class="bg-white border-b shadow-sm sticky top-0 z-10">
  <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <span class="text-xl font-bold text-gray-800">🤖 루나트 통합 테스트 대시보드</span>
      <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-semibold">TEST MODE</span>
    </div>
    <div class="flex items-center gap-4 text-sm text-gray-500">
      <span id="running-badge" class="hidden bg-blue-50 text-blue-600 px-2 py-1 rounded font-medium">⚡ 실행 중...</span>
      <button onclick="clearGlobalLog()" class="text-gray-400 hover:text-red-500">🗑 전체 로그 지우기</button>
    </div>
  </div>
  <!-- 탭 -->
  <div class="max-w-7xl mx-auto px-4 flex gap-1 border-t">
    <button onclick="showTab('dashboard')" id="tab-dashboard" class="tab-btn px-4 py-2 text-sm font-medium border-b-2 border-blue-500 text-blue-600">대시보드</button>
    <button onclick="showTab('agent')" id="tab-agent" class="tab-btn px-4 py-2 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">AI Agent 설계</button>
  </div>
</header>

<!-- ── TAB 1: 대시보드 ── -->
<div id="tab-dashboard-panel" class="max-w-7xl mx-auto px-4 py-6">
  <div id="task-grid" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"></div>

  <!-- 전역 로그 패널 -->
  <div class="mt-6 bg-white rounded-xl border shadow-sm">
    <div class="flex items-center justify-between px-4 py-3 border-b">
      <span class="font-semibold text-gray-700">📋 실행 로그</span>
      <button onclick="clearGlobalLog()" class="text-xs text-gray-400 hover:text-red-500">지우기</button>
    </div>
    <div id="global-log" class="p-4 bg-gray-950 rounded-b-xl h-56 overflow-y-auto space-y-0.5">
      <p class="log-line text-gray-500">여기에 실행 로그가 표시됩니다...</p>
    </div>
  </div>
</div>

<!-- ── TAB 2: AI Agent 설계 ── -->
<div id="tab-agent-panel" class="hidden max-w-5xl mx-auto px-4 py-6 space-y-6">

  <div class="bg-white rounded-xl border shadow-sm p-6">
    <h2 class="text-lg font-bold text-gray-800 mb-2">📐 AI Agent 고도화 로드맵</h2>
    <p class="text-sm text-gray-500">현재 규칙 기반 RPA에서 <strong>ReAct 패러다임 기반 AI Agent</strong>로 전환하는 설계안입니다.</p>
  </div>

  <!-- 아키텍처 다이어그램 -->
  <div class="bg-white rounded-xl border shadow-sm p-6">
    <h3 class="font-semibold text-gray-700 mb-3">1. 전체 아키텍처</h3>
    <pre class="bg-gray-950 text-green-300 text-xs p-4 rounded-lg overflow-x-auto">
┌──────────────────── Input Gateway ─────────────────────┐
│  이메일 / Slack / HTTP / Cron                           │
│  → parse_intent() → InputEvent(task_id, params)        │
└────────────────────────┬───────────────────────────────┘
                         │
            ┌────────────▼────────────┐
            │   RPA Supervisor Agent  │  ← Anthropic Claude API
            │   (ReAct Loop)          │
            │                         │
            │  REASON → ACTION → OBS  │
            │       └── LOOP ──┘      │
            └────────────┬────────────┘
                         │  dispatch_tool(task_id, params)
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ Tool:   │    │ Tool:   │    │ Tool:   │
    │ run_b2  │    │ run_a2  │    │ run_c3  │  ... (9개)
    └────┬────┘    └────┬────┘    └────┬────┘
         │              │              │
         ▼              ▼              ▼
    ┌─────────────────────────────────────┐
    │  Repository Layer (IXxxRepository)  │
    │  Sheets / Supabase (교체 가능)       │
    └─────────────────────────────────────┘
                         │
            ┌────────────▼────────────┐
            │  Human-in-the-Loop Gate │
            │  (승인 필요 액션 검토)    │
            │  approve / reject / edit │
            └─────────────────────────┘</pre>
  </div>

  <!-- 구현 원칙 -->
  <div class="grid md:grid-cols-2 gap-4">
    <div class="bg-white rounded-xl border shadow-sm p-5">
      <h3 class="font-semibold text-gray-700 mb-3">2. ReAct 패러다임</h3>
      <div class="space-y-2 text-sm text-gray-600">
        <div class="flex gap-2"><span class="bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded font-mono text-xs">REASON</span><span>현재 상태 분석 → 다음 행동 결정</span></div>
        <div class="flex gap-2"><span class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-mono text-xs">ACTION</span><span>Tool 호출 (run_b2, run_a2 ...)</span></div>
        <div class="flex gap-2"><span class="bg-green-100 text-green-700 px-2 py-0.5 rounded font-mono text-xs">OBSERVE</span><span>결과 수신 → 다음 REASON 으로</span></div>
        <hr class="my-2">
        <p class="text-xs text-gray-400">Claude API tool_use 기능으로 구현. 각 Handler의 run() 함수를 Tool 로 래핑. 최대 반복(max_iterations=10)으로 무한 루프 방지.</p>
      </div>
    </div>
    <div class="bg-white rounded-xl border shadow-sm p-5">
      <h3 class="font-semibold text-gray-700 mb-3">3. Human-in-the-Loop</h3>
      <div class="space-y-2 text-sm text-gray-600">
        <p><strong>승인 필요 액션:</strong></p>
        <ul class="list-disc list-inside space-y-1 text-xs">
          <li>A-2: Drive 권한 부여 → 이메일 발송 전 검토</li>
          <li>C-2: 콜드메일 50건 이상 발송 전 확인</li>
          <li>C-3: 작품 등록 → 가이드라인 내용 검토</li>
          <li>D-2: 권리사 공문 발송 전 내용 확인</li>
        </ul>
        <hr class="my-2">
        <p class="text-xs text-gray-400">Agent 가 pending_approval 상태로 중단 → 담당자 Slack DM → approve/reject 응답 수신 → 재개. 타임아웃(24h) 시 자동 취소.</p>
      </div>
    </div>
    <div class="bg-white rounded-xl border shadow-sm p-5">
      <h3 class="font-semibold text-gray-700 mb-3">4. Input Gateway</h3>
      <div class="space-y-2 text-sm text-gray-600">
        <p class="text-xs font-mono bg-gray-100 p-2 rounded">email / slack → parse_intent() → InputEvent</p>
        <ul class="list-disc list-inside space-y-1 text-xs">
          <li><strong>이메일:</strong> 권리사 회신 파싱 → C-3 가이드라인 등록</li>
          <li><strong>Slack:</strong> 작품사용신청 → A-2 승인 플로우</li>
          <li><strong>Slack:</strong> 쿠폰 키워드 → C-4 알림 플로우</li>
          <li><strong>HTTP:</strong> 웹 대시보드 버튼 → 즉시 실행</li>
          <li><strong>Cron:</strong> 주간/월별 자동 실행</li>
        </ul>
        <p class="text-xs text-gray-400 mt-2">LLM 기반 intent 파싱으로 불규칙한 메시지 형식에 강건하게 대응.</p>
      </div>
    </div>
    <div class="bg-white rounded-xl border shadow-sm p-5">
      <h3 class="font-semibold text-gray-700 mb-3">5. Supabase 마이그레이션 전략</h3>
      <div class="space-y-2 text-sm text-gray-600">
        <p class="text-xs">Repository Pattern 이 이미 적용되어 있어, 교체 시 <strong>한 줄만 수정</strong>합니다:</p>
        <p class="text-xs font-mono bg-gray-100 p-2 rounded">
# Before: Google Sheets<br>
repo = SheetLeadRepository(ws)<br><br>
# After: Supabase<br>
repo = SupabaseLeadRepository(client)
        </p>
        <p class="text-xs text-gray-400">ILeadRepository 인터페이스가 동일하므로 Handler 코드 무변경.</p>
      </div>
    </div>
  </div>

  <!-- 파일 목록 -->
  <div class="bg-white rounded-xl border shadow-sm p-5">
    <h3 class="font-semibold text-gray-700 mb-3">6. 구현 파일 목록</h3>
    <div class="grid md:grid-cols-2 gap-3 text-xs font-mono">
      <div class="bg-gray-50 p-3 rounded space-y-1">
        <p class="font-semibold text-gray-500 mb-1">Agent 코어</p>
        <p class="text-blue-700">src/agents/base.py</p>
        <p class="text-sm text-gray-400 pl-2">AbstractAgent: ReAct 루프, tool_use 디스패치</p>
        <p class="text-blue-700">src/agents/input_gateway.py</p>
        <p class="text-sm text-gray-400 pl-2">InputGateway: 이메일·Slack → InputEvent 파싱</p>
        <p class="text-blue-700">src/agents/tools.py</p>
        <p class="text-sm text-gray-400 pl-2">ToolRegistry: 9개 핸들러를 Tool 스펙으로 래핑</p>
        <p class="text-blue-700">src/agents/rpa_supervisor.py</p>
        <p class="text-sm text-gray-400 pl-2">RPASupervisorAgent: 최종 오케스트레이터</p>
      </div>
      <div class="bg-gray-50 p-3 rounded space-y-1">
        <p class="font-semibold text-gray-500 mb-1">통합 테스트</p>
        <p class="text-green-700">scripts/integration_test_dashboard.py</p>
        <p class="text-sm text-gray-400 pl-2">이 파일 — 9개 모듈 브라우저 테스트 UI</p>
        <p class="text-green-700">tests/test_c3_work_register.py</p>
        <p class="text-sm text-gray-400 pl-2">C-3 단위 테스트 (15개 케이스)</p>
        <p class="text-green-700">tests/test_d3_kakao_creator_onboarding.py</p>
        <p class="text-sm text-gray-400 pl-2">D-3 단위 테스트 (27개 케이스)</p>
      </div>
    </div>
  </div>
</div>

<!-- 작업 파라미터 모달 -->
<div id="params-modal" class="hidden fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
  <div class="bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 p-6">
    <h3 id="modal-title" class="font-bold text-gray-800 mb-4 text-lg"></h3>
    <div id="modal-fields" class="space-y-3 mb-5"></div>
    <div class="flex gap-3 justify-end">
      <button onclick="closeModal()" class="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">취소</button>
      <button onclick="submitModal()" class="px-4 py-2 rounded-lg text-sm bg-blue-600 text-white hover:bg-blue-700 font-semibold">▶ 실행</button>
    </div>
  </div>
</div>

<script>
const TASKS = {_TASKS_JSON};
let _pendingTaskKey = null;

/* ── 탭 전환 ── */
function showTab(name) {{
  ['dashboard','agent'].forEach(t => {{
    document.getElementById('tab-'+t+'-panel').classList.toggle('hidden', t!==name);
    const btn = document.getElementById('tab-'+t);
    btn.classList.toggle('border-blue-500', t===name);
    btn.classList.toggle('text-blue-600',   t===name);
    btn.classList.toggle('border-transparent', t!==name);
    btn.classList.toggle('text-gray-500',   t!==name);
  }});
}}

/* ── 카드 렌더링 ── */
const tagColor = {{
  '성과':'bg-emerald-100 text-emerald-700',
  '리드':'bg-sky-100 text-sky-700',
  '승인':'bg-violet-100 text-violet-700',
  '월별':'bg-amber-100 text-amber-700',
  '이메일':'bg-pink-100 text-pink-700',
  '등록':'bg-indigo-100 text-indigo-700',
  'API':'bg-purple-100 text-purple-700',
  '온보딩':'bg-teal-100 text-teal-700',
  '쿠폰':'bg-orange-100 text-orange-700',
}};

function buildGrid() {{
  const grid = document.getElementById('task-grid');
  TASKS.forEach(t => {{
    const div = document.createElement('div');
    div.id = 'card-'+t.key;
    div.className = 'bg-white rounded-xl border-2 card-idle p-5 flex flex-col gap-3 transition-all';
    const tc = tagColor[t.tag] || 'bg-gray-100 text-gray-600';
    const btn = t.link
      ? `<a href="${{t.link}}" target="_blank" class="flex-1 px-3 py-2 rounded-lg text-sm font-semibold bg-purple-600 text-white hover:bg-purple-700 text-center">🔗 열기</a>`
      : `<button onclick="openModal('${{t.key}}')" class="flex-1 px-3 py-2 rounded-lg text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700">▶ 실행</button>`;
    div.innerHTML = `
      <div class="flex items-start justify-between">
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="font-mono text-xs font-bold text-gray-400">${{t.id}}</span>
            <span class="text-xs px-1.5 py-0.5 rounded ${{tc}}">${{t.tag}}</span>
          </div>
          <p class="font-semibold text-gray-800">${{t.name}}</p>
        </div>
        <span id="status-${{t.key}}" class="text-lg">○</span>
      </div>
      <p class="text-xs text-gray-500 leading-relaxed">${{t.desc}}</p>
      <div class="flex gap-2 mt-auto">
        ${{btn}}
        <button onclick="toggleLog('${{t.key}}')" class="px-3 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-100 border">📋</button>
      </div>
      <div id="log-${{t.key}}" class="hidden bg-gray-950 rounded-lg p-3 max-h-40 overflow-y-auto text-xs space-y-0.5"></div>
      <div id="result-${{t.key}}" class="hidden text-xs bg-gray-50 rounded p-2 font-mono text-gray-700 max-h-24 overflow-y-auto"></div>
    `;
    grid.appendChild(div);
  }});
}}
buildGrid();

/* ── 모달 ── */
function openModal(key) {{
  const t = TASKS.find(x => x.key === key);
  if (!t) return;
  _pendingTaskKey = key;
  document.getElementById('modal-title').textContent = t.id + ' ' + t.name + ' 실행';
  const fields = document.getElementById('modal-fields');
  fields.innerHTML = '';
  if (t.params.length === 0) {{
    fields.innerHTML = '<p class="text-sm text-gray-500">파라미터가 없습니다. 바로 실행합니다.</p>';
  }} else {{
    t.params.forEach(p => {{
      const row = document.createElement('div');
      row.innerHTML = `
        <label class="block text-xs font-medium text-gray-600 mb-1">${{p.label}}</label>
        <textarea id="param-${{p.name}}" rows="2"
          class="w-full border rounded-lg px-3 py-2 text-sm resize-y font-mono"
          placeholder="${{p.placeholder||p.default||''}}"
        >${{p.default||''}}</textarea>
      `;
      fields.appendChild(row);
    }});
  }}
  document.getElementById('params-modal').classList.remove('hidden');
}}

function closeModal() {{
  document.getElementById('params-modal').classList.add('hidden');
  _pendingTaskKey = null;
}}

function submitModal() {{
  if (!_pendingTaskKey) return;
  const t = TASKS.find(x => x.key === _pendingTaskKey);
  const params = {{}};
  (t.params||[]).forEach(p => {{
    const el = document.getElementById('param-'+p.name);
    if (el) params[p.name] = el.value;
  }});
  closeModal();
  runTask(_pendingTaskKey, params);
}}

document.getElementById('params-modal').addEventListener('click', e => {{
  if (e.target === document.getElementById('params-modal')) closeModal();
}});

/* ── Task 실행 & SSE ── */
async function runTask(key, params={{}}) {{
  setCardStatus(key, 'running');
  clearCardLog(key);
  document.getElementById('result-'+key).classList.add('hidden');
  document.getElementById('running-badge').classList.remove('hidden');

  const res = await fetch('/api/run/'+key, {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{params}}),
  }});
  if (!res.ok) {{
    const err = await res.json();
    appendLog(key, '❌ ' + (err.detail||'오류'));
    setCardStatus(key, 'error');
    document.getElementById('running-badge').classList.add('hidden');
    return;
  }}
  const {{run_id}} = await res.json();
  const es = new EventSource('/api/stream/'+run_id);
  es.onmessage = e => {{
    const d = JSON.parse(e.data);
    if (d.type === 'log') {{
      appendLog(key, d.msg);
    }} else if (d.type === 'done') {{
      setCardStatus(key, d.status);
      if (d.result) {{
        const el = document.getElementById('result-'+key);
        el.textContent = JSON.stringify(d.result, null, 2);
        el.classList.remove('hidden');
      }}
      document.getElementById('running-badge').classList.add('hidden');
      es.close();
    }}
  }};
  es.onerror = () => {{
    appendLog(key, '⚡ SSE 연결 종료');
    document.getElementById('running-badge').classList.add('hidden');
    es.close();
  }};
}}

/* ── 카드 상태 ── */
const STATUS_ICON = {{idle:'○', running:'🔵', success:'✅', error:'❌'}};
function setCardStatus(key, status) {{
  const card = document.getElementById('card-'+key);
  const icon = document.getElementById('status-'+key);
  if (!card || !icon) return;
  card.className = card.className.replace(/card-\w+/, 'card-'+status);
  icon.textContent = STATUS_ICON[status]||'○';
}}

function appendLog(key, msg) {{
  const el = document.getElementById('log-'+key);
  if (el) {{
    const p = document.createElement('p');
    p.className = 'log-line ' + (msg.includes('❌')||msg.includes('ERROR')?'text-red-400':msg.includes('✅')?'text-green-400':'text-gray-300');
    p.textContent = msg;
    el.appendChild(p);
    el.scrollTop = el.scrollHeight;
    el.classList.remove('hidden');
  }}
  // 전역 로그
  const gl = document.getElementById('global-log');
  const gp = document.createElement('p');
  gp.className = 'log-line ' + (msg.includes('❌')||msg.includes('ERROR')?'text-red-400':msg.includes('✅')?'text-green-400':'text-gray-300');
  const badge = `<span class="text-gray-500 mr-1">[{{key.toUpperCase()}}]</span>`;
  gp.innerHTML = badge + msg.replace(/</g,'&lt;');
  gl.appendChild(gp);
  gl.scrollTop = gl.scrollHeight;
}}

function clearCardLog(key) {{
  const el = document.getElementById('log-'+key);
  if (el) el.innerHTML = '';
}}

function toggleLog(key) {{
  const el = document.getElementById('log-'+key);
  if (el) el.classList.toggle('hidden');
}}

function clearGlobalLog() {{
  const gl = document.getElementById('global-log');
  gl.innerHTML = '<p class="log-line text-gray-500">로그가 지워졌습니다.</p>';
}}
</script>
</body>
</html>"""

# ── 진입점 ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("DASHBOARD_PORT", "8888"))
    print(f"\n  🚀  통합 테스트 대시보드 →  http://localhost:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
