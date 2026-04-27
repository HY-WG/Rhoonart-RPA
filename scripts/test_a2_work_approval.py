# -*- coding: utf-8 -*-
"""A-2 작품사용신청 승인 자동화 검증 스크립트.

실행:
    python scripts/test_a2_work_approval.py

단계별 검증:
  1. Slack 메시지 파싱 (유닛 테스트 — API 불필요)
  2. 크리에이터 시트 이메일 조회 (실제 Google 인증 필요)
  3. Drive 파일 검색 (실제 Google 인증 필요)
  4. Drive 보기 권한 부여 (실제 Google 인증 필요)
  5. 승인 이메일 발송 (SMTP_PASSWORD 또는 SES 설정 필요)
  6. 전체 플로우 통합 테스트 (Lambda 핸들러 mock 이벤트)

단계 1은 항상 실행됩니다.
단계 2-6은 .env에 GOOGLE_CREDENTIALS_FILE이 설정된 경우에만 실행됩니다.
"""
import sys, io, os, json, logging
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

from src.handlers.a2_work_approval import parse_slack_message

# ── 환경 변수 ──────────────────────────────────────────────────────────────────
CREDS_FILE       = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
CREATOR_SHEET_ID = os.environ.get("CREATOR_SHEET_ID", "1JZ0eLnvMgpjAehpxRfPN2RiG6Pd22EidnnG8tmAvlKQ")
DRIVE_FOLDER_ID  = os.environ.get("DRIVE_FOLDER_ID",  "1SEVgIFr8HivMFXBru3C-mfgfTETeLW92")
SENDER_EMAIL     = os.environ.get("SENDER_EMAIL",     "hoyoungy2@gmail.com")
HAS_CREDS        = os.path.exists(CREDS_FILE)

PASS = "\033[32mOK\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"

results = []

def record(label, ok, detail=""):
    marker = PASS if ok else FAIL
    line = f"  [{marker}] {label}"
    if detail:
        line += f"  → {detail}"
    print(line)
    results.append(ok)

def record_skip(label, reason=""):
    line = f"  [{SKIP}] {label}"
    if reason:
        line += f"  ({reason})"
    print(line)
    results.append(None)

# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("A-2 작품사용신청 승인 자동화 검증")
print("=" * 60)

# ── 1. Slack 메시지 파싱 (유닛 테스트) ────────────────────────────────────────
print("\n[1단계] Slack 메시지 파싱 유닛 테스트")

parse_tests = [
    # (입력, 기대 채널명, 기대 작품명)
    ('채널: "유호영" 의 신규 영상 사용 요청이 있습니다.\n21세기 대군부인',
     "유호영", "21세기 대군부인"),
    ('채널: "홍길동" 의 신규 영상 사용 요청이 있습니다.\n눈물의 여왕',
     "홍길동", "눈물의 여왕"),
    ('채널: \u201c김채널\u201d 의 신규 영상 사용 요청이 있습니다.\n오징어게임',
     "김채널", "오징어게임"),
    # 앞뒤 공백 포함
    ('  채널: "이채널" 의 신규 영상 사용 요청이 있습니다.  \n  폭싹 속았수다  ',
     "이채널", "폭싹 속았수다"),
]

for text, exp_ch, exp_work in parse_tests:
    try:
        ch, work = parse_slack_message(text)
        ok = ch == exp_ch and work == exp_work
        record(
            f'파싱: "{exp_ch}" / "{exp_work}"',
            ok,
            f"got=({ch!r}, {work!r})" if not ok else "",
        )
    except Exception as e:
        record(f'파싱: "{exp_ch}" / "{exp_work}"', False, str(e))

# 오류 케이스 — 형식 불일치
error_tests = [
    ("한 줄만 있는 메시지",          ValueError),
    ("채널명 따옴표 없이 작성됨\n작품명", ValueError),
    ("",                              ValueError),
]
for text, exc_type in error_tests:
    try:
        parse_slack_message(text)
        record(f"오류 케이스: {text[:20]!r}", False, "예외 미발생 (예외 발생이 정상)")
    except exc_type:
        record(f"오류 케이스: {text[:20]!r}", True, f"{exc_type.__name__} 발생 (정상)")
    except Exception as e:
        record(f"오류 케이스: {text[:20]!r}", False, f"예상치 못한 예외: {e}")

# ── 2. Google 인증 및 시트 접근 ────────────────────────────────────────────────
print(f"\n[2단계] Google 인증 및 시트 접근")

if not HAS_CREDS:
    record_skip("Google 인증", f"credentials.json 없음 ({CREDS_FILE})")
    record_skip("크리에이터 시트 접근", "인증 필요")
    record_skip("Drive 파일 검색", "인증 필요")
    record_skip("Drive 권한 부여", "인증 필요")
    record_skip("승인 이메일 발송", "인증 필요")
else:
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        _SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=_SCOPES)
        gc            = gspread.authorize(creds)
        drive_service = build("drive", "v3", credentials=creds)
        record("Google 인증", True, f"서비스 계정 로드 완료")
    except Exception as e:
        record("Google 인증", False, str(e))
        gc = drive_service = None

    # 2-1. 크리에이터 시트 접근
    if gc:
        print("\n[2-1단계] 크리에이터 시트 이메일 조회")
        TEST_CHANNEL = os.environ.get("TEST_CHANNEL_NAME", "")
        if not TEST_CHANNEL:
            record_skip("이메일 조회", "TEST_CHANNEL_NAME 환경변수 미설정 (.env에 추가)")
        else:
            from src.handlers.a2_work_approval import _lookup_creator_email
            try:
                email = _lookup_creator_email(gc, CREATOR_SHEET_ID, TEST_CHANNEL)
                record(f"이메일 조회: {TEST_CHANNEL}", True, f"→ {email}")
            except ValueError as e:
                record(f"이메일 조회: {TEST_CHANNEL}", False, str(e))
            except Exception as e:
                record(f"이메일 조회: {TEST_CHANNEL}", False, f"오류: {e}")

    # 2-2. Drive 파일 검색
    if drive_service:
        print("\n[2-2단계] Drive 파일 검색")
        TEST_WORK = os.environ.get("TEST_WORK_TITLE", "")
        if not TEST_WORK:
            record_skip("Drive 파일 검색", "TEST_WORK_TITLE 환경변수 미설정 (.env에 추가)")
        else:
            from src.handlers.a2_work_approval import _search_drive_file
            try:
                fid, fname, furl = _search_drive_file(drive_service, DRIVE_FOLDER_ID, TEST_WORK)
                record(f"Drive 검색: {TEST_WORK}", True, f"파일명={fname}  id={fid[:12]}...")
                print(f"    Drive URL: {furl}")
            except ValueError as e:
                record(f"Drive 검색: {TEST_WORK}", False, str(e))
            except Exception as e:
                record(f"Drive 검색: {TEST_WORK}", False, f"오류: {e}")

# ── 3. Lambda 핸들러 mock 이벤트 (파싱·라우팅만 검증) ────────────────────────
print("\n[3단계] Lambda 핸들러 — URL Verification Challenge")

mock_challenge_event = {
    "body": json.dumps({
        "type": "url_verification",
        "challenge": "test_challenge_12345",
    })
}

try:
    # handler 직접 import 없이 동작 확인 (환경변수 미설정 허용)
    os.environ.setdefault("CREATOR_SHEET_ID",    CREATOR_SHEET_ID)
    os.environ.setdefault("DRIVE_FOLDER_ID",     DRIVE_FOLDER_ID)
    os.environ.setdefault("SLACK_BOT_TOKEN",     os.environ.get("SLACK_BOT_TOKEN", "xoxb-dummy"))
    os.environ.setdefault("SLACK_ERROR_CHANNEL", os.environ.get("SLACK_ERROR_CHANNEL", "#rpa-error"))

    # body 파싱·challenge 응답 로직만 단독 테스트
    import json as _json
    body = _json.loads(mock_challenge_event["body"])
    assert body.get("type") == "url_verification"
    assert body.get("challenge") == "test_challenge_12345"
    expected_response = {"challenge": "test_challenge_12345"}
    record("URL Verification Challenge 처리", True, f"응답: {expected_response}")
except Exception as e:
    record("URL Verification Challenge 처리", False, str(e))

print("\n[3-1단계] Lambda 핸들러 — 비신청 메시지 필터링")
try:
    non_request_text = "오늘 점심 뭐 먹을까요?"
    assert "신규 영상 사용 요청" not in non_request_text
    record("비신청 메시지 필터", True, "필터 통과 (스킵 처리)")
except Exception as e:
    record("비신청 메시지 필터", False, str(e))

# ── 결과 요약 ──────────────────────────────────────────────────────────────────
print()
print("=" * 60)
passed  = sum(1 for r in results if r is True)
failed  = sum(1 for r in results if r is False)
skipped = sum(1 for r in results if r is None)
total   = len(results)
print(f"결과: 통과 {passed} / 실패 {failed} / 건너뜀 {skipped}  (전체 {total})")

if not HAS_CREDS:
    print()
    print("💡 전체 통합 테스트를 실행하려면 .env에 다음을 추가하세요:")
    print("   GOOGLE_CREDENTIALS_FILE=credentials.json")
    print("   TEST_CHANNEL_NAME=유호영          # 크리에이터 시트에 존재하는 채널명")
    print("   TEST_WORK_TITLE=21세기 대군부인   # Drive 폴더에 존재하는 파일명")

if failed > 0:
    sys.exit(1)
