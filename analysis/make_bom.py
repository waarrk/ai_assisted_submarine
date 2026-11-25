"""部品表を作る。CAD に配置した数量（analysis/out/cad_mass.json）に、手配情報を足して 2 つの表を出す。

    python src/cad/build_uwd01.py
    python analysis/make_bom.py

出力（Excel でそのまま開ける UTF-8 BOM 付き CSV）
    doc/08_購買/部品表/UWD-01_加工品.csv   材料・素材寸法・加工方法・加工基準
    doc/08_購買/部品表/UWD-01_購入品.csv   メーカー・品番・手配先

確認区分
    確定   規格または設計値から決まるもの
    要確認 品番・在庫・価格を発注前に手配先で確かめるもの（調査時に販売ページを開けなかった）
    仮     現物・図面が無く、寸法や数量が変わりうるもの
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import rov_params as P

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "out"
DST = ROOT / "doc" / "08_購買" / "部品表"

HDPE = ("HDPE", f"板 t{P.PLATE_T:g}（フレームの板と同じ 1 枚から）", "ウォータージェット切断")

# 加工品: 部品名 -> (材質, 素材, 加工方法, 加工基準, 普通公差, 備考)
MADE = {
    "耐圧筒": ("A6063-T5", f"丸パイプ φ{P.HULL_OD:g}×t{P.HULL_T:g}×L{P.HULL_LEN + 5:g}",
            f"切断 → 旋盤で両端面・両端内径 φ{P.SEAL_BORE:g} H9 を仕上げ → アルマイト", "中心軸・端面", "JIS B 0405-m",
            "シール面 Ra1.6。生爪で全周を保持。素材は藤野金属の在庫寸法表に掲載"),
    "後端蓋": ("A6061-T6", "丸棒 φ160×L45", "旋盤 2 工程 → 穴あけ・M10 タップ 11 か所、内側 M4 タップ 2 か所 → アルマイト",
            "基準A つば当たり面・基準B 中心軸", "JIS B 0405-m", f"はめ込み φ{P.SEAL_BORE:g} f8。外面 Ra1.6（ペネトレータの Oリング座）"),
    "前端蓋": ("A6061-T6", "丸棒 φ160×L45", "旋盤 2 工程 → M4 タップ 6 か所 → アルマイト", "基準A つば当たり面・基準B 中心軸",
            "JIS B 0405-m", "窓の当たり面 Ra1.6"),
    "観察窓": ("アクリル キャスト板", f"t{P.WINDOW_T:g} 板から φ{P.WINDOW_OD:g}", "レーザーまたは旋盤で円形に切り出し", "当たり面・中心",
            "JIS B 0405-m", "シール面に傷を付けない"),
    "窓押え環": (HDPE[0], HDPE[1], HDPE[2], "中心", "JIS B 0405-c", "M4×6 で窓を直接押さえる"),
    "側板": (HDPE[0], f"板 t{P.PLATE_T:g}（{2 * P.SIDE_X:g}×{P.SIDE_TOP - P.SIDE_BOTTOM:g} が 2 枚）", HDPE[2], "筒の中心線", "JIS B 0405-c", "Ø3.4 は下穴で切りドリルで仕上げ"),
    "筒受け": (HDPE[0], HDPE[1], HDPE[2], "合わせ面・左右中心", "JIS B 0405-c", "受け面にゴムシート t0.5"),
    "筒押え": (HDPE[0], HDPE[1], HDPE[2], "合わせ面・左右中心", "JIS B 0405-c", "受け面にゴムシート t0.5"),
    "底板": (HDPE[0], HDPE[1], HDPE[2], "前後・左右の中心線", "JIS B 0405-c", ""),
    "アーム板": (HDPE[0], HDPE[1], HDPE[2], "サーボ軸の真下・左右中心", "JIS B 0405-c", "マニピュレータの台と下あご"),
    "可動爪": (HDPE[0], HDPE[1], HDPE[2], "回転中心", "JIS B 0405-c", "左右共通"),
    "浮力材": ("Divinycell HCP30 相当", f"板 t{P.FOAM_T:g}", "のこ・ルータで切り出し", "中心・下面", "±1", "水圧つぶれ点 30 bar"),
    "バラスト": ("SUS304", f"フラットバー {P.BALLAST_T:g}×{P.BALLAST_W:g}", f"L{P.BALLAST_L:g} に切断、穴あけ 2-Ø5.5", "中心", "JIS B 0405-c", "枚数で釣合いを取る"),
    "内部トレイ": ("A5052-H32", f"板 t{P.TRAY_T:g}", "板金: レーザーで抜き、タブを 90° 曲げ（内 R2）", "取付面・トレイ下面・左右中心", "JIS B 0405-m", "後端蓋の支柱 2 本に固定"),
    "BPB_バックプレーン基板": ("FR-4 t1.6", f"{P.BPB_LEN:g}×{P.BPB_W:g}", "プリント基板（別途設計・発注）", "後端・左右中心", "—",
                     "BIRDS-5 BPB の構造。幅を 96 → 70 に詰めるので配線の引き直しが要る"),
    "差し込み基板": ("FR-4 t1.6", f"{P.CARD_W:g}×{P.CARD_H:g}", "プリント基板（BIRDS-5 の外形のまま）", "下端・左右中心", "—", "スロット FAB/OBC/COM/M-1/M-2/RAB"),
    "ハーネス": ("—", f"ケーブル Ø{P.THR_CABLE_D:g}（スラスタ付属）ほか", "配線・結束", "—", "—", "経路の検討用モデル"),
}

# 購入品（CAD に配置済み）: 部品名 -> (品名, メーカー, 品番・仕様, 手配先, 確認区分, 備考)
BOUGHT = {
    "ApisQueen_U2-Mini": ("水中スラスタ", "ApisQueen", "U2 Mini 12–16 V（正ペラ CW・逆ペラ CCW 各 4）", "underwaterthruster.com / AliExpress", "確認済",
                          "販売ページで 5,088 円/個（ESC なし）を確認。配布 3D データを使用"),
    "WetLink_WLP-M10-7.5MM": ("ケーブルペネトレータ", "Blue Robotics", "WetLink WLP-M10-7.5MM-HC ×8、WLP-M10-4.5MM-HC ×1、テザー用 1、ベントプラグ 1",
                              "Blue Robotics", "確認済", "定格 1000 m。13〜20 米ドル/個。配布 3D データを使用"),
    "1A-G135": ("Oリング G-135", "森清化工", "1A-G135（JIS B 2401 NBR 1種A）", "ミスミ", "確認済", "端蓋はめ込み部 2 段×2"),
    "1A-G85": ("Oリング G-85", "森清化工", "1A-G85（JIS B 2401 NBR 1種A）", "ミスミ", "確認済", "観察窓"),
    "ROVMaker_RM-SV-40": ("水中サーボ", "ROVMaker", "RM-SV-40 Angle version（使用水深 300 m、12 V）", "AliExpress（AI Robot Store）", "確認済",
                                 "28,206 円（2026-11-25）。公式ストア rovmaker.org の旧型式は在庫切れのため置き換えた"),
    "Hirose_A3C-50DA-2DSA(71)": ("50 ピンコネクタ", "ヒロセ電機", "A3C-50DA-2DSA(71)", "DigiKey ほか", "確認済", "BPB 用。配布 3D データを使用"),
    "結束バンド_幅4.8": ("結束バンド 幅 4.8（耐候）", "ミスミ", "PA66 耐候グレード、長さ 150 以上", "ミスミ", "要確認", "ハーネス固定。側板 8 か所、底板 2 か所"),
    "LiPo_4S-10Ah": ("LiPo バッテリ 4S 10 Ah", "—", "外形 170×70×45 以下", "—", "仮", "寸法は実物で確かめる"),
}

# RAPiD Design で取り込んだ MISUMI 品（cad/00_既製品/MISUMI_parts.csv に型番・単価・出荷日がある）: 型番 -> 用途
MISUMI_USE = {
    "SCB3-16": "スラスタ取付 8 基×4。板厚 10 ＋ねじ込み 6",
    "SCB3-14": "サーボ取付（アーム板の下から）。板厚 10 ＋ねじ込み 4（めねじ深さ 5）",
    "SCB4-14": "可動爪 → サーボ出力円板・従動軸。板厚 10 ＋ねじ込み 4（めねじ深さ 5）",
    "SCB4-30": "窓押え環 → 前端蓋",
    "SCB5-35": "アーム板 4、バラスト 4。下でナット止め",
    "SCB4-8": "内部トレイ → 支柱",
    "SLBNR5": "横通しボルト 8、可動爪のつなぎ棒 4、アーム板 4、バラスト 4",
    "SPWF5": "ナットの下（樹脂板・底板の下面）と、アーム板のボルト頭の下",
    "FABS5-250": "フレーム横通し。下 2 本は端蓋の抜け止め",
    "FABS5-125": "可動爪のつなぎ棒",
    "VSLSBG8-40.0-M4-N4": "内部トレイの支柱。おねじ側を後端蓋のめねじ（止まり穴）へねじ込む",
}


def _name(c):
    """RAPiD Design の半角カナの品名を全角にする。"""
    return c.replace("ﾎﾞﾙﾄ", "ボルト").replace("ﾅｯﾄ", "ナット")


MISUMI_CSV = Path(__file__).resolve().parents[1] / "cad" / "00_既製品" / "MISUMI_parts.csv"
if MISUMI_CSV.exists():
    for r in csv.DictReader(open(MISUMI_CSV, encoding="utf-8-sig")):
        k = r["SpecNumber"]
        BOUGHT[f"MISUMI_{k}"] = (_name(r["Class"]) + " " + k, "ミスミ", f"{k}（SUS304 相当）", "ミスミ（RAPiD Design で取り込み）", "確認済",
                                 MISUMI_USE.get(k, ""))
        MISUMI_STOCK = f"購入可。単価 {r['UnitPrice']} 円、出荷 {r['ViaShipDate']}（RAPiD Design の表示、{r['取り込み日']}）"
        globals().setdefault("_MISUMI_STOCK", {})[_name(r["Class"]) + " " + k] = MISUMI_STOCK

# 購入品（CAD に作図していないもの）: (品名, メーカー, 品番・仕様, 数量, 手配先, 確認区分, 備考)
EXTRA = [
    ("サーボ延長ケーブル", "—", "3 芯、外径 4〜5 mm、0.5 m", 1, "—", "要確認", "サーボ付属ケーブル 0.7 m が後端蓋に届かないため。接続部は樹脂で封止する"),
    ("水中用ケーブル接続（封止）キット", "—", "熱収縮チューブ（接着剤付き）＋ポッティング樹脂", 1, "—", "要確認", "サーボケーブルの延長部"),
    ("DC-DC コンバータ 12 V 5 A", "—", "入力 4S LiPo（13〜17 V）、出力 12 V", 1, "—", "要確認", "サーボの定格 12 V 用。耐圧容器内"),
    ("ゴムシート t0.5", "—", "NBR または CR、幅 10", 1, "ミスミ / モノタロウ", "要確認", "筒受け面 4 か所"),
    ("双方向 ESC", "ApisQueen", "45 A 双方向（BEC なし）", 8, "underwaterthruster.com / AliExpress", "確認済", "耐圧容器内に収納"),
    ("50 ピンコネクタ（基板側）", "本多通信工業", "LPC-50M2LG", 6, "—", "要確認", "差し込み基板に実装。3D データ未入手"),
    ("ベントプラグ M10", "Blue Robotics", "M10 エンクロージャベント", 1, "Blue Robotics", "確認済", "気密試験用"),
]


# 在庫の確認結果（quote/stock_check.py ほかで販売ページを開いて確かめた日付と内容）。品名 -> 表示
STOCK_DATE = "2026-11-25"
NOT_CHECKED = "未確認（品番を決めていない）"
STOCK = {
    "水中スラスタ": "在庫あり。公式ストアで CW・CCW（ESC なし）とも購入可、32 米ドル（5,088 円）/個",
    "ケーブルペネトレータ": "在庫あり。Blue Robotics で M10-7.5-HC 81 個、M10-4.5-HC 92 個、各 15 米ドル。ベントは別行",
    "Oリング G-135": "購入可。ミスミ 1A-G135（森清化工）通常出荷 2 日目。在庫数の表示はない",
    "Oリング G-85": "購入可。ミスミ 1A-G85（森清化工）97 円、通常出荷 2 日目。在庫数の表示はない",
    "水中サーボ": "在庫あり。AliExpress（AI Robot Store）RM-SV-40 に 985 個、28,206 円、送料無料、配達 12/2〜12/10 の表示",
    "50 ピンコネクタ": "在庫あり。DigiKey 40 個、1,101 円/個（メーカー標準リードタイム 20 週間）",
    "双方向 ESC": "在庫あり。公式ストアで 45 A 双方向 17.64 米ドル（防水なし）、防水・BEC なし 29 米ドル",
    "50 ピンコネクタ（基板側）": "入手先が見つからない。Chip One Stop で該当なし、DigiKey は自動確認できず。ヒロセの嵌合品（A3A-50PA-2SV(71) DigiKey 18 個）などへの置き換えを要検討",
    "ベントプラグ M10": "在庫あり。Blue Robotics 240 個",
    "LiPo バッテリ 4S 10 Ah": "未確認（品番を決めていない）",
}


STOCK.update(globals().get("_MISUMI_STOCK", {}))


def main():
    rows = json.loads((OUT / "cad_mass.json").read_text(encoding="utf-8"))
    qty = Counter(r["part"] for r in rows)
    mass = {r["part"]: r["mass"] for r in rows}
    unit = {r["part"]: r["unit"] for r in rows}
    missing = sorted(set(qty) - set(MADE) - set(BOUGHT))
    if missing:
        raise SystemExit(f"手配情報が無い部品: {missing}")
    DST.mkdir(parents=True, exist_ok=True)
    made = DST / "UWD-01_加工品.csv"
    with open(made, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["No.", "ユニット", "品名", "数量", "材質", "素材", "加工方法", "加工基準", "普通公差", "質量 g/個", "備考", "cad"])
        n = 0
        for name, (mat, stock, how, datum, tol, note) in MADE.items():
            if name in qty:
                n += 1
                w.writerow([n, unit[name], name, qty[name], mat, stock, how, datum, tol, round(mass[name] * 1000), note, f"{name}.SLDPRT"])
    bought = DST / "UWD-01_購入品.csv"
    with open(bought, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["No.", "品名", "メーカー", "品番・仕様", "数量", "手配先", "確認区分", f"在庫（{STOCK_DATE} 確認）", "備考", "cad"])
        n = 0
        for name, (title, maker, spec, shop, state, note) in BOUGHT.items():
            if name in qty:
                n += 1
                w.writerow([n, title, maker, spec, qty[name], shop, state, STOCK.get(title, NOT_CHECKED), note, f"{name}.SLDPRT"])
        for title, maker, spec, q, shop, state, note in EXTRA:
            n += 1
            w.writerow([n, title, maker, spec, q, shop, state, STOCK.get(title, NOT_CHECKED), note, "（作図なし）"])
    print(f"{made}: {sum(1 for k in MADE if k in qty)} 品目")
    print(f"{bought}: {sum(1 for k in BOUGHT if k in qty) + len(EXTRA)} 品目")


if __name__ == "__main__":
    main()
