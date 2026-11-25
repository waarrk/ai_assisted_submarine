"""可制御性の事前計算: スラスタ 8 台で 6 自由度を独立に動かせるか、故障時にどこまで残るか。

    python analysis/buoyancy_balance.py      # 先に重心・BG を出す
    python analysis/controllability.py

調べること
  1. 静的な可制御性   w = B u（w = [Fx, Fy, Fz, Mx, My, Mz]）の階数・特異値・条件数。
                      モーメントは代表長さ L で割って力の単位にそろえてから比べる。
  2. 出せる力の範囲   ほかの 5 成分を 0 に保ったまま各軸に出せる最大値を、線形計画法で厳密に求める
                      （thruster_allocation.py の最小ノルム解は控えめな値。こちらが真の上限）。
  3. 故障時           1 台停止・2 台停止の全組合せについて、階数と各軸の最大値。
  4. 動的な可制御性   静止（ホバリング）まわりの線形モデル
                          η' = ν,   M ν' = −G η − D ν + B u
                      の可制御性を PBH 条件 rank [A − λI, Bc] で判定する（12 なら全状態を動かせる）。
                      M は部品を重心位置の点質量とみなした質量・慣性（付加質量は含めない = 加速度は上限側の見積り）。
                      G は復原（ロール・ピッチに W·BG）。D（抵抗）は未知なので 0 とする（階数には影響しない）。
  5. 姿勢の応答       各軸の最大角加速度と、ロール・ピッチの振り子としての固有周期。

軸: X = 前, Y = 上, Z = 右舷。Mx = ロール, My = ヨー, Mz = ピッチ。
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

import rov_params as P
from buoyancy_balance import load
from thruster_allocation import AXES, matrix

OUT = Path(__file__).parent / "out"
NAMES = [t[0] for t in P.THRUSTERS]
L_REF = 0.2          # モーメントを力に換算する代表長さ m（スラスタの腕の長さ程度）


def axis_max_lp(B, fwd, rev, dead=()):
    """各軸 ± について、ほかの 5 成分を 0 に保って出せる最大値（線形計画法）。dead = 止まっているスラスタの番号。"""
    n = B.shape[1]
    bounds = [(0.0, 0.0) if i in dead else (-rev, fwd) for i in range(n)]
    out = np.zeros((6, 2))
    for i in range(6):
        others = [k for k in range(6) if k != i]
        for j, sign in enumerate((1, -1)):
            r = linprog(-sign * B[i], A_eq=B[others], b_eq=np.zeros(5), bounds=bounds, method="highs")
            out[i, j] = abs(r.fun) if r.success else 0.0
    return out


def inertia(items, cg):
    """点質量近似の慣性テンソル（重心まわり, kg·m2）。"""
    I = np.zeros((3, 3))
    for _, _, m, _, c in items:
        r = (np.array(c) - cg) * 1e-3
        I += m * (r @ r * np.eye(3) - np.outer(r, r))
    return I


def kalman_rank(Mm, G, B, dead=()):
    Bu = np.delete(B, list(dead), axis=1)
    Mi = np.linalg.inv(Mm)
    A = np.block([[np.zeros((6, 6)), np.eye(6)], [-Mi @ G, np.zeros((6, 6))]])
    Bc = np.vstack([np.zeros((6, Bu.shape[1])), Mi @ Bu])
    # PBH 条件: A のすべての固有値 λ で rank [A − λI, Bc] = 12 なら可制御。
    # （[Bc, A Bc, …] を直接作ると A のべき乗で桁が離れ、階数の判定が数値的に不安定になる）
    n = A.shape[0]
    return min(int(np.linalg.matrix_rank(np.hstack([A - lam * np.eye(n), Bc]), tol=1e-8))
               for lam in np.linalg.eigvals(A))


def main():
    s = json.loads((OUT / "buoyancy_balance.json").read_text(encoding="utf-8"))["淡水"]
    cg, mass, bg = np.array(s["重心 mm"]), s["質量 kg"], s["BG mm"] * 1e-3
    T, R = P.THR_THRUST_KGF * P.G, P.THR_THRUST_KGF * P.G * P.THR_REV_RATIO
    B = matrix(cg)
    res = {}

    # ---- 1. 静的な可制御性
    S = np.diag([1, 1, 1, 1 / L_REF, 1 / L_REF, 1 / L_REF])
    sv = np.linalg.svd(S @ B, compute_uv=False)
    rank = int(np.linalg.matrix_rank(B))
    print(f"1. 静的な可制御性  B は 6×{B.shape[1]}, 階数 {rank}（6 なら全自由度を独立に制御できる）")
    print(f"   特異値（モーメントを L = {L_REF} m で力に換算）: {np.round(sv, 3)}")
    print(f"   条件数 {sv[0] / sv[-1]:.2f}（1 に近いほど、どの方向にも同じように力を出せる）  冗長度 {B.shape[1] - rank} 台")
    res["静的"] = {"階数": rank, "特異値": sv.tolist(), "条件数": sv[0] / sv[-1], "冗長度": B.shape[1] - rank}

    # ---- 2. 出せる力の範囲
    mx = axis_max_lp(B, T, R)
    print(f"\n2. 各軸で出せる最大値（ほかの 5 成分は 0。1 台 正転 {T:.1f} N / 逆転 {R:.1f} N）")
    for name, (a, b) in zip(AXES, mx):
        unit = "N" if name[0] == "F" else "N·m"
        print(f"   {name:<10}{a:>8.2f} / {b:>6.2f} {unit}")
    res["最大値"] = {n: {"+": a, "-": b} for n, (a, b) in zip(AXES, mx)}

    # ---- 3. 故障時
    restoring = mass * P.G * bg
    print(f"\n3. 故障時（復原モーメント W·g·BG = {restoring:.2f} N·m）")
    print(f"   {'停止':<10}{'階数':>4}  " + "  ".join(f"{a.split()[0]:>6}" for a in AXES) + "   （± の小さい方）")
    res["1台停止"] = {}
    for i, n in enumerate(NAMES):
        Bd = np.delete(B, i, axis=1)
        m1 = axis_max_lp(B, T, R, dead=(i,)).min(axis=1)
        rk = int(np.linalg.matrix_rank(Bd))
        print(f"   {n:<10}{rk:>4}  " + "  ".join(f"{v:>6.2f}" for v in m1))
        res["1台停止"][n] = {"階数": rk, "最大値": m1.tolist()}
    worst = np.min([r["最大値"] for r in res["1台停止"].values()], axis=0)
    print(f"   {'最悪':<10}{'':>4}  " + "  ".join(f"{v:>6.2f}" for v in worst))
    hold = min(worst[3], worst[5]) / restoring
    print(f"   → どの 1 台が止まっても 6 自由度を保つ。ロール・ピッチのモーメントは復原の {hold:.2f} 倍"
          f"（{'任意の姿勢を保持できる' if hold >= 1 else '保持できる傾きは %.0f° まで' % np.degrees(np.arcsin(hold))}）")
    pairs = list(itertools.combinations(range(len(NAMES)), 2))
    ok = [p for p in pairs if np.linalg.matrix_rank(np.delete(B, p, axis=1)) == 6]
    ng = [p for p in pairs if p not in ok]
    print(f"   2 台停止 {len(pairs)} 通り: 6 自由度を保つ {len(ok)} 通り、失う {len(ng)} 通り")
    lost = {}
    for p in ng:
        Bd = np.delete(B, p, axis=1)
        u, sv2, _ = np.linalg.svd(Bd)
        null = u[:, 5]                                    # 出せなくなる力・モーメントの向き
        null = null * np.array([1, 1, 1, L_REF, L_REF, L_REF])      # モーメント成分を力の単位にそろえて比べる
        null /= np.abs(null).max()
        key = "・".join(AXES[k].split()[1] for k in range(6) if abs(null[k]) > 0.3)
        lost.setdefault(key, []).append("+".join(NAMES[i] for i in p))
    for k, v in lost.items():
        print(f"      {k} の組合せを失う: {', '.join(v)}")
    res["2台停止"] = {"全組合せ": len(pairs), "6自由度を保つ": len(ok), "失う": lost}

    # ---- 4. 動的な可制御性
    items = load()
    I = inertia(items, cg)
    Mm = np.block([[mass * np.eye(3), np.zeros((3, 3))], [np.zeros((3, 3)), I]])
    G = np.zeros((6, 6))
    G[3, 3] = G[5, 5] = restoring                          # ロール・ピッチの復原。ヨーと並進には復原なし
    rk = kalman_rank(Mm, G, B)
    rk1 = min(kalman_rank(Mm, G, B, dead=(i,)) for i in range(len(NAMES)))
    print(f"\n4. 動的な可制御性（ホバリングまわりの線形モデル, 状態 12）")
    print(f"   PBH 条件の階数 {rk} / 12、1 台停止の最悪でも {rk1} / 12")
    res["動的"] = {"階数": rk, "1台停止の最小階数": rk1}

    # ---- 5. 姿勢の応答
    Id = np.diag(I)
    print(f"\n5. 姿勢の応答（慣性は点質量近似・付加質量なし。実機の加速度はこれより小さい）")
    print(f"   慣性モーメント  ロール {Id[0]:.3f}, ヨー {Id[1]:.3f}, ピッチ {Id[2]:.3f} kg·m2")
    res["応答"] = {}
    for name, i, k in (("ロール", 3, 0), ("ヨー", 4, 1), ("ピッチ", 5, 2)):
        acc = mx[i].min() / Id[k]
        t90 = 2 * np.sqrt(np.pi / 2 / acc)                 # 加速→減速で 90° 回す時間（抵抗なし）
        line = f"   {name}: 最大角加速度 {np.degrees(acc):.0f} °/s2, 90° 回すのに {t90:.2f} 秒以上"
        res["応答"][name] = {"角加速度 rad/s2": acc, "90度 s": t90}
        if i != 4:
            period = 2 * np.pi / np.sqrt(restoring / Id[k])
            line += f", 振り子の固有周期 {period:.2f} 秒"
            res["応答"][name]["固有周期 s"] = period
        print(line)
    (OUT / "controllability.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
