"""実ブラウザでページを開き、リンク先（3D データや図面の配布先を探す用）を一覧する。

    python quote/web_links.py <絞り込みの正規表現> <URL> [<URL> ...]
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = Path(__file__).resolve().parent / "meviy" / ".profile"
pat = re.compile(sys.argv[1], re.I)
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False, locale="ja-JP")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    for url in sys.argv[2:]:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(5000)
            links = page.evaluate("() => [...document.querySelectorAll('a')].map(a => [a.innerText.trim().slice(0, 60), a.href])")
            print("==", page.title()[:70])
            seen = set()
            for text, href in links:
                if href and href not in seen and (pat.search(href) or pat.search(text)):
                    seen.add(href)
                    print(f"  {text!r:<50} {href}")
        except Exception as e:
            print("失敗", url, type(e).__name__, str(e)[:100])
        page.wait_for_timeout(2000)
    ctx.close()
