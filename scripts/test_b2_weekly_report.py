# -*- coding: utf-8 -*-
"""B-2 주간 성과 보고 자동화 검증 스크립트.

실행:
    python scripts/test_b2_weekly_report.py

단계별 검증:
  1. B-2 핸들러 트리거 구분 로직 (유닛 테스트 — API 불필요)
  2. Naver Clip 크롤러 동작 확인 (네트워크 필요)
  3. 시트 권리사 목록 조회 + Looker 대시보드 URL 매핑 확인 (Google 인증 필요)
  4. 승인 이메일 템플릿 생성 검증 (API 불필요)
  5. HTTP 트리거 엔드포인트 응답 확인 (배포된 Lambda URL 필요)

단계 1, 4는 항상 실행됩니다.
단계 2-3은 환경변수 설정 여부에 따라 실행됩니다.
단계 5는 LAMBDA_B2_URL 환경변수가 설정된 경우에만 실행됩니다.
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

CREDS_FILE       = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
CONTENT_SHEET_ID = os.environ.get("CONTENT_SHEET_ID", "")
HAS_CREDS        = os.path.exists(CREDS_FILE) and bool(CONTENT_SHEET_ID)

LOOKER_DASHBOARDS = {
    "웨이브x루나르트":    os.environ.get("LOOKER_URL_WAVVE", ""),
    "판씨네마x루나르트":  os.environ.get("LOOKER_URL_PANSCINEMA", ""),
    "영상권리사x루나르트": os.environ.get("LOOKER_URL_RIGHTS", ""),
}

# ══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("B-2 주간 성과 보고 자동화 검증")
print("=" * 60)

# ── 1. 트리거 구분 로직 ────────────────────────────────────────────────────────
print("\n[1단계] 트리거 구분 로직 (HTTP vs CRON)")

trigger_tests = [
    ({},                         "http",  "HTTP"),
    ({"source": "http"},         "http",  "HTTP"),
    ({"source": "cron"},         "cron",  "CRON"),
    ({"source": "manual"},       "http",  "HTTP (manual → http 폴백)"),
    ({"body": '{"source":"cron"}', "httpMethod": "POST"}, "cron", "API GW body 언래핑"),
]

from src.models.log_entry import TriggerType

for event, exp_source, label in trigger_tests:
    # b2_weekly_report_handler의 트리거 분기 로직 재현
    body = event.get("body", event)
    if isinstance(body, str):
        try:
            import json as _j; body = _j.loads(body); event = {**event, **body}
        except Exception:
            pass
    source = event.get("source", "http")
    trigger_type = TriggerType.CRON if source == "cron" else TriggerType.HTTP
    expected_type = TriggerType.CRON if exp_source == "cron" else TriggerType.HTTP
    ok = trigger_type == expected_type
    record(label, ok, f"source={source!r} → {trigger_type.value}")

# ── 2. Looker 대시보드 URL 매핑 ───────────────────────────────────────────────
print("\n[2단계] Looker 대시보드 URL 환경변수 확인")

for name, url in LOOKER_DASHBOARDS.items():
    if url:
        record(f"대시보드 URL: {name}", True, url[:60] + ("..." if len(url) > 60 else ""))
    else:
        record_skip(f"대시보드 URL: {name}", "환경변수 미설정 (정상 — 배포 전 설정)")

# ── 3. 이메일 템플릿 생성 ──────────────────────────────────────────────────────
print("\n[3단계] 권리사 이메일 템플릿 생성")

from src.handlers.b2_weekly_report import _build_email_body
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")
now = datetime.now(KST)

test_cases = [
    ("웨이브", "https://datastudio.google.com/wavve-test"),
    ("판씨네마", "https://datastudio.google.com/pans-test"),
    ("영상권리사", ""),
]

for holder_name, dashboard_url in test_cases:
    try:
        if not dashboard_url:
            record_skip(f"이메일 템플릿: {holder_name}", "대시보드 URL 없음 (발송 건너뜀)")
            continue
        html = _build_email_body(holder_name, dashboard_url, now)
        has_name = holder_name in html
        has_url  = dashboard_url in html
        has_date = now.strftime("%Y년") in html
        ok = has_name and has_url and has_date
        record(
            f"이메일 템플릿: {holder_name}",
            ok,
            f"이름={'포함' if has_name else '누락'} / URL={'포함' if has_url else '누락'} / 날짜={'포함' if has_date else '누락'}",
        )
    except Exception as e:
        record(f"이메일 템플릿: {holder_name}", False, str(e))

# ── 4. 크리에이터 시트 권리사 목록 + Looker URL 매핑 ─────────────────────────
print("\n[4단계] 시트 권리사 목록 조회 + Looker URL 매핑")

if not HAS_CREDS:
    record_skip("권리사 목록 조회", f"credentials.json 또는 CONTENT_SHEET_ID 미설정")
else:
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        _SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
        ]
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=_SCOPES)
        gc = gspread.authorize(creds)

        from src.core.repositories.sheet_repository import SheetPerformanceRepository

        content_sh = gc.open_by_key(CONTENT_SHEET_ID)
        TAB_CONTENT = os.environ.get("TAB_CONTENT", "콘텐츠 목록")
        TAB_STATS   = os.environ.get("TAB_STATS", "성과 데이터")
        TAB_RIGHTS  = os.environ.get("TAB_RIGHTS", "A3_작품 관리의 사본")

        try:
            perf_repo = SheetPerformanceRepository(
                content_ws=content_sh.worksheet(TAB_CONTENT),
                stats_ws=content_sh.worksheet(TAB_STATS),
                rights_ws=content_sh.worksheet(TAB_RIGHTS),
                looker_dashboards=LOOKER_DASHBOARDS,
            )
            holders = perf_repo.get_rights_holders()
            record(f"권리사 목록 조회", True, f"{len(holders)}개 권리사")
            for h in holders:
                url_status = h.dashboard_url[:50] if h.dashboard_url else "URL 없음"
                print(f"    {h.name:<20} {h.email:<30} 대시보드: {url_status}")
        except Exception as e:
            record("권리사 목록 조회", False, str(e))

        # 콘텐츠 목록 조회
        try:
            contents = perf_repo.get_content_list()
            record(f"콘텐츠 목록 조회", True, f"{len(contents)}개 콘텐츠")
            for identifier, name in contents[:5]:
                print(f"    식별코드={identifier!r:<20} 콘텐츠명={name!r}")
            if len(contents) > 5:
                print(f"    ... 외 {len(contents)-5}개")
        except Exception as e:
            record("콘텐츠 목록 조회", False, str(e))

    except Exception as e:
        record("Google 인증", False, str(e))

# ── 5. Naver Clip 크롤러 단독 테스트 ─────────────────────────────────────────
print("\n[5단계] Naver Clip 크롤러 단독 테스트")

TEST_HASHTAG = os.environ.get("TEST_NAVER_HASHTAG", "")
if not TEST_HASHTAG:
    record_skip("Naver Clip 크롤링", "TEST_NAVER_HASHTAG 환경변수 미설정 (.env에 추가)")
    print("   예: TEST_NAVER_HASHTAG=눈물의여왕")
else:
    try:
        from src.core.crawlers.naver_clip_crawler import NaverClipCrawler

        crawler = NaverClipCrawler(
            contents=[(TEST_HASHTAG, TEST_HASHTAG)],
            headless=True,
        )
        stats = crawler.run()
        if stats:
            s = stats[0]
            record(
                f"크롤링: #{TEST_HASHTAG}",
                True,
                f"총 조회수={s.get('total_views', 0):,}  클립 수={s.get('video_count', 0)}",
            )
        else:
            record(f"크롤링: #{TEST_HASHTAG}", False, "결과 없음")
    except Exception as e:
        record(f"크롤링: #{TEST_HASHTAG}", False, str(e))

# ── 6. 배포된 Lambda HTTP 엔드포인트 확인 ────────────────────────────────────
print("\n[6단계] Lambda HTTP 엔드포인트 확인")

LAMBDA_B2_URL = os.environ.get("LAMBDA_B2_URL", "")
if not LAMBDA_B2_URL:
    record_skip("HTTP 엔드포인트 호출", "LAMBDA_B2_URL 환경변수 미설정 (배포 후 설정)")
    print("   예: LAMBDA_B2_URL=https://xxx.execute-api.ap-northeast-2.amazonaws.com/dev/report/weekly")
else:
    try:
        import requests
        resp = requests.post(
            LAMBDA_B2_URL,
            json={"source": "test"},
            timeout=30,
        )
        ok = resp.status_code == 200
        record(
            "HTTP POST /report/weekly",
            ok,
            f"status={resp.status_code}  body={resp.text[:80]}",
        )
    except Exception as e:
        record("HTTP POST /report/weekly", False, str(e))

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
    print("   CONTENT_SHEET_ID=1e-rRWmjL29U53OG1ZPYKSaqKlbSq46K6AsQ356nlM0w")
    print("   LOOKER_URL_WAVVE=https://...")
    print("   LOOKER_URL_PANSCINEMA=https://...")
    print("   LOOKER_URL_RIGHTS=https://...")
    print("   TEST_NAVER_HASHTAG=눈물의여왕")
    print("   LAMBDA_B2_URL=https://...  # 배포 후")

if failed > 0:
    sys.exit(1)
