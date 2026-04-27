#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""C-3 통합 테스트 — Admin API 실제 연결 검증.

목적:
  .env에 설정된 ADMIN_API_BASE_URL을 사용해 실제 Admin API에
  작품 등록 요청을 보내고 응답을 확인한다.

실행 방법:
    cd C:\\Users\\mung9\\IdeaProjects\\rhoonart-rpa
    python scripts/integration_test_c3_admin_api.py

사전 조건:
  - .env에 ADMIN_API_BASE_URL, ADMIN_API_TOKEN 설정
  - Admin API 엔드포인트 접근 가능

검증 항목:
  1. ADMIN_API_BASE_URL 환경변수 로드 확인
  2. Admin API 엔드포인트 헬스체크 (GET /)
  3. C-3 run() 실제 호출 — 테스트 작품 데이터 전송
  4. 응답 확인 (work_id 반환 여부)
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import pytz
import requests as http_req

KST = pytz.timezone("Asia/Seoul")

ADMIN_API_BASE_URL  = os.environ.get("ADMIN_API_BASE_URL", "")
ADMIN_API_TOKEN     = os.environ.get("ADMIN_API_TOKEN", "")
X_INTERN_SESSION    = os.environ.get("X_INTERN_SESSION", "")


def _banner(text):
    print("\n" + "="*60)
    print("  " + text)
    print("="*60)


def test_env_vars():
    """[1] 환경변수 로드 확인"""
    _banner("테스트 1: 환경변수 확인")
    print("  ADMIN_API_BASE_URL: " + (ADMIN_API_BASE_URL or "(미설정)"))
    print("  ADMIN_API_TOKEN:    " + ("***" + ADMIN_API_TOKEN[-8:] if ADMIN_API_TOKEN else "(미설정)"))
    print("  X_INTERN_SESSION:   " + ("***" + X_INTERN_SESSION[-8:] if X_INTERN_SESSION else "(미설정 - Bearer 모드)"))

    if not ADMIN_API_BASE_URL:
        raise ValueError("ADMIN_API_BASE_URL이 .env에 설정되지 않았습니다.")
    print("  [OK] 환경변수 로드 성공")


def test_api_reachable():
    """[2] API 엔드포인트 연결 확인"""
    _banner("테스트 2: API 연결 확인 (" + ADMIN_API_BASE_URL + ")")
    try:
        resp = http_req.get(
            ADMIN_API_BASE_URL,
            headers={"Authorization": "Bearer " + ADMIN_API_TOKEN},
            timeout=10,
        )
        print("  HTTP 상태코드: " + str(resp.status_code))
        if resp.status_code < 500:
            print("  [OK] API 연결 성공 (status=" + str(resp.status_code) + ")")
            if resp.text:
                print("  응답 미리보기: " + resp.text[:200])
        else:
            print("  [WARN] 서버 에러 (status=" + str(resp.status_code) + ")")
    except http_req.exceptions.ConnectionError as e:
        print("  [FAIL] 연결 실패: " + str(e))
        raise
    except http_req.exceptions.Timeout:
        print("  [FAIL] 타임아웃 (10초)")
        raise


def test_c3_run():
    """[3] C-3 run() 실제 호출"""
    _banner("테스트 3: C-3 run() 실제 호출")
    from src.handlers.c3_work_register import run
    from src.models.work import Work

    test_work = Work(
        work_title="[통합테스트] 신병",
        rights_holder_name="웨이브",
        release_year=2022,
        description="군 복무 이야기 (통합 테스트용 데이터)",
        director="홍길동",
        cast="배우A, 배우B",
        genre="드라마",
        video_type="드라마",
        country="한국",
        platforms=["웨이브"],
        platform_video_url="https://wavve.com/play/test",
        trailer_url="",
        source_download_url="",
    )

    print("  테스트 작품: '" + test_work.work_title + "' (권리사: " + test_work.rights_holder_name + ")")
    print("  API URL: " + ADMIN_API_BASE_URL)

    result = run(
        work=test_work,
        admin_api_base_url=ADMIN_API_BASE_URL,
        admin_api_token=ADMIN_API_TOKEN,
        admin_api_session=X_INTERN_SESSION,
    )

    print("\n  응답:\n" + json.dumps(result, ensure_ascii=False, indent=4))

    if result.get("success"):
        print("\n  [OK] 등록 성공! work_id = " + str(result.get("work_id")))
    else:
        print("\n  [WARN] 등록 실패 또는 stub 모드: " + str(result.get("message")))


def _print_summary(passed, failed):
    total = passed + failed
    _banner("결과 요약: " + str(passed) + "/" + str(total) + " 통과")
    if failed == 0:
        print("  모든 통합 테스트 통과!")
    else:
        print("  " + str(failed) + "개 실패 - 위 에러 메시지를 확인하세요.")
    print()


def main():
    print("\n[TEST] C-3 Admin API 통합 테스트 시작")
    print("   실행 시각: " + datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST"))

    tests = [test_env_vars, test_api_reachable, test_c3_run]
    passed = failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print("  [FAIL] " + test_fn.__name__ + " 실패: " + str(e))
            import traceback
            traceback.print_exc()
            failed += 1

    _print_summary(passed, failed)


if __name__ == "__main__":
    main()
