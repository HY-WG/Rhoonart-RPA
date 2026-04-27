"""셀렉터 실사이트 검증 스크립트.

실행:
    python scripts/verify_selectors.py

각 셀렉터의 매칭 여부를 확인하고 정확도(matched/total)를 출력한다.
"""
import sys
import io
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import sync_playwright, Page


# ── 검증 대상 ───────────────────────────────────────────────────

PLAYBOARD_URL = "https://playboard.co/ko/chart/KR/24/shorts/monthly"
NAVER_CLIP_URL = "https://clip.naver.com/hashtag/재벌집막내아들"  # 예시 식별코드


@dataclass
class SelectorResult:
    name: str
    selector: str
    matched: bool
    sample_text: str = ""
    note: str = ""


@dataclass
class SiteReport:
    site: str
    url: str
    results: list[SelectorResult] = field(default_factory=list)

    @property
    def score(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.matched) / len(self.results)

    @property
    def critical_score(self) -> float:
        """핵심 셀렉터(row/name/views)만의 점수."""
        critical = [r for r in self.results if r.name in ("row", "channel_name", "monthly_views", "total_views", "clip_count")]
        if not critical:
            return 0.0
        return sum(1 for r in critical if r.matched) / len(critical)


# ── 검증 로직 ───────────────────────────────────────────────────

def _try_selectors(page: Page, selectors: list[str], timeout: int = 3000) -> tuple[bool, str, str]:
    """셀렉터 목록 순서대로 시도. (matched, winning_selector, sample_text) 반환."""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count():
                text = loc.inner_text(timeout=timeout).strip()[:80]
                return True, sel, text
        except Exception:
            continue
    return False, "", ""


def verify_playboard(page: Page) -> SiteReport:
    report = SiteReport(site="Playboard (C-1)", url=PLAYBOARD_URL)
    print(f"\n{'='*60}")
    print(f"[Playboard] {PLAYBOARD_URL}")
    print(f"{'='*60}")

    try:
        page.goto(PLAYBOARD_URL, wait_until="networkidle", timeout=30_000)
    except Exception as e:
        print(f"  페이지 로드 실패: {e}")
        return report

    # 1. 채널 행 (row)
    row_selectors = ["li.chart_item", ".chart-item", "[class*='chartItem']", "tr.channel-row"]
    matched, winning, sample = _try_selectors(page, row_selectors)
    report.results.append(SelectorResult("row", winning or row_selectors[0], matched, sample))
    _print_result("채널 행 (row)", matched, winning, sample)

    # row가 잡혀야 하위 셀렉터 검증 가능
    if matched:
        row = page.locator(winning).first

        # 2. 채널 링크
        link_sel = "a[href*='/channel/']"
        try:
            el = row.locator(link_sel).first
            link_matched = el.count() > 0
            href = el.get_attribute("href") or "" if link_matched else ""
        except Exception:
            link_matched, href = False, ""
        report.results.append(SelectorResult("channel_link", link_sel, link_matched, href))
        _print_result("채널 링크", link_matched, link_sel, href)

        # 3. 채널명
        name_selectors = [".channel_name", ".channel-name", "[class*='channelName']"]
        matched2, winning2, sample2 = _try_selectors(row, name_selectors)
        report.results.append(SelectorResult("channel_name", winning2 or name_selectors[0], matched2, sample2))
        _print_result("채널명", matched2, winning2, sample2)

        # 4. 월간 조회수
        views_selectors = [".view_count", ".views", "[class*='viewCount']", "td:nth-child(4)"]
        matched3, winning3, sample3 = _try_selectors(row, views_selectors)
        report.results.append(SelectorResult("monthly_views", winning3 or views_selectors[0], matched3, sample3))
        _print_result("월간 조회수", matched3, winning3, sample3)

        # 5. 구독자 수
        subs_selectors = [".subscriber_count", ".subscribers", "[class*='subscriberCount']", "td:nth-child(3)"]
        matched4, winning4, sample4 = _try_selectors(row, subs_selectors)
        report.results.append(SelectorResult("subscribers", winning4 or subs_selectors[0], matched4, sample4))
        _print_result("구독자 수", matched4, winning4, sample4)
    else:
        for name in ["channel_link", "channel_name", "monthly_views", "subscribers"]:
            report.results.append(SelectorResult(name, "", False, "", "row 미매칭으로 건너뜀"))

    # 6. 다음 페이지 버튼
    next_selectors = [".pagination_next:not(.disabled)", "a[rel='next']", ".btn_next:not(.disabled)"]
    matched5, winning5, _ = _try_selectors(page, next_selectors)
    report.results.append(SelectorResult("next_page", winning5 or next_selectors[0], matched5))
    _print_result("다음 페이지", matched5, winning5, "")

    # 7. URL 패턴 (카테고리 ID 검증)
    current_url = page.url
    url_ok = "24" in current_url or "chart" in current_url
    report.results.append(SelectorResult("url_pattern", current_url, url_ok, current_url))
    _print_result("URL 패턴 (카테고리 24)", url_ok, current_url, "")

    return report


def verify_naver_clip(page: Page) -> SiteReport:
    report = SiteReport(site="네이버 클립 (B-2)", url=NAVER_CLIP_URL)
    print(f"\n{'='*60}")
    print(f"[네이버 클립] {NAVER_CLIP_URL}")
    print(f"{'='*60}")

    try:
        page.goto(NAVER_CLIP_URL, wait_until="networkidle", timeout=30_000)
    except Exception as e:
        print(f"  페이지 로드 실패: {e}")
        return report

    # 1. 전체 조회수
    total_views_selectors = ["._total_view_count", ".hashtag_view_count", "[class*='viewCount']"]
    matched, winning, sample = _try_selectors(page, total_views_selectors)
    report.results.append(SelectorResult("total_views", winning or total_views_selectors[0], matched, sample))
    _print_result("전체 조회수", matched, winning, sample)

    # 2. 클립 수
    clip_count_selectors = ["._clip_count", ".hashtag_clip_count", "[class*='clipCount']"]
    matched2, winning2, sample2 = _try_selectors(page, clip_count_selectors)
    report.results.append(SelectorResult("clip_count", winning2 or clip_count_selectors[0], matched2, sample2))
    _print_result("클립 수", matched2, winning2, sample2)

    # 3. 주간 조회수 (선택)
    weekly_selectors = ["._weekly_view", "[class*='weeklyView']"]
    matched3, winning3, sample3 = _try_selectors(page, weekly_selectors)
    report.results.append(SelectorResult("weekly_views", winning3 or weekly_selectors[0], matched3, sample3,
                                          "optional" if not matched3 else ""))
    _print_result("주간 조회수 (optional)", matched3, winning3, sample3)

    # 4. 페이지 자체 로드 확인 (해시태그 타이틀)
    title_selectors = ["h1", ".hashtag_title", "[class*='hashtagTitle']", ".tag_name"]
    matched4, winning4, sample4 = _try_selectors(page, title_selectors)
    report.results.append(SelectorResult("page_title", winning4 or title_selectors[0], matched4, sample4))
    _print_result("페이지 타이틀", matched4, winning4, sample4)

    # 5. DOM에서 실제 클래스명 힌트 추출 (통계 관련 요소 후보)
    try:
        hints = page.evaluate("""() => {
            const stats = [];
            document.querySelectorAll('[class]').forEach(el => {
                const cls = el.className;
                if (typeof cls === 'string' && (cls.includes('view') || cls.includes('count') || cls.includes('stat'))) {
                    const text = el.innerText?.trim().slice(0, 40);
                    if (text) stats.push({cls: cls.slice(0, 60), text});
                }
            });
            return stats.slice(0, 10);
        }""")
        if hints:
            print("\n  [DOM 힌트] 통계 관련 실제 클래스명:")
            for h in hints:
                print(f"    class='{h['cls']}' → '{h['text']}'")
    except Exception:
        pass

    return report


def _print_result(label: str, matched: bool, selector: str, sample: str) -> None:
    icon = "[OK]" if matched else "[NO]"
    sel_short = selector[:50] if selector else "-"
    sample_short = f" => '{sample}'" if sample else ""
    print(f"  {icon} {label:<20} [{sel_short}]{sample_short}")


# ── 메인 ────────────────────────────────────────────────────────

def main():
    print("셀렉터 실사이트 검증 시작...")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        reports: list[SiteReport] = []
        reports.append(verify_playboard(page))
        reports.append(verify_naver_clip(page))

        browser.close()

    # ── 최종 리포트 ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("최종 정확도 리포트")
    print(f"{'='*60}")

    for r in reports:
        score_pct      = r.score * 100
        critical_pct   = r.critical_score * 100
        matched_count  = sum(1 for x in r.results if x.matched)
        total_count    = len(r.results)

        status = "[PASS] 정상" if critical_pct >= 80 else ("[WARN] 부분 동작" if critical_pct >= 50 else "[FAIL] 에이전트 도입 필요")

        print(f"\n  {r.site}")
        print(f"    전체 정확도   : {matched_count}/{total_count} ({score_pct:.0f}%)")
        print(f"    핵심 정확도   : {critical_pct:.0f}%")
        print(f"    판정          : {status}")
        if critical_pct < 80:
            print(f"    → CSS 셀렉터 수동 교정 또는 JS evaluate() 기반 에이전트 전환 권장")

    # JSON 저장
    output = []
    for r in reports:
        output.append({
            "site": r.site,
            "url": r.url,
            "overall_accuracy": round(r.score, 3),
            "critical_accuracy": round(r.critical_score, 3),
            "selectors": [
                {"name": x.name, "selector": x.selector, "matched": x.matched,
                 "sample": x.sample_text, "note": x.note}
                for x in r.results
            ],
        })
    out_path = "scripts/selector_verification_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
