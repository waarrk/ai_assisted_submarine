"""実ブラウザでリンクを開いてファイルを保存する（メーカー配布の 3D データ・図面用）。

    python quote/web_download.py <保存先フォルダ> <URL> [<URL> ...]
利用条件の同意画面が出たら、画面の内容を表示して止まる（自動では同意しない）。
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = Path(__file__).resolve().parent / "meviy" / ".profile"
dst = Path(sys.argv[1]); dst.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False, locale="ja-JP", accept_downloads=True)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    for url in sys.argv[2:]:
        try:
            with page.expect_download(timeout=30000) as info:
                try:
                    page.goto(url, timeout=30000)
                except Exception:
                    pass                      # ダウンロードが始まると遷移は中断される
            d = info.value
            out = dst / d.suggested_filename
            d.save_as(str(out))
            print("保存", out.name, out.stat().st_size)
        except Exception as e:
            print("ダウンロードが始まらない:", type(e).__name__)
            print("  URL:", page.url)
            print("  画面:", page.inner_text("body")[:600].replace("\n", " / "))
    ctx.close()
