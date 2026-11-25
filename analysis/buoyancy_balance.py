"""浮力・重量の釣合い。CAD が書き出した部品ごとの質量・体積・重心から、浮力材の厚さとバラスト枚数を決める。

    python src/cad/build_uwd01.py        # analysis/out/cad_mass.json を書き出す
    python analysis/buoyancy_balance.py

モデル
  重量 W   = Σ 部品質量 + 内部搭載物 + 未作図の小ねじ類
  浮力 B   = ρ (Σ 部品の実体体積 + 耐圧容器の内部空間)
             耐圧容器の外にある部品はすべて水に浸かるので、実体体積がそのまま排水体積になる。
  重心 G, 浮心 C は質量・排水体積の重み付き平均。BG = C_y − G_y が正なら復原する。
  釣合いの目標: 淡水で正味浮力が重量の +1〜2 %（スラスタ停止で緩やかに浮く）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import rov_params as P

OUT = Path(__file__).parent / "out"
TARGET = 0.015                     # 正味浮力 / 重量 の目標
SMALL_PARTS = (0.15, 20e-6)        # [仮] 未作図の小ねじ・ゴムシート: 質量 kg, 体積 m3
INSIDE = "内部機器"                 # 耐圧容器の中に入るユニット


def hull_air():
    """耐圧容器の内部空間の体積 m3 と図心 mm。"""
    mm3 = math.pi / 4 * P.HULL_ID ** 2 * P.HULL_LEN
    mm3 += 2 * math.pi / 4 * (P.SEAL_BORE ** 2 - P.HULL_ID ** 2) * P.SEAL_LEN          # 両端の内径仕上げ分
    mm3 -= 2 * math.pi / 4 * (P.SPIGOT_OD ** 2 - P.SPIGOT_ID ** 2) * P.SPIGOT_LEN      # 端蓋のはめ込み部
    ap = math.pi / 4 * P.WINDOW_APERTURE ** 2 * P.CAP_PLATE_T                          # 前端蓋の窓開口
    x = ap * (P.HULL_LEN / 2 + P.CAP_PLATE_T / 2) / (mm3 + ap)
    return (mm3 + ap) * 1e-9, (x, 0.0, 0.0)


def load():
    rows = json.loads((OUT / "cad_mass.json").read_text(encoding="utf-8"))
    # 耐圧容器の中にある部品は水を押しのけない（容器の内部空間として数える）ので、体積を 0 にする
    items = [(r["unit"], r["part"], r["mass"], 0.0 if r["unit"] == INSIDE else r["volume"], tuple(r["cg"])) for r in rows]
    v_air, c_air = hull_air()
    items.append(("耐圧容器", "内部空間", 0.0, v_air, c_air))
    items.append((INSIDE, "未作図の内部機器(仮)", P.PAYLOAD_MASS, 0.0, P.PAYLOAD_CG))
    items.append(("締結", "小ねじ類(仮)", SMALL_PARTS[0], SMALL_PARTS[1], (0.0, 0.0, 0.0)))
    return items


def summarize(items, rho):
    m = sum(i[2] for i in items)
    v = sum(i[3] for i in items)
    g = [sum(i[2] * i[4][k] for i in items) / m for k in range(3)]
    c = [sum(i[3] * i[4][k] for i in items) / v for k in range(3)]
    return {"質量 kg": m, "排水体積 L": v * 1e3, "浮力 kgf": rho * v, "正味浮力 kgf": rho * v - m,
            "重心 mm": g, "浮心 mm": c, "BG mm": c[1] - g[1]}


def main():
    items = load()
    by_unit = {}
    for u, _, m, v, _ in items:
        a = by_unit.setdefault(u, [0.0, 0.0])
        a[0] += m
        a[1] += v
    print(f"{'ユニット':<10}{'質量 kg':>10}{'排水 L':>10}{'水中重量 kgf':>14}")
    for u, (m, v) in by_unit.items():
        print(f"{u:<10}{m:>10.3f}{v * 1e3:>10.3f}{m - P.RHO_FRESH * v:>14.3f}")
    res = {}
    for name, rho in (("淡水", P.RHO_FRESH), ("海水", P.RHO_SEA)):
        s = res[name] = summarize(items, rho)
        print(f"\n■ {name}  質量 {s['質量 kg']:.2f} kg, 浮力 {s['浮力 kgf']:.2f} kgf, 正味 {s['正味浮力 kgf']:+.2f} kgf "
              f"({s['正味浮力 kgf'] / s['質量 kg'] * 100:+.1f} %)")
        print(f"   重心 ({s['重心 mm'][0]:.1f}, {s['重心 mm'][1]:.1f}, {s['重心 mm'][2]:.1f})  "
              f"浮心 ({s['浮心 mm'][0]:.1f}, {s['浮心 mm'][1]:.1f}, {s['浮心 mm'][2]:.1f})  BG {s['BG mm']:.1f} mm")

    # 釣合わせ: 浮力材の厚さ 1 mm、バラスト 1 枚あたりの正味浮力の変化（淡水）
    s = res["淡水"]
    foam_area = 2 * P.FOAM_X * 2 * P.INNER_HALF_W * 1e-6                       # m2
    per_mm = foam_area * 1e-3 * (P.RHO_FRESH - P.FOAM.rho)                     # kgf / mm
    bal = P.BALLAST_L * P.BALLAST_T * P.BALLAST_W * 1e-9
    per_plate = bal * (P.SUS304.rho - P.RHO_FRESH)                             # kgf / 枚（沈む向き）
    want = TARGET * s["質量 kg"]
    d_foam = (want - s["正味浮力 kgf"]) / per_mm
    print(f"\n■ 釣合わせ（淡水で正味 +{TARGET * 100:.1f} % を狙う）")
    print(f"   浮力材 1 mm あたり {per_mm * 1000:.1f} gf、バラスト 1 枚あたり −{per_plate * 1000:.0f} gf")
    print(f"   現在の浮力材厚さ {P.FOAM_T:g} mm → 必要な厚さ {P.FOAM_T + d_foam:.1f} mm（バラスト片舷 {P.BALLAST_N} 枚のまま）")
    trim = math.degrees(math.atan2(s["重心 mm"][0] - s["浮心 mm"][0], s["BG mm"]))
    print(f"   前後の釣合い: 重心が浮心より {s['重心 mm'][0] - s['浮心 mm'][0]:+.1f} mm 前 → 静止姿勢 約 {trim:+.1f}°（+ は機首下げ）")
    res["釣合わせ"] = {"浮力材 gf/mm": per_mm * 1000, "バラスト gf/枚": per_plate * 1000,
                    "必要な浮力材厚さ mm": P.FOAM_T + d_foam, "静止ピッチ角 deg": trim}
    (OUT / "buoyancy_balance.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
