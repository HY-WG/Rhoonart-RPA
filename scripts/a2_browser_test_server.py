#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A-2 브라우저 통합 테스트 서버.

목적:
  브라우저에서 버튼 클릭 → A-2 백엔드 로직 실행 → 결과 가시화

실행 방법:
    cd C:\\Users\\mung9\\IdeaProjects\\rhoonart-rpa
    python scripts/a2_browser_test_server.py

  브라우저에서 http://localhost:8001 접속

주의:
  - credentials.json이 프로젝트 루트에 있어야 함
  - .env 파일에 환경 변수 설정 필요
  - 실제 Drive 권한 변경이 일어나므로 테스트 계정으로 실행 권장

테스트 대상 플로우:
  1. 입력: 채널명, 작품명, 이메일 (또는 Slack 메시지 포맷)
  2. A-2 run() 호출 (Drive 검색 → 권한 부여 → 이메일 발송)
  3. 결과를 HTML로 렌더링
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

import pytz
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

KST = pytz.timezone("Asia/Seoul")

app = FastAPI(title="A-2 Browser Integration Test")

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>A-2 작품사용신청 승인 — 통합 테스트</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans KR', sans-serif;
           max-width: 720px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
    h1 {{ color: #333; font-size: 1.4rem; }}
    .card {{ background: white; border-radius: 8px; padding: 24px; margin: 16px 0;
             box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
    label {{ display: block; font-weight: 600; margin: 12px 0 4px; color: #555; }}
    input, textarea {{ width: 100%; padding: 8px 12px; border: 1px solid #ddd;
                       border-radius: 4px; font-size: 14px; box-sizing: border-box; }}
    textarea {{ height: 100px; font-family: monospace; }}
    button {{ margin-top: 16px; padding: 10px 24px; background: #4a6cf7; color: white;
              border: none; border-radius: 4px; font-size: 15px; cursor: pointer; }}
    button:hover {{ background: #3a5ce7; }}
    .result {{ margin-top: 20px; }}
    .success {{ border-left: 4px solid #22c55e; background: #f0fdf4; padding: 16px; border-radius: 4px; }}
    .failure {{ border-left: 4px solid #ef4444; background: #fef2f2; padding: 16px; border-radius: 4px; }}
    .warning  {{ border-left: 4px solid #f59e0b; background: #fffbeb; padding: 16px; border-radius: 4px; }}
    pre {{ background: #1e1e1e; color: #d4d4d4; padding: 16px; border-radius: 4px;
           overflow-x: auto; font-size: 12px; white-space: pre-wrap; word-break: break-all; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px;
              font-size: 12px; font-weight: 600; margin-right: 4px; }}
    .badge.green {{ background: #dcfce7; color: #15803d; }}
    .badge.red   {{ background: #fee2e2; color: #b91c1c; }}
    .badge.gray  {{ background: #f3f4f6; color: #374151; }}
  </style>
</head>
<body>
  <h1>🎬 A-2 작품사용신청 승인 — 통합 테스트</h1>

  <div class="card">
    <h2 style="font-size:1rem; color:#666; margin:0 0 12px">테스트 입력</h2>
    <form method="post" action="/test-a2">
      <label>채널명 (크리에이터명)</label>
      <input name="channel_name" value="{channel_name}" placeholder="예: 유호영" required>

      <label>작품명</label>
      <input name="work_title" value="{work_title}" placeholder="예: 21세기 대군부인" required>

      <label>크리에이터 이메일 <span style="font-weight:400; color:#999">(직접 입력 — Sheets 조회 대신)</span></label>
      <input name="email" value="{email}" placeholder="예: creator@gmail.com" type="email" required>

      <label>Slack 스레드 타임스탬프 <span style="font-weight:400; color:#999">(옵션)</span></label>
      <input name="slack_ts" value="{slack_ts}" placeholder="예: 1714000000.000001">

      <label>Slack 채널 ID <span style="font-weight:400; color:#999">(옵션)</span></label>
      <input name="slack_channel" value="{slack_channel}" placeholder="예: C00ABCDEF">

      <button type="submit">🚀 A-2 승인 플로우 실행</button>
    </form>
  </div>

  {result_section}

  <div class="card" style="font-size:12px; color:#999;">
    <strong>환경:</strong> DRIVE_FOLDER_ID={drive_folder_id} &nbsp;
    CREATOR_SHEET_ID={creator_sheet_id} &nbsp;
    SENDER_EMAIL={sender_email}
  </div>
</body>
</html>
"""

_RESULT_SUCCESS = """
<div class="card result">
  <div class="success">
    <strong>✅ 처리 완료</strong>
    <div style="margin-top:8px">
      <span class="badge green">이메일 {email_sent}</span>
      <span class="badge {slack_color}">Slack 회신 {slack_replied}</span>
      <span class="badge gray">Drive 권한 {drive_perm}</span>
    </div>
  </div>
  <pre>{result_json}</pre>
</div>
"""

_RESULT_FAILURE = """
<div class="card result">
  <div class="failure">
    <strong>❌ 처리 실패</strong>
    <p style="margin-top:8px; color:#b91c1c">{error}</p>
  </div>
  <pre>{detail}</pre>
</div>
"""

_RESULT_WARNING = """
<div class="card result">
  <div class="warning">
    <strong>⚠️ 부분 처리 (stub 모드)</strong>
    <p style="margin-top:8px">{message}</p>
  </div>
  <pre>{result_json}</pre>
</div>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return _render_form()


@app.post("/test-a2", response_class=HTMLResponse)
async def run_a2_test(
    request: Request,
    channel_name: str = Form(...),
    work_title: str = Form(...),
    email: str = Form(...),
    slack_ts: str = Form(""),
    slack_channel: str = Form(""),
):
    result_section = ""
    try:
        result_section = await _execute_a2_flow(
            channel_name=channel_name,
            work_title=work_title,
            email=email,
            slack_ts=slack_ts or None,
            slack_channel=slack_channel or None,
        )
    except Exception as exc:
        import traceback
        result_section = _RESULT_FAILURE.format(
            error=str(exc),
            detail=traceback.format_exc()[:2000],
        )
    return _render_form(
        channel_name=channel_name,
        work_title=work_title,
        email=email,
        slack_ts=slack_ts,
        slack_channel=slack_channel,
        result_section=result_section,
    )


from src.api.deps import build_google_creds as _build_google_creds


async def _execute_a2_flow(
    channel_name: str,
    work_title: str,
    email: str,
    slack_ts: str | None,
    slack_channel: str | None,
) -> str:
    """A-2 핸들러를 직접 호출해 결과를 HTML로 반환."""
    import gspread
    from googleapiclient.discovery import build as google_build

    from src.handlers.a2_work_approval import run as a2_run
    from src.core.notifiers.email_notifier import EmailNotifier
    from src.core.notifiers.slack_notifier import SlackNotifier

    _SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive",
    ]

    cred_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    creds = _build_google_creds(cred_file, _SCOPES)

    gc        = gspread.authorize(creds)
    drive_svc = google_build("drive", "v3", credentials=creds)

    slack_token  = os.environ.get("SLACK_BOT_TOKEN", "")
    slack_ch     = os.environ.get("SLACK_ERROR_CHANNEL", "#rpa-error")
    slack_notifier = SlackNotifier(token=slack_token, error_channel=slack_ch) if slack_token else _NullNotifier()

    email_notifier = EmailNotifier(
        sender_email=os.environ.get("SENDER_EMAIL", "hoyoungy2@gmail.com"),
        use_ses=os.environ.get("USE_SES", "false").lower() == "true",
        smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=os.environ.get("SMTP_USER", ""),
        smtp_password=os.environ.get("SMTP_PASSWORD", ""),
    )

    # A-2 run()은 Slack 메시지 포맷에서 채널명·작품명을 파싱하고
    # 시트에서 이메일을 조회하므로, 브라우저 테스트에서는
    # 폼 입력값으로 Slack 메시지를 재조합해 전달한다.
    slack_message_text = (
        f'채널: "{channel_name}" 의 신규 영상 사용 요청이 있습니다.\n{work_title}'
    )
    creator_sheet_id = os.environ.get(
        "CREATOR_SHEET_ID", "1JZ0eLnvMgpjAehpxRfPN2RiG6Pd22EidnnG8tmAvlKQ"
    )

    start = datetime.now(KST)
    result = a2_run(
        slack_channel_id=slack_channel or "C_BROWSER_TEST",
        slack_message_ts=slack_ts or "0000000000.000001",
        slack_message_text=slack_message_text,
        sheets_client=gc,
        drive_service=drive_svc,
        email_notifier=email_notifier,
        slack_notifier=slack_notifier,
        creator_sheet_id=creator_sheet_id,
        drive_folder_id=os.environ.get("DRIVE_FOLDER_ID", "1SEVgIFr8HivMFXBru3C-mfgfTETeLW92"),
        sender_email=os.environ.get("SENDER_EMAIL", "hoyoungy2@gmail.com"),
        admin_api_base_url=os.environ.get("ADMIN_API_BASE_URL", ""),
    )
    elapsed = (datetime.now(KST) - start).total_seconds()
    result["_elapsed_s"] = round(elapsed, 2)
    result["_run_at"] = start.strftime("%Y-%m-%d %H:%M:%S KST")

    result_json = json.dumps(result, ensure_ascii=False, indent=2)

    if result.get("stub"):
        return _RESULT_WARNING.format(
            message="Admin API URL 미설정 — 스텁 모드로 실행됨",
            result_json=result_json,
        )

    return _RESULT_SUCCESS.format(
        email_sent="✓" if result.get("email_sent") else "✗",
        slack_replied="✓" if result.get("slack_replied") else "✗",
        slack_color="green" if result.get("slack_replied") else "gray",
        drive_perm=result.get("drive_file_id", "N/A")[:20] if result.get("drive_file_id") else "✗",
        result_json=result_json,
    )


class _NullNotifier:
    """Slack 환경 변수 없을 때 사용하는 빈 Notifier."""
    def send(self, *args, **kwargs) -> bool:
        return False

    def send_error(self, *args, **kwargs) -> bool:
        return False


def _render_form(
    channel_name: str = "테스트채널",
    work_title: str = "신병",
    email: str = "hoyoungy2@gmail.com",
    slack_ts: str = "",
    slack_channel: str = "",
    result_section: str = "",
) -> str:
    return _HTML_TEMPLATE.format(
        channel_name=channel_name,
        work_title=work_title,
        email=email,
        slack_ts=slack_ts,
        slack_channel=slack_channel,
        result_section=result_section,
        drive_folder_id=os.environ.get("DRIVE_FOLDER_ID", "1SEVgIFr8HivMFXBru3C-mfgfTETeLW92"),
        creator_sheet_id=os.environ.get("CREATOR_SHEET_ID", "1JZ0eLnvMgpjAehpxRfPN2RiG6Pd22EidnnG8tmAvlKQ"),
        sender_email=os.environ.get("SENDER_EMAIL", "hoyoungy2@gmail.com"),
    )


if __name__ == "__main__":
    print("🚀 A-2 브라우저 통합 테스트 서버 시작")
    print("   브라우저에서 http://localhost:8001 접속")
    uvicorn.run(app, host="0.0.0.0", port=8001)
