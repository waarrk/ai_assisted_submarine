"""部品の 3D ビューア（見積り画面）を開いて記録する（開発用）。"""
import sys
from playwright.sync_api import sync_playwright
from meviy_browser import dump
from meviy_quote import enter_folder, start

folder, part, tag = sys.argv[1], sys.argv[2], sys.argv[3]
with sync_playwright() as p:
    ctx, page = start(p)
    try:
        enter_folder(page, folder)
        page.wait_for_timeout(3000)
        row = page.locator("[class*=projectsListViewBodyRow]").filter(has_text=part).first
        href = row.locator("a[href*='3dview']").first.get_attribute("href")
        print("href", href)
        page.goto("https://meviy.misumi-ec.com" + href, wait_until="domcontentloaded")
        page.wait_for_timeout(25000)
        n = dump(page, tag)
        body = page.inner_text("body")
        open(f"explore/{tag}_body.txt", "w", encoding="utf-8").write(body)
        print("url", page.url, "要素", n)
        print(" / ".join(t.strip() for t in body.split("\n") if t.strip())[:2500])
    finally:
        ctx.close()
