# -*- coding: utf-8 -*-
"""D-3 Lambda 엔트리포인트 — 카카오 오리지널 크리에이터 월초 점검.

트리거: HTTP POST (매달 초 담당자가 수동 호출 또는 Cron)

환경 변수:
  KAKAO_FORM_SHEET_ID    구글폼 응답이 연결된 스프레드시트 ID
  KAKAO_OUTPUT_SHEET_ID  출력 대상 스프레드시트 ID
                         (1tqhZEoUnTITURcJTGhPAcPPjzckVstdsETcUMY7I7Ys)
  KAKAO_FORM_TAB         구글폼 응답 탭명 (기본: "설문지 응답 시트1")
  KAKAO_OUTPUT_TAB       출력 탭명 (기본: "최종 리스트")
  GOOGLE_CREDENTIALS_FILE  인증 파일 경로 (기본: credentials.json)
  LOG_SHEET_ID           로그 시트 ID
  SLACK_BOT_TOKEN        Slack 에러 알림
  SLACK_ERROR_CHANNEL    Slack 에러 채널
"""
import json
import os
import sys

import gspread

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.api.deps import build_google_creds
from src.core.logger import CoreLogger
from src.handlers.d3_kakao_creator_onboarding import run as d3_run, TASK_ID, TASK_NAME

log = CoreLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

KAKAO_FORM_SHEET_ID  = os.environ.get("KAKAO_FORM_SHEET_ID", "")
KAKAO_OUTPUT_SHEET_ID = os.environ.get(
    "KAKAO_OUTPUT_SHEET_ID", "1tqhZEoUnTITURcJTGhPAcPPjzckVstdsETcUMY7I7Ys"
)
KAKAO_FORM_TAB   = os.environ.get("KAKAO_FORM_TAB",   "설문지 응답 시트1")
KAKAO_OUTPUT_TAB = os.environ.get("KAKAO_OUTPUT_TAB", "최종 리스트")
CREDS_FILE       = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")


def _build_deps():
    creds = build_google_creds(CREDS_FILE, _SCOPES)
    gc    = gspread.authorize(creds)

    # 폼 응답 시트: 별도 시트 ID가 없으면 출력 시트에서 폼 탭을 찾는다
    form_sheet_id = KAKAO_FORM_SHEET_ID or KAKAO_OUTPUT_SHEET_ID
    form_sh   = gc.open_by_key(form_sheet_id)
    output_sh = gc.open_by_key(KAKAO_OUTPUT_SHEET_ID)

    form_ws   = form_sh.worksheet(KAKAO_FORM_TAB)
    output_ws = output_sh.worksheet(KAKAO_OUTPUT_TAB)

    return form_ws, output_ws


def handler(event: dict, context=None) -> dict:
    """Lambda / HTTP 핸들러 진입점."""
    if isinstance(event.get("body"), str):
        try:
            body = json.loads(event["body"])
            event = {**event, **body}
        except json.JSONDecodeError:
            pass

    dry_run = bool(event.get("dry_run", False))

    log.info("[D-3] 핸들러 시작 (dry_run=%s)", dry_run)
    try:
        form_ws, output_ws = _build_deps()
        result = d3_run(
            form_ws=form_ws,
            output_ws=output_ws,
            dry_run=dry_run,
        )
        return {
            "statusCode": 200,
            "body": json.dumps(result, ensure_ascii=False),
        }
    except Exception as e:
        log.error("[D-3] 핸들러 실패: %s", e)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}, ensure_ascii=False),
        }


if __name__ == "__main__":
    result = handler({"dry_run": False}, None)
    print(json.dumps(json.loads(result["body"]), ensure_ascii=False, indent=2))
