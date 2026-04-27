"""네트워크 인터셉트로 실제 API 엔드포인트 탐색.

Playboard 로그인 후 차트 페이지, 네이버 클립 해시태그 페이지에서
JSON 응답을 반환하는 모든 요청을 캡처한다.
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright, Response

# 환경변수 또는 직접 입력
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PLAYBOARD_EMAIL    = os.environ.get("PLAYBOARD_EMAIL", "")
PLAYBOARD_PASSWORD = os.environ.get("PLAYBOARD_PASSWORD", "")

PLAYBOARD_CHART_URL = "https://playboard.co/ko/chart/KR/24/shorts/monthly"
NAVER_CLIP_URL      = "https://clip.naver.com/hashtag/재벌집막내아들"

captured: dict[str, list] = {"playboard": [], "naver_clip": []}


def on_response(site: str, response: Response):
    """JSON 응답만 필터링하여 저장."""
    url = response.url
    ct  = response.headers.get("content-type", "")
    if "json" not in ct:
        return
    # 정적 번들 파일 제외
    if any(x in url for x in [".chunk.", "webpack", "manifest", "__webpack"]):
        return
    try:
        body = response.json()
    except Exception:
        return
    captured[site].append({"url": url, "status": response.status, "body_preview": _preview(body)})


def _preview(body) -> str:
    """JSON body 미리보기 (최대 300자)."""
    try:
        s = json.dumps(body, ensure_ascii=False)
        return s[:300] + ("..." if len(s) > 300 else "")
    except Exception:
        return str(body)[:300]


def run_playboard(page):
    print("\n" + "="*60)
    print("[Playboard] 로그인 후 차트 페이지 API 탐색")
    print("="*60)

    page.on("response", lambda r: on_response("playboard", r))

    # 1. 로그인
    print("  로그인 페이지 이동...")
    page.goto("https://playboard.co/account/signin", wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(1000)

    try:
        page.fill("input[type='email'], input[name='email'], #email", PLAYBOARD_EMAIL)
        page.fill("input[type='password'], input[name='password'], #password", PLAYBOARD_PASSWORD)
        page.click("button[type='submit'], .btn-signin, .login-btn, button:has-text('로그인')")
        page.wait_for_load_state("networkidle", timeout=15_000)
        print(f"  현재 URL: {page.url}")
    except Exception as e:
        print(f"  로그인 실패: {e}")
        return

    # 2. 차트 페이지
    print(f"  차트 페이지 이동: {PLAYBOARD_CHART_URL}")
    page.goto(PLAYBOARD_CHART_URL, wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(2000)
    print(f"  현재 URL: {page.url}")

    # 3. 결과 출력
    results = captured["playboard"]
    print(f"\n  캡처된 JSON 응답: {len(results)}개")
    for r in results:
        print(f"\n  [{r['status']}] {r['url']}")
        print(f"  미리보기: {r['body_preview'][:200]}")


def run_naver_clip(page):
    print("\n" + "="*60)
    print("[네이버 클립] 해시태그 페이지 API 탐색")
    print("="*60)

    page.on("response", lambda r: on_response("naver_clip", r))

    print(f"  페이지 이동: {NAVER_CLIP_URL}")
    page.goto(NAVER_CLIP_URL, wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(3000)

    # 스크롤로 추가 로딩 유도
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2000)

    results = captured["naver_clip"]
    print(f"\n  캡처된 JSON 응답: {len(results)}개")
    for r in results:
        print(f"\n  [{r['status']}] {r['url']}")
        print(f"  미리보기: {r['body_preview'][:200]}")


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = ctx.new_page()
        run_playboard(page)

        # 새 페이지로 네이버 클립 탐색 (쿠키 분리)
        page2 = ctx.new_page()
        run_naver_clip(page2)

        browser.close()

    # JSON 저장
    out = "scripts/api_discovery_result.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(captured, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out}")
    print("탐색 완료.")


if __name__ == "__main__":
    main()
