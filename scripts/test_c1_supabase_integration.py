"""C-1 리드 발굴 ↔ Supabase 통합 테스트 스크립트.

실행:
    python scripts/test_c1_supabase_integration.py

3단계로 구성:
  [1] Supabase lead_channels 직접 upsert / read / cleanup  (REST API)
  [2] C-1 YouTubeShortsCrawler 실행 + 결과를 Supabase에 upsert  (소규모: max_channels=5)
  [3] Supabase에서 upsert된 레코드 조회 및 검증

환경 변수:
  SUPABASE_URL              Supabase 프로젝트 URL
  SUPABASE_SERVICE_ROLE_KEY Service Role 키
  YOUTUBE_API_KEY           YouTube Data API v3 키
"""
from __future__ import annotations

import os
import sys
import json
from datetime import datetime
from unittest.mock import MagicMock

# ── 프로젝트 루트를 path에 추가 ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests as _requests
import pytz

KST = pytz.timezone("Asia/Seoul")
LEAD_TABLE = "lead_channels"
TEST_CHANNEL_ID = "UC_INTEGRATION_TEST_C1_001"

# ── Supabase REST 헬퍼 ────────────────────────────────────────────────────────
SUPA_URL = os.environ["SUPABASE_URL"]
SUPA_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": SUPA_KEY,
    "Authorization": f"Bearer {SUPA_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def sb_upsert(table: str, rows: list[dict], on_conflict: str) -> list[dict]:
    r = _requests.post(
        f"{SUPA_URL}/rest/v1/{table}",
        headers={**HEADERS, "Prefer": f"return=representation,resolution=merge-duplicates"},
        params={"on_conflict": on_conflict},
        json=rows,
    )
    r.raise_for_status()
    return r.json()


def sb_select(table: str, filters: dict | None = None) -> list[dict]:
    params = filters or {}
    r = _requests.get(f"{SUPA_URL}/rest/v1/{table}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def sb_delete(table: str, eq_col: str, eq_val: str) -> None:
    r = _requests.delete(
        f"{SUPA_URL}/rest/v1/{table}",
        headers=HEADERS,
        params={eq_col: f"eq.{eq_val}"},
    )
    r.raise_for_status()


# ── STEP 1: lead_channels 직접 upsert/read/cleanup ──────────────────────────
def step1_direct_lead_upsert() -> bool:
    print("\n[STEP 1] lead_channels 직접 upsert/read/cleanup")
    now = datetime.now(KST).isoformat()
    test_row = {
        "channel_id": TEST_CHANNEL_ID,
        "channel_name": "C1 통합테스트 채널",
        "channel_url": "https://www.youtube.com/@c1-integration-test",
        "platform": "youtube",
        "genre": "drama_movie",
        "grade": "B",
        "monthly_views": 8_000_000,
        "subscriber_count": 50_000,
        "email": None,
        "email_status": "unsent",
        "discovered_at": now,
        "last_updated_at": now,
    }

    # Upsert
    try:
        result = sb_upsert(LEAD_TABLE, [test_row], on_conflict="channel_id")
        print(f"  ✅ upsert 성공: id={result[0].get('id') if result else '(returned empty)'}")
    except Exception as e:
        print(f"  ❌ upsert 실패: {e}")
        return False

    # Read back
    try:
        rows = sb_select(LEAD_TABLE, {"channel_id": f"eq.{TEST_CHANNEL_ID}"})
        assert rows, "조회된 레코드 없음"
        row = rows[0]
        assert row["channel_name"] == "C1 통합테스트 채널", f"이름 불일치: {row['channel_name']}"
        assert row["grade"] == "B", f"등급 불일치: {row['grade']}"
        assert row["monthly_views"] == 8_000_000, f"조회수 불일치: {row['monthly_views']}"
        print(f"  ✅ read 성공: channel_id={row['channel_id']}, grade={row['grade']}, "
              f"monthly_views={row['monthly_views']:,}")
    except Exception as e:
        print(f"  ❌ read 실패: {e}")
        return False

    # Upsert 업데이트 (같은 channel_id → 덮어쓰기)
    test_row["grade"] = "A"
    test_row["monthly_views"] = 25_000_000
    try:
        sb_upsert(LEAD_TABLE, [test_row], on_conflict="channel_id")
        rows2 = sb_select(LEAD_TABLE, {"channel_id": f"eq.{TEST_CHANNEL_ID}"})
        assert rows2[0]["grade"] == "A", "upsert 업데이트 실패"
        assert rows2[0]["monthly_views"] == 25_000_000, "monthly_views 업데이트 실패"
        print(f"  ✅ upsert 업데이트(A, 25M) 확인")
    except Exception as e:
        print(f"  ❌ upsert 업데이트 실패: {e}")
        return False

    # Cleanup
    try:
        sb_delete(LEAD_TABLE, "channel_id", TEST_CHANNEL_ID)
        remaining = sb_select(LEAD_TABLE, {"channel_id": f"eq.{TEST_CHANNEL_ID}"})
        assert not remaining, "삭제 후 레코드 남아있음"
        print(f"  ✅ cleanup 성공")
    except Exception as e:
        print(f"  ❌ cleanup 실패: {e}")
        return False

    return True


# ── SupabaseLeadRepository (requests 기반 경량 구현) ─────────────────────────
class RequestsLeadRepository:
    """Python supabase 클라이언트 대신 requests로 구현한 lead repository."""

    def upsert_leads(self, leads) -> int:
        if not leads:
            return 0
        rows = [self._to_row(lead) for lead in leads]
        try:
            sb_upsert(LEAD_TABLE, rows, on_conflict="channel_id")
            return len(rows)
        except Exception as e:
            print(f"  [repo] upsert 오류: {e}")
            return 0

    @staticmethod
    def _to_row(lead) -> dict:
        now = datetime.utcnow().isoformat()
        return {
            "channel_id": lead.channel_id,
            "channel_name": lead.channel_name,
            "channel_url": lead.channel_url,
            "platform": lead.platform,
            "genre": lead.genre.value if hasattr(lead.genre, "value") else str(lead.genre),
            "grade": lead.tier,
            "monthly_views": lead.monthly_shorts_views or 0,
            "subscriber_count": lead.subscribers or 0,
            "email": lead.email,
            "email_status": "unsent",
            "discovered_at": (
                lead.discovered_at.isoformat()
                if lead.discovered_at else now
            ),
            "last_updated_at": now,
        }

    def get_leads_for_email(self, filters):
        return []

    def update_lead_email_status(self, channel_id: str, status: str) -> None:
        pass


# ── STEP 2: C-1 실제 탐색 → Supabase upsert ─────────────────────────────────
def step2_c1_run_and_upsert() -> dict | None:
    print("\n[STEP 2] C-1 YouTubeShortsCrawler 실행 + Supabase upsert (max_channels=5)")

    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        print("  ⚠️  YOUTUBE_API_KEY 미설정 → STEP 2 스킵")
        return None

    try:
        from src.handlers.c1_lead_filter import run as c1_run
    except ImportError as e:
        print(f"  ❌ c1_lead_filter import 실패: {e}")
        return None

    lead_repo = RequestsLeadRepository()
    log_repo = MagicMock()          # 로그는 mock 처리
    slack_notifier = MagicMock()    # Slack 알림은 mock 처리

    # 시드 채널 URL — 시트 없이 하드코딩 (통합 테스트용 소규모)
    seed_urls = [
        "https://www.youtube.com/@라면무비",
        "https://www.youtube.com/@DRAMACOOL",
    ]

    try:
        result = c1_run(
            lead_repo=lead_repo,
            log_repo=log_repo,
            slack_notifier=slack_notifier,
            api_key=api_key,
            seed_sheet_id="",       # seed_urls 직접 전달이므로 무시됨
            seed_sheet_gid="1224056617",
            max_channels=5,         # 소규모로 API 유닛 절약
            seed_urls=seed_urls,
        )
        print(f"  ✅ C-1 실행 완료:")
        print(f"     발굴 채널: {result['discovered']}개")
        print(f"     A={result['tier_a']}, B={result['tier_b']}, "
              f"B?={result['tier_b_potential']}, C={result['tier_c']}")
        print(f"     Supabase upsert: {result['upserted']}건")
        return result
    except Exception as e:
        print(f"  ❌ C-1 실행 오류: {e}")
        import traceback; traceback.print_exc()
        return None


# ── STEP 3: Supabase lead_channels 조회 확인 ─────────────────────────────────
def step3_verify_leads(c1_result: dict | None) -> bool:
    print("\n[STEP 3] Supabase lead_channels 조회 확인")
    try:
        rows = sb_select(LEAD_TABLE)
        print(f"  ✅ lead_channels 총 {len(rows)}건")
        if rows:
            for row in rows[:5]:
                print(f"     • {row.get('channel_name','?')} | grade={row.get('grade')} "
                      f"| monthly_views={row.get('monthly_views', 0):,} "
                      f"| discovered_at={str(row.get('discovered_at',''))[:10]}")
            if len(rows) > 5:
                print(f"     ... 외 {len(rows)-5}건")

        if c1_result and c1_result.get("upserted", 0) > 0:
            upserted = c1_result["upserted"]
            assert len(rows) >= upserted, (
                f"upsert {upserted}건 했는데 조회된 레코드({len(rows)})가 더 적음"
            )
            print(f"  ✅ C-1 upsert {upserted}건 검증 완료")
        return True
    except Exception as e:
        print(f"  ❌ 검증 실패: {e}")
        return False


# ── 메인 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("C-1 ↔ Supabase 통합 테스트")
    print("=" * 60)

    results = {}
    results["step1"] = step1_direct_lead_upsert()
    c1_result = step2_c1_run_and_upsert()
    results["step2"] = c1_result is not None
    results["step3"] = step3_verify_leads(c1_result)

    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    labels = {
        "step1": "lead_channels 직접 upsert/read/cleanup",
        "step2": "C-1 crawler → Supabase upsert",
        "step3": "Supabase 조회 검증",
    }
    all_pass = True
    for key, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon} {labels[key]}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("🎉 모든 테스트 통과!")
        sys.exit(0)
    else:
        print("💥 일부 테스트 실패")
        sys.exit(1)
