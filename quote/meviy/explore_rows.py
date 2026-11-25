"""フォルダの一覧で、各部品の行の文字とリンク・操作できる要素を記録する（開発用）。何も変更しない。

    python quote/meviy/explore_rows.py <フォルダ名> [部品名 ...]
"""
import sys

from playwright.sync_api import sync_playwright

from meviy_browser import dump
from meviy_quote import enter_folder, start

folder, only = sys.argv[1], sys.argv[2:]
with sync_playwright() as p:
    ctx, page = start(p)
    try:
        page.goto("https://meviy.misumi-ec.com/ja-jp/app/fa/mypage", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        enter_folder(page, folder)
        page.wait_for_timeout(5000)
        rows = page.locator("[class*=projectsListViewBodyRow]")
        for i in range(rows.count()):
            row = rows.nth(i)
            text = " | ".join(x.strip() for x in row.inner_text().splitlines() if x.strip())
            if only and not any(o in text for o in only):
                continue
            print(text)
            if only:
                row.scroll_into_view_if_needed()
                print("   リンク:", row.locator("a").evaluate_all("es => es.map(e => (e.getAttribute('href') || '') + ' [' + e.innerText.trim() + ']')"))
                print("   ボタン:", row.locator("button").evaluate_all("es => es.map(e => e.innerText.trim() + (e.disabled ? '(無効)' : ''))"))
                print("   選択:", row.locator("[class*=select__control]").evaluate_all("es => es.map(e => e.className.includes('disabled') ? e.innerText.trim() + '(無効)' : e.innerText.trim())"))
        dump(page, "40_rows")
    finally:
        ctx.close()
