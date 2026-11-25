"""耐圧容器の事前計算: 筒の座屈・降伏、端蓋と観察窓の曲げ、Oリングのつぶし率・充填率。

    python analysis/hull_strength.py

モデル
  筒の座屈   Windenburg-Trilling の短円筒式（両端を端蓋が支える。支持間隔 = 筒長）
             Pcr = 2.42 E (t/D)^2.5 / [(1-nu^2)^0.75 (L/D - 0.45 (t/D)^0.5)]   D: 板厚中心径
  筒の降伏   薄肉円筒の周方向応力  sigma = p Ro / t
  端蓋・窓   周辺単純支持の円板に等分布圧  sigma = 3(3+nu)/8 p a^2 / t^2
             支持半径 a は、端蓋では筒の板厚中心、窓では端蓋の開口半径。
             端蓋ははめ込み部の環が補強になるが、板厚 12 の円板だけで受けるとして見積もる。
             後端蓋はペネトレータ穴、前端蓋は窓開口があるので応力集中係数 2 を掛ける（概算）。
  Oリング    つぶし率 E = (W - h) / W、充填率 n = (pi/4 W^2) / (G h)。h は溝の径方向深さ。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import rov_params as P

OUT = Path(__file__).parent / "out"


def tube():
    p = P.RHO_SEA * P.G * P.DEPTH_RATED * 1e-6          # MPa
    m = P.A6063
    D, t, L = P.HULL_OD - P.HULL_T, P.HULL_T, P.HULL_LEN
    pcr = 2.42 * m.E * (t / D) ** 2.5 / ((1 - m.nu ** 2) ** 0.75 * (L / D - 0.45 * math.sqrt(t / D)))
    py = m.sy * t / (P.HULL_OD / 2)
    return {"設計圧力 MPa": p, "座屈圧力 MPa": pcr, "降伏圧力 MPa": py,
            "座屈安全率": pcr / p, "降伏安全率": py / p}


def plate(mat, a, t, p, kt=1.0):
    s = 3 * (3 + mat.nu) / 8 * p * a ** 2 / t ** 2 * kt
    w = 3 * (1 - mat.nu) * (5 + mat.nu) * p * a ** 4 / (16 * mat.E * t ** 3)
    return {"応力 MPa": s, "安全率": mat.sy / s, "中心たわみ mm": w}


def oring(w, tol, h_nom, h_min, h_max, g, d_groove=None, d_ring=None):
    """h_nom / h_min / h_max: 溝の深さ（つぶし方向）の公称・最小・最大。"""
    def e(w_, h_):
        return (w_ - h_) / w_ * 100
    r = {"つぶし率 % 公称": e(w, h_nom),
         "つぶし率 % 最小": e(w - tol, h_max), "つぶし率 % 最大": e(w + tol, h_min),
         "充填率 % 公称": math.pi / 4 * w ** 2 / (g * h_nom) * 100,
         "充填率 % 最大": math.pi / 4 * (w + tol) ** 2 / (g * h_min) * 100}
    if d_groove:
        r["伸び率 %"] = (d_groove - d_ring) / d_ring * 100
    return r


def main():
    t = tube()
    p = t["設計圧力 MPa"]
    res = {
        "条件": {"設計水深 m": P.DEPTH_RATED, "海水密度 kg/m3": P.RHO_SEA},
        "耐圧筒 A6063-T5 150x5": t,
        "後端蓋 A6061-T6 t12 (穴あり kt=2)": plate(P.A6061, (P.HULL_OD - P.HULL_T) / 2, P.CAP_PLATE_T, p, 2.0),
        "前端蓋 A6061-T6 t12 (開口あり kt=2)": plate(P.A6061, (P.HULL_OD - P.HULL_T) / 2, P.CAP_PLATE_T, p, 2.0),
        "観察窓 アクリル t15 (開口 80)": plate(P.ACRYL, P.WINDOW_APERTURE / 2, P.WINDOW_T, p),
        # 円筒面: 径方向深さは (D - d)/2。公差 D +0.10/0, d 0/-0.10
        "Oリング G-135 円筒面固定": oring(P.ORING_W, P.ORING_W_TOL,
                                   (P.GROOVE_BORE - P.GROOVE_D) / 2,
                                   (P.GROOVE_BORE - P.GROOVE_D) / 2,
                                   (P.GROOVE_BORE + 0.10 - (P.GROOVE_D - 0.10)) / 2,
                                   P.GROOVE_W, P.GROOVE_D, P.GSEAL_ID),
        # 平面: 溝深さ H ±0.05
        "Oリング G-85 平面固定": oring(P.ORING_W, P.ORING_W_TOL, P.FACE_GROOVE_H, P.FACE_GROOVE_H - 0.05,
                                 P.FACE_GROOVE_H + 0.05, P.FACE_GROOVE_W),
        # 端蓋は Oリングの摩擦とベントからの負圧で保持する（通しボルトなし）
        "端蓋の保持": {"水圧による押付け N（設計水深）": p * math.pi / 4 * P.SEAL_BORE ** 2,
                   "負圧 0.02 MPa での保持力 N": 0.02 * math.pi / 4 * P.SEAL_BORE ** 2,
                   "内圧が 0.02 MPa 高いときの押出し力 N": 0.02 * math.pi / 4 * P.SEAL_BORE ** 2},
        "浮力材": {"圧縮強さ MPa": P.FOAM_STRENGTH, "安全率": P.FOAM_STRENGTH / p},
    }
    for k, v in res.items():
        print(f"■ {k}")
        for kk, vv in v.items():
            print(f"    {kk:<32} {vv:10.3f}")
    ok = t["座屈安全率"] >= P.SAFETY_BUCKLING and t["降伏安全率"] >= P.SAFETY_YIELD
    print("判定: 筒は", "基準内" if ok else "基準外")
    OUT.mkdir(exist_ok=True)
    (OUT / "hull_strength.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
