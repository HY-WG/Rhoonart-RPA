"""브라우저 기반 최종 API 탐색.

Playboard : 브라우저 로그인 → lapi.playboard.co 응답 전체 캡처
네이버 클립: graphql 응답 전체 캡처 (요청 body 포함)
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass

EMAIL    = os.environ.get("PLAYBOARD_EMAIL", "")
PASSWORD = os.environ.get("PLAYBOARD_PASSWORD", "")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

results = {"playboard": [], "naver_clip": []}


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)

        # ── Playboard ────────────────────────────────────────
        print("\n" + "="*60)
        print("[Playboard] 브라우저 로그인 + lapi 응답 캡처")
        print("="*60)

        pb = ctx.new_page()

        def on_pb_response(resp):
            if "lapi.playboard.co" not in resp.url:
                return
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                body = resp.json()
            except Exception:
                return
            body_str = json.dumps(body, ensure_ascii=False)
            results["playboard"].append({"url": resp.url, "status": resp.status, "body": body_str[:1000]})
            has_list = "channelId" in body_str or ('"list"' in body_str and '"total"' in body_str)
            mark = "[CHART?]" if has_list else "       "
            print(f"  {mark} [{resp.status}] {resp.url}")
            print(f"           {body_str[:200]}")

        pb.on("response", on_pb_response)

        # 로그인
        pb.goto("https://playboard.co/account/signin", wait_until="networkidle", timeout=30_000)
        pb.wait_for_timeout(1000)
        # email input은 type='text', name='email' (type='email' 아님)
        pb.fill("input[name='email']", EMAIL)
        pb.fill("input[name='password']", PASSWORD)
        pb.click("button[type='submit']")
        pb.wait_for_load_state("networkidle", timeout=20_000)
        print(f"  로그인 URL: {pb.url}")

        # 차트 페이지
        pb.goto("https://playboard.co/ko/chart/KR/24/shorts/monthly",
                wait_until="networkidle", timeout=30_000)
        pb.wait_for_timeout(3000)
        # 스크롤로 추가 API 요청 유발
        pb.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        pb.wait_for_timeout(2000)
        pb.close()

        # ── 네이버 클립 ───────────────────────────────────────
        print("\n" + "="*60)
        print("[네이버 클립] GraphQL 캡처")
        print("="*60)

        nc = ctx.new_page()
        req_store: dict[str, str] = {}  # frame_id+url → post_data

        def on_nc_request(req):
            if "graphql" in req.url:
                key = req.url
                try:
                    req_store[key] = req.post_data or ""
                except Exception:
                    req_store[key] = ""

        def on_nc_response(resp):
            if "graphql" not in resp.url:
                return
            try:
                body = resp.json()
            except Exception:
                return
            body_str = json.dumps(body, ensure_ascii=False)
            req_body = req_store.get(resp.url, "(no request body)")
            results["naver_clip"].append({
                "url": resp.url,
                "request_body": req_body[:600],
                "response_body": body_str[:800],
            })
            print(f"\n  [{resp.status}] {resp.url}")
            print(f"  REQ: {req_body[:300]}")
            print(f"  RES: {body_str[:300]}")

        nc.on("request", on_nc_request)
        nc.on("response", on_nc_response)

        nc.goto("https://clip.naver.com/hashtag/재벌집막내아들",
                wait_until="networkidle", timeout=30_000)
        nc.wait_for_timeout(3000)
        nc.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        nc.wait_for_timeout(2000)
        nc.close()

        browser.close()

    # 저장
    out = "scripts/api_browser_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out}")
    print(f"  Playboard 응답: {len(results['playboard'])}개")
    print(f"  네이버 클립 GraphQL: {len(results['naver_clip'])}개")
    print("탐색 완료.")


if __name__ == "__main__":
    run()
