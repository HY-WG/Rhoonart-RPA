"""YouTubeShortsCrawler 동작 검증.

실행 범위를 줄이기 위해 max_channels=30으로 제한.
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

from src.core.crawlers.youtube_shorts_crawler import (
    YouTubeShortsCrawler,
    load_seed_urls_from_sheet,
    block_channels,
    unblock_channels,
    update_manual_drama_titles,
)

API_KEY  = os.environ.get("YOUTUBE_API_KEY", "")
SHEET_ID = os.environ.get("SEED_CHANNEL_SHEET_ID", "")
GID      = os.environ.get("SEED_CHANNEL_GID", "")

# ── [선택] 수동 드라마 제목 목록 업데이트 ────────────────────────────────
# 담당자가 최근 6개월 인기 드라마·영화 목록을 직접 관리할 경우 아래 주석 해제.
# 지정한 제목으로 Layer B 검색 → 더 정밀한 발굴 가능.
# (auto_titles는 덮어쓰지 않고 manual_titles만 교체됨)
#
# update_manual_drama_titles([
#     "눈물의 여왕",
#     "졸업",
#     "연인",
#     "이재, 곧 죽습니다",
#     "오징어게임",
#     "정년이",
#     "폭싹 속았수다",
# ])

print("=" * 60)
print("YouTubeShortsCrawler 검증 (최대 30채널)")
print("=" * 60)

# 1. 시드 URL 로드
seed_urls = load_seed_urls_from_sheet(SHEET_ID, GID)
print(f"\n[시드 채널] {len(seed_urls)}개 URL 로드 완료")
for u in seed_urls[:5]:
    print(f"  {u}")
if len(seed_urls) > 5:
    print(f"  ... 외 {len(seed_urls)-5}개")

# 2. 크롤러 실행 (검증용: max_channels=30)
crawler = YouTubeShortsCrawler(
    api_key=API_KEY,
    seed_channel_urls=seed_urls,
    max_channels=30,
)
results = crawler.discover()

# 3. 결과 출력
print(f"\n{'='*60}")
print(f"발굴 채널 총 {len(results)}개")
print(f"{'='*60}")

tier_a = [r for r in results if r.tier == "A"]
tier_b = [r for r in results if r.tier in ("B", "B?")]
tier_c = [r for r in results if r.tier == "C"]

print(f"\n[A등급] 월간 숏츠 조회 2,000만+ ({len(tier_a)}개)")
for ch in sorted(tier_a, key=lambda x: -x.monthly_shorts_views):
    growth = f" / 성장률 {ch.growth_rate:.1%}" if ch.growth_rate is not None else ""
    print(f"  {ch.name:<20} 월간={ch.monthly_shorts_views:>12,}  구독={ch.subscriber_count:>8,}{growth}")

print(f"\n[B등급] 성장 잠재 채널 ({len(tier_b)}개)")
for ch in sorted(tier_b, key=lambda x: -(x.growth_rate or 0)):
    growth = f"성장률 {ch.growth_rate:.1%}" if ch.growth_rate is not None else f"월간 {ch.monthly_shorts_views:,} (첫실행)"
    print(f"  {ch.name:<20} {growth}  구독={ch.subscriber_count:>8,}")

print(f"\n[C등급] 기준 미달 ({len(tier_c)}개) — 생략")

# 4. JSON 저장
out_path = "scripts/youtube_shorts_result.json"
import dataclasses
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(
        [dataclasses.asdict(r) for r in results],
        f, ensure_ascii=False, indent=2
    )
print(f"\n결과 저장: {out_path}")
print(f"쿼터 사용: 크롤러 내부 로그 참고")

# 5. 블록리스트 현황 출력
bl = crawler.get_blocklist()
if bl:
    print(f"\n{'='*60}")
    print(f"[블록리스트] 영구 제외 채널 {len(bl)}개")
    for cid, info in bl.items():
        print(f"  {info.get('name', cid):<22} 사유: {info.get('reason','')}")
else:
    print("\n[블록리스트] 등록된 채널 없음")

# ──────────────────────────────────────────────────────────────────────────
# 블록리스트 등록 예시 (검증 후 수동으로 주석 해제하여 실행)
# ──────────────────────────────────────────────────────────────────────────
# block_channels([
#     {"channel_id": "UC-X9afa4j1s8o3K-pOeVkNQ", "name": "드라마톡톡"},
# ], reason="드라마 썰 채널 — 판권 영상 아님, 계약 대상 아님")
#
# unblock_channels(["UC-X9afa4j1s8o3K-pOeVkNQ"])  # 실수 취소 시
