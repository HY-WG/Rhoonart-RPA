"""심층 API 탐색 — 차트 데이터 및 GraphQL 응답 전체 캡처."""
import sys, io, json, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright, Response, Request

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

PLAYBOARD_EMAIL    = os.environ.get("PLAYBOARD_EMAIL", "")
PLAYBOARD_PASSWORD = os.environ.get("PLAYBOARD_PASSWORD", "")

PLAYBOARD_CHART_URL = "https://playboard.co/ko/chart/KR/24/shorts/monthly"
NAVER_CLIP_URL      = "https://clip.naver.com/hashtag/재벌집막내아들"

# ── Playboard ─────────────────────────────────────────────────

def discover_playboard(ctx):
    print("\n" + "="*60)
    print("[Playboard] Bearer 토큰 취득 후 차트 API 직접 호출")
    print("="*60)

    page = ctx.new_page()
    all_requests: list[dict] = []

    def on_req(req: Request):
        if "lapi.playboard.co" in req.url or "api.playboard.co" in req.url:
            all_requests.append({"method": req.method, "url": req.url,
                                  "headers": dict(req.headers)})

    def on_resp(resp: Response):
        url = resp.url
        ct  = resp.headers.get("content-type", "")
        if "json" not in ct:
            return
        if any(x in url for x in ["chunk", "webpack", "manifest"]):
            return
        try:
            body = resp.json()
        except Exception:
            return
        # 차트/랭킹 관련 응답만 상세 출력
        body_str = json.dumps(body, ensure_ascii=False)
        if any(k in body_str for k in ["channelId", "channelTitle", "shorts", "rank", "list"]):
            print(f"\n  [CHART API] {resp.status} {url}")
            print(f"  {body_str[:500]}")

    page.on("request", on_req)
    page.on("response", on_resp)

    # 로그인
    print("  로그인...")
    page.goto("https://playboard.co/account/signin", wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(500)
    page.fill("input[type='email']", PLAYBOARD_EMAIL, timeout=5_000)
    page.fill("input[type='password']", PLAYBOARD_PASSWORD, timeout=5_000)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle", timeout=15_000)
    print(f"  로그인 후 URL: {page.url}")

    # 차트 페이지
    print(f"  차트 페이지 이동...")
    page.goto(PLAYBOARD_CHART_URL, wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(3000)

    # 스크롤 → 더 많은 API 요청 유발
    for _ in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

    print(f"\n  lapi.playboard.co 요청 목록 ({len(all_requests)}개):")
    for r in all_requests:
        auth = r["headers"].get("authorization", "")[:30]
        print(f"    [{r['method']}] {r['url']}")
        if auth:
            print(f"           Authorization: {auth}...")

    page.close()


# ── 네이버 클립 ────────────────────────────────────────────────

def discover_naver_clip(ctx):
    print("\n" + "="*60)
    print("[네이버 클립] GraphQL 요청/응답 상세 캡처")
    print("="*60)

    page = ctx.new_page()
    graphql_calls: list[dict] = []

    def on_req(req: Request):
        if "graphql" in req.url:
            try:
                post_data = req.post_data or ""
                graphql_calls.append({"url": req.url, "body": post_data[:400]})
            except Exception:
                pass

    def on_resp(resp: Response):
        if "graphql" not in resp.url:
            return
        try:
            body = resp.json()
        except Exception:
            return
        body_str = json.dumps(body, ensure_ascii=False)
        # 조회수/통계 포함 여부
        has_stats = any(k in body_str for k in ["viewCount", "view_count", "clipCount",
                                                  "playCount", "likeCount", "totalCount"])
        print(f"\n  [GraphQL] {resp.status} {resp.url}")
        print(f"  통계 포함: {'YES' if has_stats else 'NO'}")
        print(f"  응답 전체:\n{body_str[:800]}")

    page.on("request", on_req)
    page.on("response", on_resp)

    print(f"  페이지 이동: {NAVER_CLIP_URL}")
    page.goto(NAVER_CLIP_URL, wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(3000)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)

    print(f"\n  GraphQL 요청 바디 ({len(graphql_calls)}개):")
    for c in graphql_calls:
        print(f"\n  URL: {c['url']}")
        print(f"  Body: {c['body']}")

    page.close()


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        discover_playboard(ctx)
        discover_naver_clip(ctx)
        browser.close()
    print("\n심층 탐색 완료.")


if __name__ == "__main__":
    main()
