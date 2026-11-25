"""実ブラウザ（専用 Chrome）で Web ページを開き、本文テキストを保存する。部品の仕様・在庫寸法の確認用。

    python quote/web_lookup.py <保存名> <URL> [<保存名> <URL> ...]

販売サイトはプログラムからの直接取得を拒むことが多いので、人が見るのと同じブラウザで開く。
結果は quote/lookup/<保存名>.txt と .png。1 ページずつ間隔を空けて開く。
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "lookup"
PROFILE = HERE / "meviy" / ".profile"


def main():
    args = sys.argv[1:]
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False,
                                                   viewport={"width": 1400, "height": 1000}, locale="ja-JP")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        for name, url in zip(args[0::2], args[1::2]):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(5000)
                text = page.inner_text("body")
                imgs = page.evaluate("() => [...document.images].filter(i => i.naturalWidth > 500).map(i => i.src).slice(0, 40)")
                (OUT / f"{name}.txt").write_text(f"{page.url}\n{page.title()}\n\n{text}\n\n[images]\n" + "\n".join(imgs), encoding="utf-8")
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
                print(f"{name}: {len(text)} 文字  {page.title()[:60]}")
            except Exception as e:
                print(f"{name}: 失敗 {type(e).__name__} {str(e)[:120]}")
            page.wait_for_timeout(2500)
        ctx.close()


if __name__ == "__main__":
    main()
