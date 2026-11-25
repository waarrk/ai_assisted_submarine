"""meviy を操作するブラウザの共通処理。

ログインは人が行う。パスワードはスクリプトに書かず、ログイン後の状態を専用プロファイル
（quote/meviy/.profile/、Git 管理外）に残して次回から使い回す。
このスクリプト群が行うのは「フォルダ作成・アップロード・見積条件の読み取り」までで、注文はしない。
"""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROFILE = HERE / ".profile"
EXPLORE = HERE / "explore"
MYPAGE = "https://meviy.misumi-ec.com/ja-jp/app/fa/mypage"

# 注文につながる操作。画面上の文言にこれらを含むボタンは押さない
FORBIDDEN = ("注文", "発注", "購入", "カート", "決済", "お支払")


def open_browser(p, headless=False):
    """インストール済みの Chrome を専用プロファイルで開く。"""
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE), channel="chrome", headless=headless, viewport={"width": 1500, "height": 950},
        accept_downloads=True, locale="ja-JP")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return ctx, page


def logged_in(page):
    """マイページの画面にいて、ログイン画面へ飛ばされていないこと。"""
    return "meviy.misumi-ec.com" in page.url and "/app/" in page.url and "login" not in page.url.lower()


def wait_login(page, timeout_s=900):
    """人がログインを終えるまで待つ。"""
    page.goto(MYPAGE, wait_until="domcontentloaded")
    stable, t0 = 0, time.time()
    while time.time() - t0 < timeout_s:
        page.wait_for_timeout(2000)
        stable = stable + 1 if logged_in(page) else 0
        if stable >= 4:
            return True
    return False


def dump(page, name):
    """画面の状態を残す（画面の構成を調べる用）: スクリーンショットと、操作できる要素の一覧。"""
    EXPLORE.mkdir(exist_ok=True)
    page.screenshot(path=str(EXPLORE / f"{name}.png"))
    items = page.evaluate("""() => {
        const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
        const txt = e => (e.innerText || e.value || e.getAttribute('aria-label') || e.getAttribute('title') || e.getAttribute('placeholder') || '').trim().replace(/\\s+/g, ' ').slice(0, 60);
        const out = [];
        for (const e of document.querySelectorAll('button, a, input, select, textarea, [role=button], [role=menuitem], [role=tab]')) {
            if (!vis(e)) continue;
            const r = e.getBoundingClientRect();
            out.push([e.tagName.toLowerCase(), e.getAttribute('type') || '', e.id || '', (e.className || '').toString().slice(0, 50), txt(e), Math.round(r.x), Math.round(r.y)].join(' | '));
        }
        return out;
    }""")
    (EXPLORE / f"{name}.txt").write_text(f"{page.url}\n{page.title()}\n\n" + "\n".join(items), encoding="utf-8")
    return len(items)


if __name__ == "__main__":
    with sync_playwright() as p:
        ctx, page = open_browser(p)
        print("ブラウザを開きました。meviy にログインしてください（最大 15 分待ちます）。")
        ok = wait_login(page)
        print("ログイン確認:", "OK" if ok else "時間切れ", page.url)
        if ok:
            page.wait_for_timeout(4000)
            print("要素数", dump(page, "01_mypage"))
        ctx.close()
