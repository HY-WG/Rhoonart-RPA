"""실사이트 DOM 구조 덤프 — 실제 클래스명 확인용."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

SITES = {
    "playboard": "https://playboard.co/ko/chart/KR/24/shorts/monthly",
    "naver_clip": "https://clip.naver.com/hashtag/재벌집막내아들",
}

def dump(page, label):
    print(f"\n{'='*60}")
    print(f"[{label}] 주요 클래스/태그 덤프")
    print(f"{'='*60}")

    # 1. 리스트/행 후보 요소 (li, tr, article, div with class containing item/row/card/channel)
    rows = page.evaluate("""() => {
        const tags = ['li', 'tr', 'article'];
        const results = [];
        tags.forEach(tag => {
            document.querySelectorAll(tag).forEach(el => {
                const cls = (el.className || '').toString().trim().slice(0, 80);
                const text = (el.innerText || '').trim().slice(0, 60).replace(/\\n/g, ' ');
                if (cls && text) results.push({tag, cls, text});
            });
        });
        // div/span with item/row/card/channel in class
        document.querySelectorAll('[class]').forEach(el => {
            const cls = (el.className || '').toString();
            if (/item|row|card|channel|rank|chart/i.test(cls)) {
                const text = (el.innerText || '').trim().slice(0, 60).replace(/\\n/g, ' ');
                if (text) results.push({tag: el.tagName, cls: cls.slice(0, 80), text});
            }
        });
        // 중복 제거 (cls 기준)
        const seen = new Set();
        return results.filter(r => {
            if (seen.has(r.cls)) return false;
            seen.add(r.cls);
            return true;
        }).slice(0, 20);
    }""")
    print("\n[행/카드 후보]")
    for r in rows:
        print(f"  <{r['tag']} class='{r['cls']}'> => {r['text']}")

    # 2. 숫자 포함 요소 (조회수/구독자 후보)
    nums = page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('[class]').forEach(el => {
            const text = (el.innerText || '').trim();
            if (/^[\\d,.]+[만억MK]?$/.test(text) || /[\\d,]+\\s*(만|억|회|명)/.test(text)) {
                const cls = (el.className || '').toString().trim().slice(0, 80);
                if (cls) results.push({tag: el.tagName, cls, text: text.slice(0, 40)});
            }
        });
        const seen = new Set();
        return results.filter(r => {
            if (seen.has(r.cls)) return false;
            seen.add(r.cls);
            return true;
        }).slice(0, 15);
    }""")
    print("\n[숫자 포함 요소 (조회수/구독자 후보)]")
    for n in nums:
        print(f"  <{n['tag']} class='{n['cls']}'> => {n['text']}")

    # 3. 링크 후보
    links = page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('a[href]').forEach(el => {
            const href = el.href || '';
            const cls = (el.className || '').toString().trim().slice(0, 60);
            const text = (el.innerText || '').trim().slice(0, 40);
            if ((href.includes('channel') || href.includes('chart') || href.includes('hashtag')) && text)
                results.push({href: href.slice(0, 80), cls, text});
        });
        return results.slice(0, 10);
    }""")
    print("\n[채널/링크 후보]")
    for l in links:
        print(f"  <a href='{l['href']}'> class='{l['cls']}' => {l['text']}")


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = ctx.new_page()

    for label, url in SITES.items():
        print(f"\n로딩: {url}")
        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
            page.wait_for_timeout(2000)  # JS 렌더링 추가 대기
        except Exception as e:
            print(f"  로드 실패: {e}")
            continue
        dump(page, label)

    browser.close()
print("\n덤프 완료.")
