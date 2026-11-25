"""meviy の 1 部品に材質・表面処理を設定し、見積条件を確定して金額と出荷日を読み取る。

    python quote/meviy/meviy_part_quote.py <フォルダ名> <部品名.SLDPRT> <材質の区分> <材質> <表面処理の語> [加工方法]

例: python quote/meviy/meviy_part_quote.py 20261125_UWD-01 後端蓋.SLDPRT アルミニウム A6061 白アルマイト
加工方法（切削 / 板金）は、一覧で「加工方法を選択してください」になっている部品にだけ指定する。
行うのは見積条件の確定まで。カート・注文には進まない。結果は result/<フォルダ名>/<部品>.txt と画面の記録に残す。
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

from meviy_browser import FORBIDDEN, HERE, dump
from meviy_quote import enter_folder, start

BASE = "https://meviy.misumi-ec.com"


def lines(page):
    return [x.strip() for x in page.inner_text("body").splitlines() if x.strip()]


def open_viewer(page, folder, part, method=None):
    enter_folder(page, folder)
    page.wait_for_timeout(3000)
    row = page.locator("[class*=projectsListViewBodyRow]").filter(has_text=part).first
    if method and row.get_by_text("加工方法を選択してください").count():
        row.get_by_role("button", name=method, exact=True).first.click()      # 切削 / 板金
        page.wait_for_timeout(12000)
        row = page.locator("[class*=projectsListViewBodyRow]").filter(has_text=part).first
    href = row.locator("a[href*='3dview']").first.get_attribute("href")
    page.goto(BASE + href, wait_until="domcontentloaded")
    page.wait_for_timeout(20000)


def set_material(page, tab, material, surface_word):
    page.get_by_text("材質・表面処理を変更", exact=True).first.click()
    page.wait_for_timeout(3000)
    page.get_by_text(tab, exact=True).first.click()
    page.wait_for_timeout(1500)
    # 板金では「SUS304(2B)」のように材質名のあとに仕上げが付くので、前方一致で選ぶ
    page.get_by_text(re.compile("^" + re.escape(material))).last.click()
    page.wait_for_timeout(2500)
    t = lines(page)
    i = t.index("2. 表面処理を選ぶ")
    j = len(t) - 1 - t[::-1].index("決定する")
    opts = [x for x in t[i + 1:j] if "詳しく" not in x and "担当者見積" not in x]
    print("  表面処理の選択肢:", " / ".join(dict.fromkeys(opts)))
    pick = next((x for x in opts if surface_word in x), None)
    if pick is None:
        print(f"  「{surface_word}」は選べない。表面処理なしのまま進める")
    else:
        page.get_by_text(pick, exact=True).last.click()
        page.wait_for_timeout(1500)
    page.get_by_role("button", name="決定する").click()
    page.wait_for_timeout(8000)
    return pick


PRICE = re.compile(r"^1～\d+\s+[0-9,]+円", re.M)


def set_method_in_viewer(page, method):
    """ビューアの「加工方法」を合わせる（切削 / 板金）。変えたら形状の再認識を待つ。"""
    sel = page.locator("select").filter(has=page.locator("option", has_text=re.compile("^切削$"))).first
    if not sel.count():
        return "選択ボックスなし"
    cur = sel.evaluate("e => e.options[e.selectedIndex].text")
    if cur.strip() == method:
        return "そのまま"
    sel.select_option(label=method)
    page.wait_for_timeout(25000)
    return f"{cur.strip()} → {method}"


def confirm_and_read(page):
    """見積りを実行して画面の文字を返す。押すのは「自動見積開始」と「見積条件を確定」だけ。

    自動見積の対象外（担当者見積）の部品には「この内容で見積依頼へ」が出る。これは担当者への依頼になるので押さない。
    """
    for label in ("自動見積開始", "見積条件を確定"):
        assert not any(w in label for w in FORBIDDEN)
        btn = page.get_by_role("button", name=label)
        if btn.count() and btn.first.is_visible() and btn.first.is_enabled():
            btn.first.click()
            for _ in range(36):                  # 見積り計算を待つ（最長 3 分）
                page.wait_for_timeout(5000)
                body = page.inner_text("body")
                if PRICE.search(body) or "見積依頼へ" in body:
                    break
                nxt = page.get_by_role("button", name="見積条件を確定")
                if label == "自動見積開始" and nxt.count() and nxt.first.is_visible() and nxt.first.is_enabled():
                    break
    return lines(page)


def main():
    folder, part, tab, material, surface = sys.argv[1:6]
    method = sys.argv[6] if len(sys.argv) > 6 else None
    out = HERE / "result" / folder
    out.mkdir(parents=True, exist_ok=True)
    stem = part.rsplit(".", 1)[0]
    with sync_playwright() as p:
        ctx, page = start(p)
        try:
            open_viewer(page, folder, part, method)
            picked = set_material(page, tab, material, surface)
            t = confirm_and_read(page)
            dump(page, f"30_quote_{stem}")
            (out / f"{stem}.txt").write_text("\n".join(t), encoding="utf-8")
            hits = [x for x in t if re.search(r"円|出荷|型番|見積|納期|MV[A-Z0-9-]{6,}", x)]
            print(f"== {part}  材質 {material}  表面処理 {picked or 'なし'}")
            for x in hits[:40]:
                print("  ", x[:120])
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
