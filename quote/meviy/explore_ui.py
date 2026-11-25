"""画面構成を調べる（開発用）。引数の段階まで進めて、スクリーンショットと要素一覧を explore/ に残す。

    python quote/meviy/explore_ui.py folder_dialog      フォルダ新規作成のダイアログを開くだけ（作成しない）
    python quote/meviy/explore_ui.py upload_menu <フォルダ名>   フォルダに入り、アップロードのメニューを開くだけ
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

from meviy_browser import MYPAGE, dump, logged_in, open_browser


def main():
    step = sys.argv[1]
    with sync_playwright() as p:
        ctx, page = open_browser(p)
        page.goto(MYPAGE, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        if not logged_in(page):
            raise SystemExit("ログインが切れている。meviy_browser.py を実行してログインし直す")
        if step == "folder_dialog":
            page.get_by_role("button", name="フォルダ新規作成").click()
            page.wait_for_timeout(1500)
            dump(page, "02_folder_dialog")
        elif step == "upload_menu":
            page.locator("a, span, div").filter(has_text=sys.argv[2]).last.click()
            page.wait_for_timeout(4000)
            dump(page, "03_in_folder")
            page.get_by_role("button", name="アップロード").first.click()
            page.wait_for_timeout(1500)
            dump(page, "04_upload_menu")
        print(page.url)
        ctx.close()


if __name__ == "__main__":
    main()
