"""meviy のフォルダの中身を読み取る（一覧の各行の文字と、画面の記録）。

    python quote/meviy/meviy_state.py <フォルダ名> [待つ秒数]
"""
import sys
from playwright.sync_api import sync_playwright
from meviy_browser import dump
from meviy_quote import enter_folder, start

name = sys.argv[1]
wait = int(sys.argv[2]) if len(sys.argv) > 2 else 0
with sync_playwright() as p:
    ctx, page = start(p)
    try:
        enter_folder(page, name)
        page.wait_for_timeout(wait * 1000)
        rows = page.evaluate("""() => {
            const out = [];
            for (const cb of document.querySelectorAll('input[type=checkbox]')) {
                let e = cb;
                for (let i = 0; i < 8 && e; i++) { e = e.parentElement; if (e && e.innerText && e.innerText.includes('.SLDPRT')) break; }
                if (e && e.innerText && e.innerText.includes('.SLDPRT')) {
                    const t = e.innerText.replace(/\s+/g, ' ').trim();
                    if (t.length < 400 && !out.includes(t)) out.push(t);
                }
            }
            return out;
        }""")
        print(len(rows), "行")
        for r in rows:
            print("  ", r[:230])
        dump(page, "14_state")
    finally:
        ctx.close()
