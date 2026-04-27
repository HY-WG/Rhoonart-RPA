"""Playboard 로그인 페이지 HTML 덤프 + 스크린샷."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent=UA)
    page = ctx.new_page()

    page.goto("https://playboard.co/account/signin", wait_until="networkidle", timeout=30_000)
    page.wait_for_timeout(2000)

    # 현재 URL
    print(f"URL: {page.url}")

    # 모든 input 요소 출력
    inputs = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input, button, [type]')).map(el => ({
            tag: el.tagName,
            type: el.type || '',
            name: el.name || '',
            id: el.id || '',
            placeholder: el.placeholder || '',
            cls: (el.className || '').toString().slice(0, 60),
            visible: el.offsetParent !== null,
        }));
    }""")
    print(f"\n입력 요소 ({len(inputs)}개):")
    for el in inputs:
        print(f"  <{el['tag']} type='{el['type']}' name='{el['name']}' id='{el['id']}' "
              f"placeholder='{el['placeholder']}' visible={el['visible']} class='{el['cls']}'>")

    # 스크린샷
    page.screenshot(path="scripts/debug_signin.png")
    print("\n스크린샷 저장: scripts/debug_signin.png")

    # body HTML 일부
    html = page.content()
    print(f"\nHTML 길이: {len(html)}")
    # form 태그 주변만 추출
    import re
    forms = re.findall(r'<form[^>]*>.*?</form>', html, re.DOTALL)
    for f in forms[:2]:
        print(f"\nFORM: {f[:500]}")

    browser.close()
