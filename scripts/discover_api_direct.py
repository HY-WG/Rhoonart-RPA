"""직접 HTTP 호출로 API 엔드포인트 탐색.

Playboard: requests로 Bearer 토큰 취득 → 차트 API 탐색
네이버 클립: Playwright로 GraphQL 요청/응답 전체 캡처
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
from playwright.sync_api import sync_playwright, Response, Request

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

PLAYBOARD_EMAIL    = os.environ.get("PLAYBOARD_EMAIL", "")
PLAYBOARD_PASSWORD = os.environ.get("PLAYBOARD_PASSWORD", "")
NAVER_CLIP_URL     = "https://clip.naver.com/hashtag/재벌집막내아들"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


# ── Playboard: requests 직접 호출 ─────────────────────────────

def discover_playboard_api():
    print("\n" + "="*60)
    print("[Playboard] REST API 직접 탐색")
    print("="*60)

    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Origin": "https://playboard.co",
                             "Referer": "https://playboard.co/"})

    # 1. 로그인 → Bearer 토큰
    print("  로그인 요청...")
    resp = session.post(
        "https://account.playboard.co/v1/signin/email",
        json={"email": PLAYBOARD_EMAIL, "password": PLAYBOARD_PASSWORD},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    print(f"  로그인 상태: {resp.status_code}")
    if resp.status_code != 200:
        print(f"  실패: {resp.text[:200]}")
        return

    token_data = resp.json()
    access_token = token_data.get("access_token", "")
    print(f"  토큰 취득: {access_token[:30]}...")

    auth_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    lapi = "https://lapi.playboard.co"

    # 2. 차트 API 패턴 탐색
    print("\n  차트 API 후보 요청:")
    chart_candidates = [
        f"{lapi}/v1/chart/KR/24/shorts/monthly",
        f"{lapi}/v1/chart?countryCode=KR&category=24&type=shorts&period=monthly&page=1",
        f"{lapi}/v1/chart/KR/24/shorts/monthly?page=1&limit=50",
        f"{lapi}/v1/chart/video?countryCode=KR&categoryId=24&chartType=shorts&period=monthly",
        f"{lapi}/v1/ranking?countryCode=KR&category=24&videoType=shorts&period=monthly",
        f"{lapi}/v1/chart?countryCode=KR&categoryId=24&shortsFilter=true&period=monthly",
        f"{lapi}/v2/chart/KR/24/shorts/monthly",
        f"{lapi}/v1/chart/KR/all/shorts/monthly",
    ]

    found = []
    for url in chart_candidates:
        try:
            r = session.get(url, headers=auth_headers, timeout=10)
            body_str = r.text[:300]
            has_data = any(k in body_str for k in ["channelId", "channelTitle", "list", "items", "rank"])
            status_mark = "[HIT]" if (r.status_code == 200 and has_data) else f"[{r.status_code}]"
            print(f"    {status_mark} {url}")
            if r.status_code == 200:
                print(f"           {body_str}")
                if has_data:
                    found.append({"url": url, "body": r.json()})
        except Exception as e:
            print(f"    [ERR] {url} — {e}")

    if found:
        out = "scripts/playboard_chart_api.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(found, f, ensure_ascii=False, indent=2)
        print(f"\n  차트 API 결과 저장: {out}")
    else:
        print("\n  차트 API 미발견 → 브라우저 네트워크 탭 수동 확인 필요")


# ── 네이버 클립: GraphQL 전체 캡처 ────────────────────────────

def discover_naver_clip_graphql():
    print("\n" + "="*60)
    print("[네이버 클립] GraphQL 요청/응답 전체 캡처")
    print("="*60)

    graphql_pairs: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        page = ctx.new_page()

        req_bodies: dict[str, str] = {}

        def on_req(req: Request):
            if "graphql" in req.url:
                req_bodies[req.url + "|" + (req.post_data or "")[:50]] = req.post_data or ""

        def on_resp(resp: Response):
            if "graphql" not in resp.url:
                return
            try:
                body = resp.json()
            except Exception:
                return
            body_str = json.dumps(body, ensure_ascii=False)
            # 매칭 req_body 찾기
            req_key = next((k for k in req_bodies if k.startswith(resp.url)), None)
            req_body = req_bodies.get(req_key, "") if req_key else ""
            graphql_pairs.append({
                "url": resp.url,
                "request_body": req_body[:600],
                "response_body": body_str[:800],
            })

        page.on("request", on_req)
        page.on("response", on_resp)

        print(f"  로딩: {NAVER_CLIP_URL}")
        page.goto(NAVER_CLIP_URL, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(3000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)

        browser.close()

    print(f"\n  GraphQL 쌍 ({len(graphql_pairs)}개):")
    for i, p in enumerate(graphql_pairs, 1):
        print(f"\n  [{i}] {p['url']}")
        print(f"  REQ: {p['request_body'][:400]}")
        print(f"  RES: {p['response_body'][:400]}")

    if graphql_pairs:
        out = "scripts/naver_clip_graphql.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(graphql_pairs, f, ensure_ascii=False, indent=2)
        print(f"\n  결과 저장: {out}")


if __name__ == "__main__":
    discover_playboard_api()
    discover_naver_clip_graphql()
    print("\n탐색 완료.")
