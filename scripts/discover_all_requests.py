"""전체 네트워크 요청 캡처 — 도메인 무관, 모든 JSON 응답 수집."""
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

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)

        # ── 1. Playboard: 모든 JSON 요청 캡처 ────────────────
        print("\n" + "="*60)
        print("[Playboard] 차트 페이지 전체 요청 캡처")
        print("="*60)

        pb = ctx.new_page()
        pb_all = []

        def on_pb(resp):
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            skip = ["chunk", "webpack", "manifest", "font", "analytics", "tracking",
                    "gtm", "google-analytics", "sentry", "logrocket"]
            if any(s in resp.url for s in skip):
                return
            try:
                body = resp.json()
                body_str = json.dumps(body, ensure_ascii=False)
                pb_all.append({"url": resp.url, "status": resp.status, "body": body_str[:1200]})
            except Exception:
                pass

        pb.on("response", on_pb)

        # 로그인
        pb.goto("https://playboard.co/account/signin", wait_until="networkidle", timeout=30_000)
        pb.wait_for_timeout(1000)
        pb.fill("input[name='email']", EMAIL)
        pb.fill("input[name='password']", PASSWORD)
        pb.click("button[type='submit']")
        pb.wait_for_load_state("networkidle", timeout=20_000)
        print(f"  로그인 URL: {pb.url}")

        # 차트 페이지 (로그인 후 캡처 초기화)
        pb_all.clear()
        pb.goto("https://playboard.co/ko/chart/KR/24/shorts/monthly",
                wait_until="domcontentloaded", timeout=30_000)
        pb.wait_for_timeout(5000)
        pb.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        pb.wait_for_timeout(3000)

        print(f"\n  차트 페이지 JSON 응답 ({len(pb_all)}개):")
        for r in pb_all:
            print(f"\n  [{r['status']}] {r['url']}")
            print(f"  {r['body'][:300]}")

        # HTML SSR 확인
        html = pb.content()
        print(f"\n  HTML 길이: {len(html)}")
        # 채널 ID 패턴 찾기 (UC로 시작하는 YouTube 채널 ID)
        import re
        uc_ids = list(set(re.findall(r'UC[\w-]{22}', html)))[:5]
        if uc_ids:
            print(f"  HTML 내 YouTube 채널 ID 발견: {uc_ids}")
        else:
            print("  HTML 내 YouTube 채널 ID 없음")

        pb.close()

        # ── 2. 네이버 클립: 모든 GraphQL operation 캡처 ──────
        print("\n" + "="*60)
        print("[네이버 클립] 모든 GraphQL operation 캡처")
        print("="*60)

        nc = ctx.new_page()
        nc_ops = {}  # operationName → {request, response}

        def on_nc_req(req):
            if "graphql" not in req.url:
                return
            try:
                body = json.loads(req.post_data or "{}")
                op = body.get("operationName", "unknown")
                nc_ops[op] = {"request": body, "response": None}
            except Exception:
                pass

        def on_nc_resp(resp):
            if "graphql" not in resp.url:
                return
            try:
                body = resp.json()
                # operationName을 response에서 역추적
                req_data = None
                try:
                    req_data = json.loads(resp.request.post_data or "{}")
                except Exception:
                    pass
                op = req_data.get("operationName", "unknown") if req_data else "unknown"
                nc_ops[op] = {
                    "request": req_data,
                    "response": json.dumps(body, ensure_ascii=False)[:1200],
                }
            except Exception:
                pass

        nc.on("request", on_nc_req)
        nc.on("response", on_nc_resp)

        nc.goto("https://clip.naver.com/hashtag/재벌집막내아들",
                wait_until="domcontentloaded", timeout=30_000)
        nc.wait_for_timeout(4000)
        nc.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        nc.wait_for_timeout(3000)

        print(f"\n  GraphQL 조작 ({len(nc_ops)}개):")
        for op_name, data in nc_ops.items():
            print(f"\n  [{op_name}]")
            if data.get("request"):
                vars_preview = json.dumps(
                    data["request"].get("variables", {}), ensure_ascii=False)[:150]
                print(f"  variables: {vars_preview}")
            if data.get("response"):
                print(f"  response:  {data['response'][:300]}")

        nc.close()
        browser.close()

    # 저장
    out = "scripts/all_requests_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"playboard": pb_all, "naver_clip_ops": nc_ops}, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out}")
    print("탐색 완료.")

if __name__ == "__main__":
    run()
