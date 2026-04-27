# -*- coding: utf-8 -*-
"""루나트 RPA — HTTP POST 통합 트리거 서버.

A-2, B-2, C-1, C-2 자동화 업무를 외부 HTTP POST 요청으로 실행한다.

실행 방법:
    cd C:\\Users\\mung9\\IdeaProjects\\rhoonart-rpa
    python -m src.api.rpa_server
    # 또는
    uvicorn src.api.rpa_server:app --port 8000 --reload

엔드포인트 목록:
    GET  /health                 — 서버 상태 확인
    POST /api/a2/trigger         — A-2 작품사용신청 승인
    POST /api/b2/trigger         — B-2 주간 성과 보고
    POST /api/c1/trigger         — C-1 리드 발굴 (YouTube Shorts)
    POST /api/c2/trigger         — C-2 콜드메일 발송
    GET  /api/tasks/{task_id}    — 백그라운드 태스크 결과 조회

인증:
    요청 헤더에 X-RPA-Token 포함 (값: .env의 X_INTERN_TOKEN)
    미설정 시 인증 없이 동작 (개발 모드)

Google 인증:
    credentials.json 형식 자동 감지 (service_account / OAuth2)
    OAuth2: 최초 실행 시 브라우저 인증 1회 필요
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Optional

import pytz
import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from src.api.deps import build_google_creds
from src.config import settings
from src.core.logger import CoreLogger
from src.core.notifiers.null_notifier import NullNotifier
from src.models.lead import Genre

log = CoreLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

# ── 환경 변수 (src.config.Settings 에서 일괄 관리) ────────────────────────────
_RPA_TOKEN          = settings.X_INTERN_TOKEN
_CREDS_FILE         = settings.GOOGLE_CREDENTIALS_FILE

# A-2
_CREATOR_SHEET_ID   = settings.CREATOR_SHEET_ID
_DRIVE_FOLDER_ID    = settings.DRIVE_FOLDER_ID
_ADMIN_API_BASE_URL = settings.ADMIN_API_BASE_URL

# B-2
_CONTENT_SHEET_ID   = settings.CONTENT_SHEET_ID
_PERF_SHEET_ID      = settings.PERFORMANCE_SHEET_ID
_LOOKER_DASHBOARDS  = settings.looker_dashboards

# C-1
_YOUTUBE_API_KEY    = settings.YOUTUBE_API_KEY
_SEED_SHEET_ID      = settings.SEED_CHANNEL_SHEET_ID
_SEED_SHEET_GID     = settings.SEED_CHANNEL_GID
_LEAD_SHEET_ID      = settings.LEAD_SHEET_ID

# C-2
_SENDER_EMAIL       = settings.SENDER_EMAIL
_SENDER_NAME        = settings.SENDER_NAME
_USE_SES            = settings.USE_SES

# 공통
_LOG_SHEET_ID       = settings.LOG_SHEET_ID
_SLACK_TOKEN        = settings.SLACK_BOT_TOKEN
_SLACK_ERROR_CH     = settings.SLACK_ERROR_CHANNEL
_TAB_CONTENT        = settings.TAB_CONTENT
_TAB_STATS          = settings.TAB_STATS
_TAB_RIGHTS         = settings.TAB_RIGHTS
_TAB_LOG            = settings.TAB_LOG
_TAB_LEADS          = settings.TAB_LEADS

# D-3
_KAKAO_FORM_SHEET_ID   = settings.KAKAO_FORM_SHEET_ID
_KAKAO_OUTPUT_SHEET_ID = settings.KAKAO_OUTPUT_SHEET_ID
_KAKAO_FORM_TAB        = settings.KAKAO_FORM_TAB
_KAKAO_OUTPUT_TAB      = settings.KAKAO_OUTPUT_TAB

_GENRE_MAP = {
    "예능":        Genre.ENTERTAINMENT,
    "드라마·영화": Genre.DRAMA_MOVIE,
    "기타":        Genre.OTHER,
}

# ── 백그라운드 태스크 저장소 ────────────────────────────────────────────────────
_task_store: dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=4)

# ── FastAPI 앱 ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="루나트 RPA — HTTP 트리거 서버",
    description="A-2, B-2, C-1, C-2 자동화 업무를 HTTP POST로 트리거",
    version="1.0.0",
)


# ── 인증 ──────────────────────────────────────────────────────────────────────

def _check_auth(x_rpa_token: Optional[str] = Header(default=None)) -> None:
    """X-RPA-Token 헤더 검증. RPA_TOKEN 미설정 시 인증 생략(개발 모드)."""
    if not _RPA_TOKEN:
        return  # 개발 모드: 인증 없이 통과
    if x_rpa_token != _RPA_TOKEN:
        raise HTTPException(status_code=401, detail="X-RPA-Token 헤더가 유효하지 않습니다.")


# ── 공통 의존성 빌더 ────────────────────────────────────────────────────────────

def _build_common_deps():
    """공통 의존성: gspread 클라이언트, 로그 저장소, 알림 발송."""
    import gspread
    from src.core.notifiers.email_notifier import EmailNotifier
    from src.core.notifiers.slack_notifier import SlackNotifier
    from src.core.repositories.sheet_repository import SheetLogRepository

    creds = build_google_creds(_CREDS_FILE)
    gc    = gspread.authorize(creds)

    log_repo = None
    try:
        log_sh   = gc.open_by_key(_LOG_SHEET_ID)
        log_repo = SheetLogRepository(log_sh.worksheet(_TAB_LOG))
    except Exception as e:
        log.warning("[RPA] 로그 저장소 초기화 실패 (무시): %s", e)

    slack_notifier = (
        _build_slack_notifier() if _SLACK_TOKEN
        else NullNotifier()
    )
    email_notifier = EmailNotifier(
        sender_email=_SENDER_EMAIL,
        use_ses=_USE_SES,
    )
    return gc, creds, log_repo, slack_notifier, email_notifier


def _build_slack_notifier():
    from src.core.notifiers.slack_notifier import SlackNotifier
    return SlackNotifier(token=_SLACK_TOKEN, error_channel=_SLACK_ERROR_CH)


# ── 요청 모델 ──────────────────────────────────────────────────────────────────

class A2TriggerRequest(BaseModel):
    channel_name:    str
    work_title:      str
    slack_channel_id: str = "C_HTTP_TRIGGER"
    slack_message_ts: str = ""

class B2TriggerRequest(BaseModel):
    pass  # 파라미터 없음

class C1TriggerRequest(BaseModel):
    max_channels: int = 200

class C2TriggerRequest(BaseModel):
    batch_size:         int           = 50
    genre:              Optional[str] = None   # "예능" | "드라마·영화" | "기타"
    min_monthly_views:  int           = 0
    platform:           Optional[str] = None   # "youtube"


# ── 응답 헬퍼 ──────────────────────────────────────────────────────────────────

def _ok(result: dict, task_id: str | None = None) -> JSONResponse:
    payload = {"status": "ok", "result": result}
    if task_id:
        payload["task_id"] = task_id
    return JSONResponse(content=payload)

def _task_started(task_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=202,
        content={
            "status": "started",
            "task_id": task_id,
            "poll_url": f"/api/tasks/{task_id}",
        },
    )


# ── 헬스체크 ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "time": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"),
        "auth_required": bool(_RPA_TOKEN),
    }


# ── 태스크 결과 조회 ─────────────────────────────────────────────────────────────

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str, _: None = Depends(_check_auth)):
    entry = _task_store.get(task_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"태스크 없음: {task_id}")
    return entry


# ── A-2: 작품사용신청 승인 ────────────────────────────────────────────────────────
#
# 플로우: 채널명 + 작품명 → Slack 메시지 포맷으로 조합 → a2.run()
#   → 시트에서 크리에이터 이메일 조회 → Drive 파일 권한 부여 → 승인 이메일 발송

@app.post("/api/a2/trigger")
async def trigger_a2(
    req: A2TriggerRequest,
    _: None = Depends(_check_auth),
):
    from googleapiclient.discovery import build as google_build
    from src.handlers.a2_work_approval import run as a2_run

    slack_text = (
        f'채널: "{req.channel_name}" 의 신규 영상 사용 요청이 있습니다.\n'
        f'{req.work_title}'
    )

    def _run():
        gc, creds, log_repo, slack_notifier, email_notifier = _build_common_deps()
        drive_svc = google_build("drive", "v3", credentials=creds)
        return a2_run(
            slack_channel_id   = req.slack_channel_id,
            slack_message_ts   = req.slack_message_ts or "0000000000.000001",
            slack_message_text = slack_text,
            sheets_client      = gc,
            drive_service      = drive_svc,
            email_notifier     = email_notifier,
            slack_notifier     = slack_notifier,
            creator_sheet_id   = _CREATOR_SHEET_ID,
            drive_folder_id    = _DRIVE_FOLDER_ID,
            sender_email       = _SENDER_EMAIL,
            admin_api_base_url = _ADMIN_API_BASE_URL,
        )

    try:
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run)
        log.info("[A-2] HTTP 트리거 완료: %s", result)
        return _ok(result)
    except Exception as e:
        log.error("[A-2] HTTP 트리거 실패: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


# ── B-2: 주간 성과 보고 ───────────────────────────────────────────────────────────
#
# 크롤링(Naver Clip) → 시트 upsert → 권리사 이메일 발송
# 소요 시간이 길 수 있어 BackgroundTasks 사용 → 202 + task_id 즉시 반환

@app.post("/api/b2/trigger")
async def trigger_b2(
    req: B2TriggerRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(_check_auth),
):
    task_id = str(uuid.uuid4())[:8]
    _task_store[task_id] = {"status": "running", "started_at": datetime.now(KST).isoformat()}

    def _run():
        import gspread
        from src.core.repositories.sheet_repository import (
            SheetPerformanceRepository, SheetLogRepository,
        )
        from src.handlers.b2_weekly_report import run as b2_run

        try:
            gc, _creds, _log_repo, slack_notifier, email_notifier = _build_common_deps()
            content_sh = gc.open_by_key(_CONTENT_SHEET_ID)
            perf_sh    = gc.open_by_key(_PERF_SHEET_ID)
            log_sh     = gc.open_by_key(_LOG_SHEET_ID)

            perf_repo = SheetPerformanceRepository(
                content_ws       = content_sh.worksheet(_TAB_CONTENT),
                stats_ws         = perf_sh.worksheet(_TAB_STATS),
                rights_ws        = content_sh.worksheet(_TAB_RIGHTS),
                looker_dashboards= _LOOKER_DASHBOARDS,
            )
            log_repo = SheetLogRepository(log_sh.worksheet(_TAB_LOG))

            result = b2_run(
                perf_repo      = perf_repo,
                log_repo       = log_repo,
                email_notifier = email_notifier,
                slack_notifier = slack_notifier,
                headless       = True,
            )
            _task_store[task_id] = {
                "status": "done",
                "result": result,
                "finished_at": datetime.now(KST).isoformat(),
            }
        except Exception as e:
            log.error("[B-2] 백그라운드 실행 실패: %s", e)
            _task_store[task_id] = {
                "status": "error",
                "error": str(e),
                "finished_at": datetime.now(KST).isoformat(),
            }

    background_tasks.add_task(_run)
    log.info("[B-2] HTTP 트리거 시작: task_id=%s", task_id)
    return _task_started(task_id)


# ── C-1: 리드 발굴 ────────────────────────────────────────────────────────────
#
# YouTube Shorts 채널 탐색 → 등급 분류 → 리드 시트 upsert
# 소요 시간이 길어 BackgroundTasks 사용

@app.post("/api/c1/trigger")
async def trigger_c1(
    req: C1TriggerRequest,
    background_tasks: BackgroundTasks,
    _: None = Depends(_check_auth),
):
    if not _YOUTUBE_API_KEY:
        raise HTTPException(status_code=400, detail="YOUTUBE_API_KEY 환경 변수가 설정되지 않았습니다.")

    task_id = str(uuid.uuid4())[:8]
    _task_store[task_id] = {"status": "running", "started_at": datetime.now(KST).isoformat()}

    def _run():
        import gspread
        from src.core.repositories.sheet_repository import SheetLeadRepository, SheetLogRepository
        from src.handlers.c1_lead_filter import run as c1_run

        try:
            gc, _creds, _log_repo, slack_notifier, _email_notifier = _build_common_deps()
            lead_sh  = gc.open_by_key(_LEAD_SHEET_ID)
            log_sh   = gc.open_by_key(_LOG_SHEET_ID)

            lead_repo = SheetLeadRepository(lead_sh.worksheet(_TAB_LEADS))
            log_repo  = SheetLogRepository(log_sh.worksheet(_TAB_LOG))

            result = c1_run(
                lead_repo      = lead_repo,
                log_repo       = log_repo,
                slack_notifier = slack_notifier,
                api_key        = _YOUTUBE_API_KEY,
                seed_sheet_id  = _SEED_SHEET_ID,
                seed_sheet_gid = _SEED_SHEET_GID,
                max_channels   = req.max_channels,
            )
            _task_store[task_id] = {
                "status": "done",
                "result": result,
                "finished_at": datetime.now(KST).isoformat(),
            }
        except Exception as e:
            log.error("[C-1] 백그라운드 실행 실패: %s", e)
            _task_store[task_id] = {
                "status": "error",
                "error": str(e),
                "finished_at": datetime.now(KST).isoformat(),
            }

    background_tasks.add_task(_run)
    log.info("[C-1] HTTP 트리거 시작: task_id=%s", task_id)
    return _task_started(task_id)


# ── C-2: 콜드메일 발송 ────────────────────────────────────────────────────────
#
# 리드 시트 조회 → 필터 적용 → 개인화 이메일 발송

@app.post("/api/c2/trigger")
async def trigger_c2(
    req: C2TriggerRequest,
    _: None = Depends(_check_auth),
):
    if req.genre and req.genre not in _GENRE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"genre 값 오류: {req.genre!r}. 예능 / 드라마·영화 / 기타 중 하나."
        )

    def _run():
        import gspread
        from src.core.repositories.sheet_repository import SheetLeadRepository, SheetLogRepository
        from src.handlers.c2_cold_email import run as c2_run

        gc, _creds, _log_repo, slack_notifier, email_notifier = _build_common_deps()
        lead_sh  = gc.open_by_key(_LEAD_SHEET_ID)
        log_sh   = gc.open_by_key(_LOG_SHEET_ID)

        lead_repo = SheetLeadRepository(lead_sh.worksheet(_TAB_LEADS))
        log_repo  = SheetLogRepository(log_sh.worksheet(_TAB_LOG))

        return c2_run(
            lead_repo         = lead_repo,
            log_repo          = log_repo,
            email_notifier    = email_notifier,
            slack_notifier    = slack_notifier,
            sender_name       = _SENDER_NAME,
            batch_size        = req.batch_size,
            genre             = _GENRE_MAP.get(req.genre) if req.genre else None,
            min_monthly_views = req.min_monthly_views,
            platform          = req.platform,
        )

    try:
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run)
        log.info("[C-2] HTTP 트리거 완료: %s", result)
        return _ok(result)
    except Exception as e:
        log.error("[C-2] HTTP 트리거 실패: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


# ── D-3: 카카오 오리지널 크리에이터 월초 점검 ───────────────────────────────────
#
# 구글폼 응답 → '최종 리스트' 시트 자동 입력 + 규모 카테고리 계산

class D3TriggerRequest(BaseModel):
    dry_run: bool = False   # True이면 시트에 쓰지 않고 결과만 반환

@app.post("/api/d3/trigger")
async def trigger_d3(
    req: D3TriggerRequest,
    _: None = Depends(_check_auth),
):
    def _run():
        import gspread
        from src.handlers.d3_kakao_creator_onboarding import run as d3_run

        gc, _creds, _log_repo, _slack_notifier, _email_notifier = _build_common_deps()

        form_sheet_id = _KAKAO_FORM_SHEET_ID or _KAKAO_OUTPUT_SHEET_ID
        form_sh       = gc.open_by_key(form_sheet_id)
        output_sh     = gc.open_by_key(_KAKAO_OUTPUT_SHEET_ID)

        form_ws   = form_sh.worksheet(_KAKAO_FORM_TAB)
        output_ws = output_sh.worksheet(_KAKAO_OUTPUT_TAB)

        return d3_run(
            form_ws   = form_ws,
            output_ws = output_ws,
            dry_run   = req.dry_run,
        )

    try:
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run)
        log.info("[D-3] HTTP 트리거 완료: %s", result)
        return _ok(result)
    except Exception as e:
        log.error("[D-3] HTTP 트리거 실패: %s", e)
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


# ── 관리 UI (브라우저 접근용) ───────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def admin_ui():
    # 서버 측에서 토큰을 JS 변수로 주입 (로컬 전용 관리 UI)
    return _ADMIN_HTML.replace("__RPA_TOKEN__", _RPA_TOKEN)


_ADMIN_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>루나트 RPA 관리 콘솔</title>
  <style>
    * { box-sizing: border-box; }
    body { font-family: -apple-system, 'Noto Sans KR', sans-serif;
           background: #f0f2f5; margin: 0; padding: 24px; }
    h1 { font-size: 1.4rem; color: #1a1a2e; margin: 0 0 4px; }
    .subtitle { color: #666; font-size: 0.85rem; margin-bottom: 24px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
    .card { background: white; border-radius: 10px; padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,.08); }
    .card h2 { font-size: 1rem; margin: 0 0 4px; color: #333; }
    .card .desc { font-size: 0.8rem; color: #888; margin-bottom: 16px; }
    label { display: block; font-size: 0.8rem; font-weight: 600;
            color: #555; margin: 10px 0 3px; }
    input, select { width: 100%; padding: 7px 10px; border: 1px solid #ddd;
                    border-radius: 5px; font-size: 13px; }
    .btn { display: block; width: 100%; margin-top: 14px; padding: 10px;
           background: #4a6cf7; color: white; border: none; border-radius: 6px;
           font-size: 14px; cursor: pointer; font-weight: 600; }
    .btn:hover { background: #3a5ce7; }
    .btn.secondary { background: #6c757d; }
    .result-box { margin-top: 12px; padding: 12px; border-radius: 6px;
                  font-size: 12px; font-family: monospace; display: none; }
    .result-box.ok   { background: #f0fdf4; border-left: 4px solid #22c55e; }
    .result-box.err  { background: #fef2f2; border-left: 4px solid #ef4444; }
    .result-box.info { background: #eff6ff; border-left: 4px solid #3b82f6; }
    pre { margin: 0; white-space: pre-wrap; word-break: break-all; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 10px;
             font-size: 11px; font-weight: 600; background: #e0e7ff; color: #3730a3; }
  </style>
</head>
<body>
  <h1>루나트 RPA 관리 콘솔</h1>
  <div class="subtitle">A-2 / B-2 / C-1 / C-2 업무 자동화 HTTP 트리거</div>

  <div class="grid">

    <!-- A-2 -->
    <div class="card">
      <h2>🎬 A-2 &nbsp;<span class="badge">작품사용신청 승인</span></h2>
      <div class="desc">채널명 + 작품명 → 시트 이메일 조회 → Drive 권한 부여 → 승인 이메일</div>
      <label>채널명 (크리에이터명)</label>
      <input id="a2-channel" value="유호영" placeholder="예: 유호영">
      <label>작품명</label>
      <input id="a2-work" value="신병" placeholder="예: 21세기 대군부인">
      <button class="btn" onclick="triggerA2()">실행</button>
      <div id="a2-result" class="result-box"><pre id="a2-pre"></pre></div>
    </div>

    <!-- B-2 -->
    <div class="card">
      <h2>📊 B-2 &nbsp;<span class="badge">주간 성과 보고</span></h2>
      <div class="desc">네이버 클립 크롤링 → 성과 시트 업데이트 → 권리사 이메일 발송</div>
      <div style="color:#888; font-size:13px; margin: 12px 0;">
        파라미터 없음. 완료까지 수분 소요 → 202 즉시 반환 후 task_id로 결과 조회.
      </div>
      <button class="btn" onclick="triggerB2()">실행</button>
      <button class="btn secondary" onclick="pollTask('b2')">결과 조회</button>
      <div id="b2-result" class="result-box"><pre id="b2-pre"></pre></div>
    </div>

    <!-- C-1 -->
    <div class="card">
      <h2>🔍 C-1 &nbsp;<span class="badge">리드 발굴</span></h2>
      <div class="desc">YouTube Shorts 채널 탐색 → 등급 분류 → 리드 시트 upsert</div>
      <label>최대 탐색 채널 수</label>
      <input id="c1-max" type="number" value="200" min="1" max="500">
      <button class="btn" onclick="triggerC1()">실행</button>
      <button class="btn secondary" onclick="pollTask('c1')">결과 조회</button>
      <div id="c1-result" class="result-box"><pre id="c1-pre"></pre></div>
    </div>

    <!-- D-3 -->
    <div class="card">
      <h2>🟡 D-3 &nbsp;<span class="badge">카카오 크리에이터 온보딩</span></h2>
      <div class="desc">구글폼 응답 → '최종 리스트' 시트 자동 입력 + 규모 카테고리 계산</div>
      <label style="display:flex;align-items:center;gap:8px;font-weight:400">
        <input type="checkbox" id="d3-dryrun"> dry_run (시트 쓰기 생략)
      </label>
      <button class="btn" onclick="triggerD3()">실행</button>
      <div id="d3-result" class="result-box"><pre id="d3-pre"></pre></div>
    </div>

    <!-- C-2 -->
    <div class="card">
      <h2>📧 C-2 &nbsp;<span class="badge">콜드메일 발송</span></h2>
      <div class="desc">리드 시트 조회 → 필터 적용 → 개인화 이메일 발송</div>
      <label>배치 크기</label>
      <input id="c2-batch" type="number" value="50" min="1" max="200">
      <label>장르 필터</label>
      <select id="c2-genre">
        <option value="">전체</option>
        <option value="예능">예능</option>
        <option value="드라마·영화">드라마·영화</option>
        <option value="기타">기타</option>
      </select>
      <label>최소 월간 조회수</label>
      <input id="c2-views" type="number" value="0" min="0">
      <button class="btn" onclick="triggerC2()">실행</button>
      <div id="c2-result" class="result-box"><pre id="c2-pre"></pre></div>
    </div>

  </div>

  <script>
    const _taskIds = {};
    const _RPA_TOKEN = '__RPA_TOKEN__';

    async function call(endpoint, body, resultId, preId, taskKey) {
      const box = document.getElementById(resultId);
      const pre = document.getElementById(preId);
      box.className = 'result-box info';
      box.style.display = 'block';
      pre.textContent = '실행 중...';
      try {
        const headers = {'Content-Type': 'application/json'};
        if (_RPA_TOKEN) headers['X-RPA-Token'] = _RPA_TOKEN;
        const res = await fetch(endpoint, {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
        });
        const data = await res.json();
        pre.textContent = JSON.stringify(data, null, 2);
        if (data.task_id) {
          _taskIds[taskKey] = data.task_id;
          pre.textContent += '\\n\\n※ task_id 저장됨: ' + data.task_id + ' — [결과 조회] 버튼으로 확인';
        }
        box.className = res.ok ? 'result-box ok' : 'result-box err';
      } catch(e) {
        pre.textContent = '오류: ' + e.message;
        box.className = 'result-box err';
      }
    }

    async function pollTask(key) {
      const taskId = _taskIds[key];
      if (!taskId) { alert('먼저 실행하세요.'); return; }
      const resultId = key + '-result';
      const preId    = key + '-pre';
      const box = document.getElementById(resultId);
      const pre = document.getElementById(preId);
      try {
        const hdrs = _RPA_TOKEN ? {'X-RPA-Token': _RPA_TOKEN} : {};
        const res  = await fetch('/api/tasks/' + taskId, {headers: hdrs});
        const data = await res.json();
        box.style.display = 'block';
        pre.textContent = JSON.stringify(data, null, 2);
        box.className = data.status === 'done' ? 'result-box ok' :
                        data.status === 'error' ? 'result-box err' : 'result-box info';
      } catch(e) {
        alert('조회 실패: ' + e.message);
      }
    }

    function triggerA2() {
      call('/api/a2/trigger', {
        channel_name: document.getElementById('a2-channel').value,
        work_title:   document.getElementById('a2-work').value,
      }, 'a2-result', 'a2-pre', 'a2');
    }
    function triggerB2() {
      call('/api/b2/trigger', {}, 'b2-result', 'b2-pre', 'b2');
    }
    function triggerC1() {
      call('/api/c1/trigger', {
        max_channels: parseInt(document.getElementById('c1-max').value),
      }, 'c1-result', 'c1-pre', 'c1');
    }
    function triggerD3() {
      call('/api/d3/trigger', {
        dry_run: document.getElementById('d3-dryrun').checked,
      }, 'd3-result', 'd3-pre', 'd3');
    }
    function triggerC2() {
      const genre = document.getElementById('c2-genre').value;
      call('/api/c2/trigger', {
        batch_size:        parseInt(document.getElementById('c2-batch').value),
        genre:             genre || null,
        min_monthly_views: parseInt(document.getElementById('c2-views').value),
      }, 'c2-result', 'c2-pre', 'c2');
    }
  </script>
</body>
</html>
"""


# ── 진입점 ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("루나트 RPA HTTP 트리거 서버 시작")
    print("  관리 콘솔: http://localhost:8000")
    print("  API 문서:  http://localhost:8000/docs")
    uvicorn.run("src.api.rpa_server:app", host="0.0.0.0", port=8000, reload=False)
