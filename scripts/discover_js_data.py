"""window 객체 및 SSR 데이터 + 네이버 클립 전체 GraphQL 탐색."""
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

        # ── 1. Playboard: JS 로그인 + SSR 데이터 확인 ─────────
        print("\n" + "="*60)
        print("[Playboard] JS 직접 입력 + __NEXT_DATA__ 확인")
        print("="*60)

        pb = ctx.new_page()
        pb_chart_apis = []

        def on_pb(resp):
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            skip = ["chunk", "webpack", "manifest", "font", "analytics", "gtm", "sentry"]
            if any(s in resp.url for s in skip):
                return
            try:
                body = resp.json()
                body_str = json.dumps(body, ensure_ascii=False)
                pb_chart_apis.append({"url": resp.url, "status": resp.status, "body": body_str[:1500]})
            except Exception:
                pass

        pb.on("response", on_pb)

        # 로그인 — JS evaluate로 직접 입력값 설정 후 submit
        pb.goto("https://playboard.co/account/signin", wait_until="networkidle", timeout=30_000)
        pb.wait_for_timeout(1500)

        # Playwright locator (자동 재시도 포함)
        pb.locator("input[name='email']").fill(EMAIL)
        pb.locator("input[name='password']").fill(PASSWORD)
        pb.locator("button[type='submit']").click()

        # 로그인 완료 대기 — URL이 signin에서 벗어날 때까지
        try:
            pb.wait_for_url(lambda url: "signin" not in url, timeout=15_000)
        except Exception:
            pass
        print(f"  로그인 후 URL: {pb.url}")

        if "signin" in pb.url:
            print("  [WARNING] 로그인 실패 — 차트 페이지 진행 불가")
        else:
            pb_chart_apis.clear()
            pb.goto("https://playboard.co/ko/chart/KR/24/shorts/monthly",
                    wait_until="domcontentloaded", timeout=30_000)
            pb.wait_for_timeout(5000)
            pb.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            pb.wait_for_timeout(3000)

            # __NEXT_DATA__ 확인
            next_data = pb.evaluate("""() => {
                const el = document.getElementById('__NEXT_DATA__');
                return el ? el.textContent.slice(0, 2000) : null;
            }""")
            if next_data:
                print(f"\n  [__NEXT_DATA__] 발견 ({len(next_data)}자):")
                print(f"  {next_data[:600]}")
            else:
                print("\n  __NEXT_DATA__ 없음")

            # window.__nuxt__ / window.__NUXT__ 확인
            nuxt = pb.evaluate("""() => {
                const n = window.__NUXT__ || window.__nuxt__;
                return n ? JSON.stringify(n).slice(0, 1000) : null;
            }""")
            if nuxt:
                print(f"\n  [__NUXT__] 발견: {nuxt[:400]}")

            # Vue/Next 상태 데이터에서 channelId 패턴 탐색
            chan_ids = pb.evaluate("""() => {
                const html = document.documentElement.outerHTML;
                const matches = html.match(/UC[\\w-]{22}/g);
                return matches ? [...new Set(matches)].slice(0, 10) : [];
            }""")
            print(f"\n  채널 ID 발견: {chan_ids}")

            # API 응답 요약
            print(f"\n  차트 페이지 JSON 응답 ({len(pb_chart_apis)}개):")
            for r in pb_chart_apis:
                print(f"\n  [{r['status']}] {r['url']}")
                print(f"  {r['body'][:250]}")

        pb.close()

        # ── 2. 네이버 클립: 해시태그 stats + 모든 GraphQL ops ─
        print("\n" + "="*60)
        print("[네이버 클립] 해시태그 stats + 전체 GraphQL 탐색")
        print("="*60)

        nc = ctx.new_page()
        nc_ops: dict[str, dict] = {}

        def on_nc_resp(resp):
            if "graphql" not in resp.url and "api/hashtag" not in resp.url:
                return
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                body = resp.json()
                body_str = json.dumps(body, ensure_ascii=False)
                try:
                    req_data = json.loads(resp.request.post_data or "{}")
                    op = req_data.get("operationName", "unknown")
                except Exception:
                    op = resp.url.split("?")[0].split("/")[-1]
                nc_ops.setdefault(op, []).append({
                    "url": resp.url,
                    "response": body_str[:800],
                })
            except Exception:
                pass

        nc.on("response", on_nc_resp)

        nc.goto("https://clip.naver.com/hashtag/재벌집막내아들",
                wait_until="domcontentloaded", timeout=30_000)
        pb.wait_for_timeout(500)  # 초기 로드
        nc.wait_for_timeout(4000)

        # 여러 번 스크롤 → 더 많은 API 호출 유발
        for _ in range(3):
            nc.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            nc.wait_for_timeout(2000)

        # window 객체에서 통계 데이터 탐색
        stats_data = nc.evaluate("""() => {
            const keys = Object.keys(window);
            const suspects = keys.filter(k =>
                /nuxt|__NEXT|store|state|apollo|relay|query/i.test(k)
            );
            const result = {};
            suspects.forEach(k => {
                try {
                    const s = JSON.stringify(window[k]);
                    if (s && s.length < 5000) result[k] = s.slice(0, 500);
                } catch(e) {}
            });
            return result;
        }""")
        if stats_data:
            print(f"\n  window 통계 관련 키:")
            for k, v in stats_data.items():
                print(f"  {k}: {v[:200]}")

        print(f"\n  GraphQL operations ({len(nc_ops)}개):")
        for op_name, calls in nc_ops.items():
            print(f"\n  [{op_name}] ({len(calls)}회 호출)")
            for c in calls[:1]:
                print(f"  {c['response'][:400]}")

        nc.close()
        browser.close()

    out = "scripts/js_data_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"playboard_apis": pb_chart_apis, "naver_clip_ops": nc_ops},
                  f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out}")
    print("탐색 완료.")

if __name__ == "__main__":
    run()
