"""meviy に加工品をアップロードして見積りを読み取る。

    python quote/meviy/meviy_quote.py folder <フォルダ名>          フォルダを作る（無ければ）
    python quote/meviy/meviy_quote.py upload <フォルダ名> <dir>     フォルダに入り、dir の中の 3D ファイルをアップロードする
    python quote/meviy/meviy_quote.py read <フォルダ名>             フォルダの一覧（型番・加工方法・材質・単価・出荷日）を読み取って CSV にする

ログインは meviy_browser.py で人が済ませておく。注文に関わる操作はしない。
meviy 側では必ずフォルダを作ってから入れる（マイページの直下に置かない）。
"""
from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from meviy_browser import HERE, MYPAGE, dump, logged_in, open_browser

RESULT = HERE / "result"


def start(p):
    ctx, page = open_browser(p)
    page.goto(MYPAGE, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    if not logged_in(page):
        ctx.close()
        raise SystemExit("ログインが切れている。meviy_browser.py を実行してログインし直す")
    return ctx, page


def folder_link(page, name):
    """左のフォルダ一覧にある name の行。"""
    return page.locator("[class*=folderBox], [class*=folderList], [class*=sideMenu], nav, aside").get_by_text(name, exact=True)


def ensure_folder(page, name):
    if page.get_by_text(name, exact=True).count() > 0:
        print("フォルダは既にある:", name)
        return False
    page.get_by_role("button", name="フォルダ新規作成").click()
    page.wait_for_timeout(1000)
    page.locator("input[class*=projectsDialog]").fill(name)
    page.get_by_role("button", name="作成", exact=True).click()
    page.wait_for_timeout(3000)
    print("フォルダを作成:", name, "→", "OK" if page.get_by_text(name, exact=True).count() > 0 else "一覧に見当たらない")
    return True


def enter_folder(page, name):
    page.get_by_text(name, exact=True).first.click()
    page.wait_for_timeout(4000)


def main():
    cmd, name = sys.argv[1], sys.argv[2]
    with sync_playwright() as p:
        ctx, page = start(p)
        try:
            ensure_folder(page, name)
            dump(page, "10_after_folder")
            if cmd == "folder":
                return
            enter_folder(page, name)
            dump(page, "11_in_folder")
            if cmd == "upload":
                files = sorted(str(f) for f in Path(sys.argv[3]).iterdir() if f.suffix.lower() == ".sldprt")
                if not files:
                    raise SystemExit("アップロードする SLDPRT が無い")
                page.get_by_role("button", name="アップロード").first.click()
                page.wait_for_timeout(1000)
                with page.expect_file_chooser() as fc:
                    page.get_by_text("ファイルをアップロード", exact=True).click()
                fc.value.set_files(files)
                print("アップロード開始", len(files), "件")
                for i in range(40):                      # 解析が終わるまで待つ（最長 約 7 分）
                    page.wait_for_timeout(10000)
                    n = page.locator("input[type=checkbox]").count()
                    busy = page.get_by_text("解析中").count() + page.get_by_text("アップロード中").count()
                    print(f"  {10 * (i + 1)} 秒: 行 {max(n - 1, 0)}、処理中 {busy}")
                    if n - 1 >= len(files) and busy == 0:
                        break
                dump(page, "13_after_upload")
            elif cmd == "read":
                rows = page.evaluate("""() => [...document.querySelectorAll('[class*=row], tr')].map(r => r.innerText.replace(/\\s+/g, ' ').trim()).filter(t => t.length > 10)""")
                RESULT.mkdir(exist_ok=True)
                out = RESULT / f"{datetime.date.today():%Y%m%d}_{name}_raw.csv"
                with open(out, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    for r in rows:
                        w.writerow([r])
                print(out, len(rows), "行")
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
