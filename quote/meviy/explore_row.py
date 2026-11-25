"""一覧の 1 行（部品）の DOM 構造を調べる（開発用）。"""
import sys
from playwright.sync_api import sync_playwright
from meviy_quote import enter_folder, start

folder, part = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    ctx, page = start(p)
    try:
        enter_folder(page, folder)
        page.wait_for_timeout(3000)
        info = page.evaluate("""(part) => {
            let leaf = null;
            for (const el of document.querySelectorAll('*')) {
                if (el.children.length === 0 && el.textContent.trim() === part) { leaf = el; break; }
            }
            if (!leaf) return 'not found';
            const chain = [];
            let e = leaf, row = null;
            for (let i = 0; i < 12 && e; i++) {
                chain.push(e.tagName + '.' + (e.className || '').toString().slice(0, 45) + ' cb=' + e.querySelectorAll('input[type=checkbox]').length + ' btn=' + e.querySelectorAll('button').length);
                if (!row && e.querySelectorAll('input[type=checkbox]').length === 1 && e.querySelectorAll('button').length >= 1) row = e;
                e = e.parentElement;
            }
            const out = {chain};
            if (row) {
                out.rowClass = row.className;
                out.html = row.outerHTML.replace(/\s+/g, ' ').slice(0, 3500);
            }
            return out;
        }""", part)
        if isinstance(info, dict):
            print("\n".join(info["chain"]))
            print("ROW", info.get("rowClass"))
            print(info.get("html"))
        else:
            print(info)
    finally:
        ctx.close()
