"""購入品の在庫を販売サイトで確かめる。見るだけで、カート・注文には触れない。

    python quote/stock_check.py

販売サイトが商品ページに埋め込んでいる在庫の情報（選択肢ごとの在庫）を、実ブラウザで読む。
  - Shopify（underwaterthruster.com）: /products/<handle>.js の variants[].available
  - WooCommerce（bluerobotics.com）  : form.variations_form の data-product_variations
  - そのほか                          : 画面の文字を quote/lookup/ に保存して人が読む
結果: quote/lookup/stock_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "lookup"
PROFILE = HERE / "meviy" / ".profile"

SHOPIFY = "https://www.underwaterthruster.com"
SHOPIFY_SEARCH = ("U2 mini", "bidirectional ESC 45A")            # 検索語（商品の handle を探す）
WOO = {
    "WetLink ペネトレータ": "https://bluerobotics.com/store/cables-connectors/penetrators/wlp-vp/",
    "ベント": "https://bluerobotics.com/store/cables-connectors/penetrators/vent-asm-r1/",
}
PAGES = {                                                        # 画面の文字を保存するだけのページ
    "stock_misumi_g135": "https://jp.misumi-ec.com/vona2/result/?Keyword=1A-G135",
    "stock_misumi_g85": "https://jp.misumi-ec.com/vona2/result/?Keyword=1A-G85",
    "stock_honda_chip1": "https://www.chip1stop.com/search?keyword=LPC-50M2LG",
    "stock_honda_mouser": "https://www.mouser.jp/c/?q=LPC-50M2LG",
    "stock_servo_ali": "https://ja.aliexpress.com/w/wholesale-ROVMaker-underwater-servo.html",
    "stock_br_vent_search": "https://bluerobotics.com/?s=vent&post_type=product",
}


def main():
    OUT.mkdir(exist_ok=True)
    rep = {}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False,
                                                   viewport={"width": 1400, "height": 1000}, locale="ja-JP")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            # ---- Shopify: 検索の候補から handle を得て、選択肢ごとの在庫を読む
            page.goto(SHOPIFY, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            for q in SHOPIFY_SEARCH:
                js = """async q => {
                    const r = await fetch('/search/suggest.json?q=' + encodeURIComponent(q) + '&resources[type]=product&resources[limit]=10');
                    const hs = (await r.json()).resources.results.products.map(p => p.handle);
                    const out = [];
                    for (const h of hs) {
                        const d = await (await fetch('/products/' + h + '.js')).json();
                        out.push({title: d.title, handle: h, variants: d.variants.map(v => ({name: v.title, available: v.available, price: v.price / 100}))});
                    }
                    return out;
                }"""
                rep[f"shopify: {q}"] = page.evaluate(js, q)
                page.wait_for_timeout(2000)
            # ---- WooCommerce: 選択肢ごとの在庫
            for name, url in WOO.items():
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(5000)
                js = """() => {
                    const f = document.querySelector('form.variations_form');
                    const whole = (document.querySelector('.summary .stock') || {}).innerText || '';
                    if (!f) return {title: document.title, stock: whole, cart: !!document.querySelector('button[name=add-to-cart], .single_add_to_cart_button')};
                    const v = JSON.parse(f.getAttribute('data-product_variations') || 'null');
                    return {title: document.title, stock: whole, variants: v && v.map(x => ({name: Object.values(x.attributes).join(' / '), sku: x.sku,
                            in_stock: x.is_in_stock, purchasable: x.is_purchasable, backorder: x.backorders_allowed,
                            note: (x.availability_html || '').replace(/<[^>]+>/g, '').trim(), price: x.display_price}))};
                }"""
                rep[f"woo: {name}"] = dict(page.evaluate(js), url=page.url)
                page.wait_for_timeout(2000)
            # ---- そのほか
            for name, url in PAGES.items():
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(12000)
                    text = page.inner_text("body")
                    (OUT / f"{name}.txt").write_text(f"{page.url}\n{page.title()}\n\n{text}", encoding="utf-8")
                    page.screenshot(path=str(OUT / f"{name}.png"))
                    print(f"{name}: {len(text)} 文字  {page.title()[:60]}")
                except Exception as e:
                    print(f"{name}: 失敗 {type(e).__name__} {str(e)[:100]}")
                page.wait_for_timeout(2500)
        finally:
            (OUT / "stock_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            ctx.close()
    for k, v in rep.items():
        print("==", k)
        for item in (v if isinstance(v, list) else [v]):
            print("  ", item.get("title"), item.get("stock", ""), item.get("url", ""))
            for x in item.get("variants") or []:
                print("      ", x)


if __name__ == "__main__":
    main()
