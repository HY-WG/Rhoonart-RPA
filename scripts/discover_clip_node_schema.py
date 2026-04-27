"""ContentsQuery 노드 스키마 완전 탐색.

목표:
  1. ContentQuery response 전체 저장 (잘림 없음)
  2. 각 클립 노드(node)의 모든 필드 키 목록 출력
  3. viewCount / likeCount / playCount 등 집계 필드 존재 여부 확인
  4. 클립 상세 페이지 URL 패턴 확인 후 접근 시도 → 추가 operation 탐색
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

TAG = "재벌집막내아들"

def flatten_keys(obj, prefix=""):
    """JSON 객체의 모든 키 경로를 평탄화"""
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            keys.append(full)
            keys.extend(flatten_keys(v, full))
    elif isinstance(obj, list) and obj:
        keys.extend(flatten_keys(obj[0], f"{prefix}[0]"))
    return keys

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        nc = ctx.new_page()

        captured_responses: list[dict] = []   # 모든 graphql 응답 전체 저장
        all_ops: dict[str, int] = {}           # operation 종류 카운트

        def on_resp(resp):
            if "graphql" not in resp.url:
                return
            try:
                body = resp.json()
                try:
                    req_data = json.loads(resp.request.post_data or "{}")
                    op = req_data.get("operationName", "unknown")
                    variables = req_data.get("variables", {})
                    query = req_data.get("query", "")
                except Exception:
                    op, variables, query = "unknown", {}, ""

                all_ops[op] = all_ops.get(op, 0) + 1
                captured_responses.append({
                    "op": op,
                    "variables": variables,
                    "query": query,
                    "body": body,   # 전체 저장 (잘림 없음)
                })
            except Exception:
                pass

        nc.on("response", on_resp)

        # ── 1. 해시태그 페이지 진입 ──────────────────────────
        print(f"[1] https://clip.naver.com/hashtag/{TAG} 진입")
        nc.goto(f"https://clip.naver.com/hashtag/{TAG}",
                wait_until="domcontentloaded", timeout=30_000)
        nc.wait_for_timeout(5000)

        # ── 2. 스크롤 2회 ───────────────────────────────────
        for i in range(2):
            nc.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            nc.wait_for_timeout(2500)

        # ── 3. 클립 링크 패턴 확인 ──────────────────────────
        all_hrefs = nc.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(h => h.includes('clip.naver'))
                .slice(0, 30);
        }""")
        print(f"\n[클립 관련 href ({len(all_hrefs)}개)]")
        for h in all_hrefs:
            print(f"  {h}")

        # ── 4. 클립 상세 페이지 접근 시도 ────────────────────
        clip_detail_url = None
        for href in all_hrefs:
            # /channel/, /video/ 또는 /c/ 패턴 탐색
            if re.search(r'/(?:channel|video|c|clip)/[\w\-]+', href):
                clip_detail_url = href
                break

        if clip_detail_url:
            print(f"\n[2] 클립 상세 접근: {clip_detail_url}")
            nc.goto(clip_detail_url, wait_until="domcontentloaded", timeout=20_000)
            nc.wait_for_timeout(4000)
        else:
            print("\n[2] 클립 상세 URL 패턴 미발견 — 건너뜀")

        nc.close()
        browser.close()

    # ── 결과 분석 ──────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print(f"[전체 GraphQL operations ({sum(all_ops.values())}건)]")
    for op, cnt in all_ops.items():
        print(f"  {op}: {cnt}회")

    # ContentsQuery 첫 번째 응답 전체 구조 분석
    contents_resp = next((r for r in captured_responses if r["op"] == "ContentsQuery"), None)
    if contents_resp:
        body = contents_resp["body"]
        print(f"\n{'='*60}")
        print("[ContentsQuery 응답 키 구조 (첫 번째 edge 노드)]")
        try:
            edges = body["data"]["contents"]["edges"]
            if edges:
                node = edges[0]["node"]
                keys = flatten_keys(node)
                print(f"  노드 최상위 키: {list(node.keys())}")
                print(f"\n  전체 키 경로 ({len(keys)}개):")
                for k in sorted(set(keys)):
                    print(f"    {k}")

                # 조회수/좋아요 관련 필드 강조
                stat_keys = [k for k in keys if any(
                    s in k.lower() for s in
                    ["view", "like", "play", "count", "stat", "watch"]
                )]
                print(f"\n  [통계 관련 키 ({len(stat_keys)}개)]")
                if stat_keys:
                    for k in stat_keys:
                        # 실제 값 출력
                        parts = k.split(".")
                        val = node
                        for p in parts:
                            if p.endswith("[0]"):
                                p = p[:-3]
                                val = val.get(p, [{}])[0] if isinstance(val, dict) else {}
                            else:
                                val = val.get(p, "?") if isinstance(val, dict) else "?"
                        print(f"    {k} = {val}")
                else:
                    print("    (통계 필드 없음)")

                # 전체 첫 번째 노드 raw 출력
                print(f"\n  [첫 번째 노드 전체 raw]")
                print(f"  {json.dumps(node, ensure_ascii=False, indent=2)[:3000]}")
        except Exception as e:
            print(f"  파싱 오류: {e}")
            print(f"  raw body: {json.dumps(body, ensure_ascii=False)[:1000]}")

    # ContentsQuery 최상위 connection 필드도 확인
    if contents_resp:
        print(f"\n{'='*60}")
        print("[ContentsConnection 최상위 필드]")
        try:
            conn = contents_resp["body"]["data"]["contents"]
            print(f"  키: {list(conn.keys())}")
            non_edges = {k: v for k, v in conn.items() if k not in ["edges", "pageInfo"]}
            print(f"  edges/pageInfo 제외 필드: {json.dumps(non_edges, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"  오류: {e}")

    # 결과 JSON 저장
    out = "scripts/clip_node_schema_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "all_ops": all_ops,
            "first_contents_query": {
                "variables": contents_resp["variables"] if contents_resp else None,
                "body": contents_resp["body"] if contents_resp else None,
            }
        }, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out}")

if __name__ == "__main__":
    run()
