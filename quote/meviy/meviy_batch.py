"""quote_plan.csv の部品を順に meviy で条件設定して、見積り（型番・単価・出荷日）を表にする。

    python quote/meviy/meviy_batch.py <フォルダ名> [部品名 ...]

部品名を省くと quote_plan.csv の全部品。行うのは見積条件の確定まで（注文・カートには進まない）。
結果: result/<フォルダ名>/quotes.csv、部品ごとの画面の文字は <部品>.txt。
"""
from __future__ import annotations

import csv
import re
import sys
import traceback

from playwright.sync_api import sync_playwright

from meviy_browser import HERE, dump
from meviy_part_quote import BASE, PRICE, confirm_and_read, lines, set_material, set_method_in_viewer
from meviy_quote import enter_folder, start


def row_of(page, part):
    return page.locator("[class*=projectsListViewBodyRow]").filter(has_text=f"{part}.SLDPRT").first


def set_method(page, part, method):
    """一覧で加工方法を合わせる。未選択ならボタン、別の方法になっていれば選択ボックスで変える。"""
    row = row_of(page, part)
    if row.get_by_text("加工方法を選択してください").count():
        row.get_by_role("button", name=method, exact=True).first.click()
        page.wait_for_timeout(15000)
        return "選択"
    cur = row.locator(".select__single-value").first
    if cur.count() and cur.inner_text().strip() != method:
        row.locator(".select__control").first.click()
        page.wait_for_timeout(800)
        page.locator(".select__option").filter(has_text=re.compile(f"^{method}$")).first.click()
        page.wait_for_timeout(15000)
        return "変更"
    return "そのまま"


def parse(t):
    """画面の文字から 型番・単価（1 個）・出荷日・状態を拾う。"""
    text = "\n".join(t)
    m = re.search(r"^1～\d+\s+([0-9,]+)円.*?(\d+)日目", text, re.M)
    # 型番は標準納期のもの。末尾に -E（特急）や -L（長納期）が付く枝番も画面に出るので、いちばん短いものを採る
    pns = re.findall(r"MV[A-Z0-9]+(?:-[A-Z0-9]+){2,4}", text)
    pn = min(pns, key=len) if pns else ""
    if m:
        return pn, m.group(1).replace(",", ""), m.group(2), "自動見積"
    if "見積依頼へ" in text or "担当者見積をご利用ください" in text:
        i = t.index("注意事項") if "注意事項" in t else 0
        why = []
        for x in t[i + 1:i + 12]:                     # 注意事項の欄は「確認」か「基本情報」で終わる
            if x in ("確認", "基本情報"):
                break
            why.append(x)
        return "", "", "", "自動見積の対象外（担当者見積）: " + "、".join(why)
    return "", "", "", "金額が出ていない（画面の記録を確認）"


def main():
    folder, only = sys.argv[1], sys.argv[2:]
    plan = [r for r in csv.DictReader(open(HERE / "quote_plan.csv", encoding="utf-8")) if not only or r["部品"] in only]
    out = HERE / "result" / folder
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as p:
        ctx, page = start(p)
        try:
            for r in plan:
                part = r["部品"]
                res = dict(r, 型番="", 単価="", 出荷日="", 状態="")
                try:
                    page.goto(BASE + "/ja-jp/app/fa/mypage", wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    enter_folder(page, folder)
                    page.wait_for_timeout(3000)
                    # 見積り済み（型番が出ている）の部品は設定し直さない。同じ条件でも確定し直すと
                    # 「型番の再発行」の確認が出て、型番が変わってしまう
                    done = bool(re.search(r"MV[A-Z0-9]+-", row_of(page, part).inner_text()))
                    how = "見積り済み" if done else set_method(page, part, r["加工方法"])
                    if not done and row_of(page, part).locator("a[href*='3dview']").count() == 0:
                        page.wait_for_timeout(20000)       # 加工方法を選んだ直後は形状の認識中でリンクが無い
                    href = row_of(page, part).locator("a[href*='3dview']").first.get_attribute("href")
                    page.goto(BASE + href, wait_until="domcontentloaded")
                    page.wait_for_timeout(20000)
                    head = lines(page)
                    kind = next((x for x in head if x.startswith("品名")), "")
                    if done or PRICE.search("\n".join(head)):
                        picked, t = r["表面処理"], head            # 見積り済み。読むだけ
                        how = "見積り済み"
                    else:
                        how2 = set_method_in_viewer(page, r["加工方法"])
                        if how2 not in ("そのまま", "選択ボックスなし"):
                            how = how2
                            kind = next((x for x in lines(page) if x.startswith("品名")), kind)
                        picked = set_material(page, r["材質の区分"], r["材質"], r["表面処理"])
                        t = confirm_and_read(page)
                    dump(page, f"30_quote_{part}")
                    (out / f"{part}.txt").write_text("\n".join(t), encoding="utf-8")
                    res["型番"], res["単価"], res["出荷日"], res["状態"] = parse(t)
                    res["meviy品名"] = kind.replace("品名", "").strip()
                    res["表面処理(設定)"] = picked or "なし"
                    print(f"{part}: 加工方法 {how} / {res['meviy品名']} / {res['状態']} {res['単価']} 円 {res['出荷日']} 日目 {res['型番']}")
                except Exception as e:
                    res["状態"] = f"操作失敗: {type(e).__name__}: {str(e).splitlines()[0][:80]}"
                    print(f"{part}: {res['状態']}")
                    tb = traceback.extract_tb(e.__traceback__)
                    print("   場所: " + " ← ".join(f"{f.name}:{f.lineno} {f.line}" for f in tb[:3][::-1]))
                    try:
                        dump(page, f"31_fail_{part}")
                    except Exception:
                        pass
                results.append(res)
        finally:
            ctx.close()
    keys = ["部品", "加工方法", "meviy品名", "材質", "表面処理(設定)", "状態", "単価", "出荷日", "型番", "備考"]
    path = out / "quotes.csv"
    old = {}
    if path.exists() and only:                    # 一部だけやり直したときは、ほかの行を残す
        old = {r["部品"]: r for r in csv.DictReader(open(path, encoding="utf-8-sig"))}
    for r in results:
        old[r["部品"]] = {k: r.get(k, "") for k in keys}
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(old.values())
    print(path)


if __name__ == "__main__":
    main()
