"""네이버 클립 — 해시태그 통계 전용 탐색.

확인 목표:
  1. 해시태그 집계 통계(총 조회수, 클립 수) GraphQL operation 존재 여부
  2. ContentsQuery 응답 구조에서 집계 필드 추출 가능 여부
  3. 클립별 view/like 필드 키 목록 확인
  4. window 객체 Apollo 캐시 탐색
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HASHTAGS = ["재벌집막내아들", "런닝맨"]  # 2개 테스트

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)

        for tag in HASHTAGS:
            print("\n" + "="*60)
            print(f"[네이버 클립] 해시태그: #{tag}")
            print("="*60)

            nc = ctx.new_page()

            # ── 모든 요청/응답 캡처 ─────────────────────────────────
            all_graphql: list[dict] = []       # GraphQL
            all_api: list[dict] = []           # /api/ 경로 기타
            all_json_urls: list[str] = []      # JSON 응답 URL 전체

            def on_req(req):
                if "graphql" in req.url:
                    try:
                        body = json.loads(req.post_data or "{}")
                    except Exception:
                        body = {}
                    all_graphql.append({
                        "op": body.get("operationName", "?"),
                        "vars": body.get("variables", {}),
                        "query_head": (body.get("query") or "")[:200],
                    })

            def on_resp(resp):
                ct = resp.headers.get("content-type", "")
                if "json" not in ct:
                    return
                skip = ["webpack", "manifest", "analytics", "gtm", "sentry"]
                if any(s in resp.url for s in skip):
                    return
                all_json_urls.append(resp.url)

                if "graphql" in resp.url:
                    try:
                        body = resp.json()
                        try:
                            req_data = json.loads(resp.request.post_data or "{}")
                            op = req_data.get("operationName", "?")
                        except Exception:
                            op = "?"
                        # 기존 항목에 response 추가
                        for item in reversed(all_graphql):
                            if item["op"] == op and "response" not in item:
                                item["response"] = json.dumps(body, ensure_ascii=False)[:2000]
                                break
                        else:
                            all_graphql.append({
                                "op": op,
                                "vars": {},
                                "query_head": "",
                                "response": json.dumps(body, ensure_ascii=False)[:2000],
                            })
                    except Exception:
                        pass
                elif "/api/" in resp.url:
                    try:
                        body = resp.json()
                        all_api.append({
                            "url": resp.url,
                            "status": resp.status,
                            "body": json.dumps(body, ensure_ascii=False)[:800],
                        })
                    except Exception:
                        pass

            nc.on("request", on_req)
            nc.on("response", on_resp)

            # 1. 해시태그 메인 페이지
            nc.goto(f"https://clip.naver.com/hashtag/{tag}",
                    wait_until="domcontentloaded", timeout=30_000)
            nc.wait_for_timeout(5000)

            # 2. 스크롤 3회 → 페이지네이션 유발
            for i in range(3):
                nc.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                nc.wait_for_timeout(2500)

            # 3. 클립 카드 클릭 시도 → 상세 페이지 operation 유발
            try:
                card = nc.locator("a[href*='/clip/']").first
                href = card.get_attribute("href")
                if href:
                    clip_url = href if href.startswith("http") else f"https://clip.naver.com{href}"
                    print(f"\n  클립 상세 페이지 접근: {clip_url}")
                    nc.goto(clip_url, wait_until="domcontentloaded", timeout=20_000)
                    nc.wait_for_timeout(4000)
            except Exception as e:
                print(f"\n  클립 카드 클릭 실패: {e}")

            # 4. Apollo 캐시 탐색
            apollo_cache = nc.evaluate("""() => {
                try {
                    // Apollo Client 3/4 캐시 위치 탐색
                    const keys = Object.keys(window);
                    const candidates = keys.filter(k =>
                        /apollo|__APOLLO|relay|store|cache|query/i.test(k)
                    );
                    const result = {};
                    for (const k of candidates) {
                        try {
                            const s = JSON.stringify(window[k]);
                            if (s && s.length > 10 && s.length < 8000) {
                                result[k] = s.slice(0, 600);
                            }
                        } catch(e) {}
                    }
                    return result;
                } catch(e) { return {}; }
            }""")

            # 5. 해시태그 페이지 DOM 통계 텍스트 추출
            nc.goto(f"https://clip.naver.com/hashtag/{tag}",
                    wait_until="domcontentloaded", timeout=30_000)
            nc.wait_for_timeout(3000)

            stat_texts = nc.evaluate("""() => {
                // 숫자+단위 패턴 포함 텍스트 노드 수집
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT
                );
                const results = [];
                let node;
                while ((node = walker.nextNode())) {
                    const t = node.textContent.trim();
                    if (/[0-9]+[만천억]?\\s*(개|회|뷰|조회|클립|영상)/.test(t) && t.length < 60) {
                        results.push(t);
                    }
                }
                return [...new Set(results)].slice(0, 20);
            }""")

            # 페이지 HTML에서 숫자 패턴 직접 탐색
            html = nc.content()
            # 조회수/클립수 관련 JSON 인라인 데이터
            inline_data = re.findall(r'"(?:viewCount|likeCount|clipCount|totalCount|count|views?)":\s*\d+', html)

            # ── 결과 출력 ─────────────────────────────────────────
            print(f"\n[GraphQL operations 전체 ({len(all_graphql)}개)]")
            seen_ops = {}
            for item in all_graphql:
                op = item["op"]
                seen_ops.setdefault(op, 0)
                seen_ops[op] += 1

            for op, cnt in seen_ops.items():
                print(f"\n  ▶ [{op}] {cnt}회")
                for item in all_graphql:
                    if item["op"] == op:
                        print(f"     variables: {json.dumps(item['vars'], ensure_ascii=False)[:150]}")
                        if item.get("query_head"):
                            print(f"     query:     {item['query_head'][:150]}")
                        if item.get("response"):
                            print(f"     response:  {item['response'][:500]}")
                        break  # 첫 번째만 상세 출력

            print(f"\n[비GraphQL /api/ 응답 ({len(all_api)}개)]")
            for a in all_api:
                print(f"\n  [{a['status']}] {a['url']}")
                print(f"  {a['body'][:300]}")

            print(f"\n[JSON 응답 URL 전체 ({len(all_json_urls)}개)]")
            for u in all_json_urls:
                print(f"  {u}")

            print(f"\n[DOM 통계 텍스트 ({len(stat_texts)}개)]")
            for t in stat_texts:
                print(f"  {t}")

            print(f"\n[HTML 인라인 count 필드 ({len(inline_data)}개)]")
            for d in inline_data[:20]:
                print(f"  {d}")

            if apollo_cache:
                print(f"\n[Apollo/Store 캐시 키 ({len(apollo_cache)}개)]")
                for k, v in apollo_cache.items():
                    print(f"  {k}: {v[:200]}")

            nc.close()

        browser.close()

    print("\n\n탐색 완료.")

if __name__ == "__main__":
    run()
