"""meviy の利用規約を開き、本文を explore/terms.txt に保存する（自動操作に関する条項の確認用）。"""
from __future__ import annotations

from playwright.sync_api import sync_playwright

from meviy_browser import EXPLORE, MYPAGE, open_browser

with sync_playwright() as p:
    ctx, page = open_browser(p)
    page.goto(MYPAGE, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    href = page.get_by_role("link", name="利用規約").first.get_attribute("href")
    print("規約:", href)
    page.goto(href if href.startswith("http") else "https://meviy.misumi-ec.com" + href, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    text = page.inner_text("body")
    EXPLORE.mkdir(exist_ok=True)
    (EXPLORE / "terms.txt").write_text(page.url + "\n\n" + text, encoding="utf-8")
    print(page.url, len(text), "文字")
    ctx.close()
