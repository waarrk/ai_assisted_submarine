"""スラスタ配置の事前計算: 6 自由度の制御行列、各軸で出せる力・モーメント、姿勢保持の余裕。

    python analysis/thruster_allocation.py

モデル
  スラスタ i の位置 r_i、推力方向 d_i（単位ベクトル）、指令 u_i（+ 正転, − 逆転）に対し
      力 F = Σ d_i u_i,   モーメント M = Σ (r_i − r_G) × d_i u_i
  これを w = B u（w = [Fx, Fy, Fz, Mx, My, Mz]）と書く。B の階数が 6 なら全自由度を独立に制御できる。
  各軸の最大値は、ほかの 5 成分を 0 に保ったまま出せる量。最小ノルム解 u = B⁺ e を、
  どれか 1 台が上限（正転 T, 逆転 r T）に達するまで拡大して求める（真の最大値以下の控えめな値）。
  姿勢保持: 傾き θ のとき復原モーメントは W g BG sinθ。スラスタのモーメントがこれを上回る範囲で
  任意の姿勢を保てる。

軸: X = 前, Y = 上, Z = 右舷。Mx = ロール, My = ヨー, Mz = ピッチ。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import rov_params as P

OUT = Path(__file__).parent / "out"
AXES = ("Fx 前後", "Fy 上下", "Fz 左右", "Mx ロール", "My ヨー", "Mz ピッチ")


def matrix(cg):
    cols = []
    for _, r, d in P.THRUSTERS:
        r = (np.array(r) - cg) * 1e-3
        d = np.array(d)
        cols.append(np.concatenate([d, np.cross(r, d)]))
    return np.array(cols).T


def axis_max(B, fwd, rev):
    """各軸の ± 方向について、ほかの成分を 0 に保って出せる最大値。"""
    pinv = np.linalg.pinv(B)
    out = []
    for i in range(6):
        row = []
        for sign in (1, -1):
            u = pinv[:, i] * sign
            lim = np.where(u > 0, fwd, rev)
            k = np.min(lim[np.abs(u) > 1e-9] / np.abs(u[np.abs(u) > 1e-9]))
            row.append(k)
        out.append(row)
    return np.array(out)


def main():
    bal = OUT / "buoyancy_balance.json"
    if bal.exists():
        s = json.loads(bal.read_text(encoding="utf-8"))["淡水"]
        cg, mass, bg = np.array(s["重心 mm"]), s["質量 kg"], s["BG mm"] * 1e-3
    else:
        cg, mass, bg = np.zeros(3), 14.0, 0.03
        print("buoyancy_balance.json が無いので仮の重心・質量を使う")
    T = P.THR_THRUST_KGF * P.G
    B = matrix(cg)
    sv = np.linalg.svd(B, compute_uv=False)
    print(f"制御行列 B (6×{B.shape[1]}): 階数 {np.linalg.matrix_rank(B)}, 特異値 {np.round(sv, 3)}")
    mx = axis_max(B, T, T * P.THR_REV_RATIO)
    res = {"階数": int(np.linalg.matrix_rank(B)), "軸": {}}
    print(f"\n1 台の推力: 正転 {T:.1f} N, 逆転 {T * P.THR_REV_RATIO:.1f} N（逆転比は仮）")
    print(f"{'軸':<10}{'+ 方向':>10}{'− 方向':>10}")
    for name, (a, b) in zip(AXES, mx):
        unit = "N" if name[0] == "F" else "N·m"
        print(f"{name:<10}{a:>8.2f} {unit:<4}{b:>8.2f} {unit}")
        res["軸"][name] = {"+": a, "-": b, "単位": unit}
    # 姿勢保持
    restoring = mass * P.G * bg
    print(f"\n復原モーメントの最大値 W g BG = {restoring:.2f} N·m（質量 {mass:.1f} kg, BG {bg * 1e3:.1f} mm）")
    for name, i in (("ロール", 3), ("ピッチ", 5)):
        tau = min(mx[i])
        ang = 90.0 if tau >= restoring else float(np.degrees(np.arcsin(tau / restoring)))
        print(f"   {name}: 出せるモーメント {tau:.2f} N·m → 保持できる傾き {'任意（余裕 %.1f 倍）' % (tau / restoring) if ang >= 90 else '%.0f° まで' % ang}")
        res[f"{name} 保持"] = {"モーメント N·m": tau, "復原比": tau / restoring}
    hover = mx[1].min() / P.G
    print(f"   上下方向に出せる力 {hover:.2f} kgf（正味浮力のずれ・ペイロード変化の吸収分）")
    print(f"   8 台同時最大の電流 {8 * P.THR_I_MAX:.0f} A")
    (OUT / "thruster_allocation.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
