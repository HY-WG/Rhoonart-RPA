#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A-3 통합 테스트 스크립트 - Google Sheets 실제 연결 검증.

목적:
  credentials.json을 사용해 실제 Google Sheets에 접근,
  A-3 네이버 클립 월별 핸들러가 폼 응답 시트를 올바르게 읽는지 확인한다.

실행 방법:
    cd C:\\Users\\mung9\\IdeaProjects\\rhoonart-rpa
    python scripts/integration_test_a3_sheets.py

credentials.json 형식 자동 감지:
  - service_account 형식 (type: "service_account")
      -> Credentials.from_service_account_file() 사용
      -> 브라우저 인증 불필요
  - OAuth2 installed 형식 (key: "installed")
      -> gspread.oauth() 사용
      -> 최초 실행 시 브라우저 인증 필요 (이후 ~/.config/gspread/credentials.json 캐시)

검증 항목:
  1. credentials.json 형식 감지 및 인증
  2. NAVER_FORM_ID 시트 열기
  3. 탭 존재 확인
  4. 헤더 행 읽기
  5. SheetFormResponseRepository.get_applicants_by_month() 호출
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pytz
import gspread

KST = pytz.timezone("Asia/Seoul")

CREDENTIALS_FILE = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
NAVER_FORM_ID    = os.environ.get("NAVER_FORM_ID", "1RDP-cf0fU9TAMEtTUZ_Av3d0Q-SjL59hULBPhiqouBs")
TAB_NAVER_FORM   = os.environ.get("TAB_NAVER_FORM", "설문지 응답 시트1")

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _banner(text):
    print("\n" + "="*60)
    print("  " + text)
    print("="*60)


def _detect_cred_type(cred_path):
    """credentials.json 형식 감지. 반환값: 'service_account' | 'oauth2' | 'unknown'"""
    with open(cred_path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("type") == "service_account":
        return "service_account"
    if "installed" in data or "web" in data:
        return "oauth2"
    return "unknown"


def test_gspread_auth():
    """[1] credentials.json 형식 감지 및 인증"""
    _banner("테스트 1: credentials.json 인증")
    cred_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), CREDENTIALS_FILE)
    print("  키 파일: " + cred_path)

    if not os.path.exists(cred_path):
        raise FileNotFoundError("credentials.json 없음: " + cred_path)

    cred_type = _detect_cred_type(cred_path)
    print("  감지된 형식: " + cred_type)

    if cred_type == "service_account":
        from google.oauth2.service_account import Credentials
        creds = Credentials.from_service_account_file(cred_path, scopes=_SCOPES)
        gc = gspread.authorize(creds)
        print("  [OK] 서비스 계정 인증 성공")

    elif cred_type == "oauth2":
        print("  OAuth2 클라이언트 ID 형식 감지됨")
        print("  -> gspread.oauth() 사용 (최초 실행 시 브라우저 인증 필요)")
        print("  -> 토큰 캐시: ~/.config/gspread/authorized_user.json")
        gc = gspread.oauth(
            credentials_filename=cred_path,
            authorized_user_filename=os.path.expanduser("~/.config/gspread/authorized_user.json"),
        )
        print("  [OK] OAuth2 인증 성공")

    else:
        raise ValueError(
            "credentials.json 형식 불명: " + str(list(json.load(open(cred_path)).keys())[:5])
            + "\n  서비스 계정 키(type=service_account)가 필요합니다."
            + "\n  GCP 콘솔 > IAM > 서비스 계정 > 키 다운로드"
        )

    return gc


def test_open_naver_form_sheet(gc):
    """[2] NAVER_FORM_ID 시트 열기"""
    _banner("테스트 2: 시트 열기 (ID: " + NAVER_FORM_ID + ")")
    sh = gc.open_by_key(NAVER_FORM_ID)
    print("  [OK] 시트 열기 성공: '" + sh.title + "'")
    return sh


def test_form_tab_exists(sh):
    """[3] 설문지 응답 탭 존재 확인"""
    _banner("테스트 3: '" + TAB_NAVER_FORM + "' 탭 확인")
    ws_names = [ws.title for ws in sh.worksheets()]
    print("  탭 목록: " + str(ws_names))
    if TAB_NAVER_FORM in ws_names:
        ws = sh.worksheet(TAB_NAVER_FORM)
        print("  [OK] '" + TAB_NAVER_FORM + "' 탭 존재")
        return ws
    else:
        ws = sh.get_worksheet(0)
        print("  [WARN] '" + TAB_NAVER_FORM + "' 탭 없음 -> 첫 번째 탭 '" + ws.title + "'으로 진행")
        return ws


def test_read_headers(ws):
    """[4] 헤더 행 읽기"""
    _banner("테스트 4: 헤더 읽기")
    try:
        headers = ws.row_values(1)
        if headers:
            preview = str(headers[:6]) + ("..." if len(headers) > 6 else "")
            print("  [OK] 헤더 " + str(len(headers)) + "개: " + preview)
        else:
            print("  [WARN] 헤더 행 비어있음 (새 시트)")
    except gspread.exceptions.APIError as e:
        print("  [FAIL] 읽기 실패: " + str(e))
        raise


def test_repository_method(gc):
    """[5] SheetFormResponseRepository 호출"""
    _banner("테스트 5: SheetFormResponseRepository.get_applicants_by_month()")
    from src.core.repositories.sheet_repository import SheetFormResponseRepository

    sh = gc.open_by_key(NAVER_FORM_ID)
    try:
        ws = sh.worksheet(TAB_NAVER_FORM)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.get_worksheet(0)
        print("  [WARN] 탭 없음, 첫 번째 탭으로 대체")

    repo = SheetFormResponseRepository(ws=ws)
    now = datetime.now(KST)
    applicants = repo.get_applicants_by_month(now.year, now.month)
    print("  [OK] get_applicants_by_month(" + str(now.year) + ", " + str(now.month) + ") -> " + str(len(applicants)) + "개")
    if applicants:
        print("       첫 응답 키: " + str(list(applicants[0].keys())))


def _print_summary(passed, failed):
    total = passed + failed
    _banner("결과: " + str(passed) + "/" + str(total) + " 통과")
    if failed == 0:
        print("  모든 통합 테스트 통과!")
    else:
        print("  " + str(failed) + "개 실패 - 위 에러를 확인하세요.")
    print()


def main():
    print("\n[TEST] A-3 Google Sheets 통합 테스트")
    print("   " + datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"))

    passed = failed = 0
    gc = ws = None

    steps = [
        ("gspread 인증",      lambda: test_gspread_auth()),
        ("시트 열기",          lambda: test_open_naver_form_sheet(gc)),
        ("탭 확인",           lambda: test_form_tab_exists(sh)),
        ("헤더 읽기",          lambda: test_read_headers(ws)),
        ("Repository 호출",   lambda: test_repository_method(gc)),
    ]

    # 순차 실행 (앞 단계 실패 시 중단)
    sh = None
    for name, fn in steps:
        try:
            result = fn()
            # 결과 저장
            if name == "gspread 인증":
                gc = result
            elif name == "시트 열기":
                sh = result
            elif name == "탭 확인":
                ws = result
            passed += 1
        except Exception as e:
            print("  [FAIL] " + name + ": " + str(e))
            failed += 1
            if name in ("gspread 인증", "시트 열기"):
                print("  -> 이후 테스트 건너뜀")
                break

    _print_summary(passed, failed)


if __name__ == "__main__":
    main()
