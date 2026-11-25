"""ビューアで「材質・表面処理を変更」を開き、材質の区分ごとに選べる材質と表面処理を記録する（開発用）。確定はしない。

    python quote/meviy/explore_viewer2.py <フォルダ名> <部品名.SLDPRT>
"""
import sys

from playwright.sync_api import sync_playwright

from meviy_quote import enter_folder, start

folder, part = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    ctx, page = start(p)
    try:
        enter_folder(page, folder)
        page.wait_for_timeout(3000)
        row = page.locator("[class*=projectsListViewBodyRow]").filter(has_text=part).first
        href = row.locator("a[href*='3dview']").first.get_attribute("href")
        page.goto("https://meviy.misumi-ec.com" + href, wait_until="domcontentloaded")
        page.wait_for_timeout(20000)
        page.get_by_text("材質・表面処理を変更", exact=True).first.click()
        page.wait_for_timeout(3000)
        for tab in ("アルミニウム", "ステンレス", "樹脂"):
            page.get_by_text(tab, exact=True).first.click()
            page.wait_for_timeout(1500)
            t = [x.strip() for x in page.inner_text("body").splitlines() if x.strip()]
            i = t.index("1. 材質を選ぶ")
            j = len(t) - 1 - t[::-1].index("決定する")
            print(f"[{tab}]", " / ".join(t[i + 1:j])[:900])
    finally:
        ctx.close()
