"""NaverClipCrawler 동작 검증."""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, ".")

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from src.core.crawlers.naver_clip_crawler import NaverClipCrawler

TEST_CONTENTS = [
    ("재벌집막내아들", "재벌집 막내아들"),
    ("런닝맨", "런닝맨"),
]

print("=" * 60)
print("NaverClipCrawler 테스트 (최대 200클립/태그)")
print("=" * 60)

crawler = NaverClipCrawler(TEST_CONTENTS, max_clips=200)
results = crawler.crawl()

print(f"\n결과 ({len(results)}개):")
for r in results:
    print(f"\n  [{r['channel_id']}] {r['channel_name']}")
    print(f"    총 클립: {r['video_count']}개")
    print(f"    누적 조회: {r['total_views']:,}")
    print(f"    주간 조회: {r['weekly_views']:,}")
    print(f"    주간 신규: {r['new_clips_week']}개")
    print(f"    총 좋아요: {r['total_likes']:,}")

with open("scripts/naver_clip_crawler_test.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\n결과 저장: scripts/naver_clip_crawler_test.json")
