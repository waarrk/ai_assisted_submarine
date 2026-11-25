"""水中ドローン UWD-01 を SOLIDWORKS 上に組み立てる。

    python src/uwd01/build.py            全体を作り直す（変更のない部品は保存済みを使い回す）
    python src/uwd01/build.py --no-cache 保存済みを使わず、全部品を最初から作り直す
    python src/uwd01/build.py --no-cache --show   画面更新を止めずに作る（作る過程を見せる・録画する用。遅い）
    python src/uwd01/build.py 前端蓋      部品 1 点だけ試作する（保存先は同じ）

SOLIDWORKS の操作は汎用ライブラリ swkit に任せ、このファイルには UWD-01 の形と配置だけを書く。

手順（アセンブリから設計する）
  1. 空のトップアセンブリとユニット別サブアセンブリを先に作って保存する。
  2. トップアセンブリにレイアウトスケッチ（側面・平面）を描く。
  3. 各部品を作り、所属するサブアセンブリへ入れて、基準平面とレイアウトスケッチに合致で拘束する。
     位置決めに要る基準平面はアセンブリ側に定義する（オフセットは変数に接続）。
  4. サブアセンブリをトップアセンブリへ入れて合致で拘束する。
  5. 相手部品と共締めする穴を、トップアセンブリの穴フィーチャで開けて加工部品へ反映する。
  6. 拘束状態・干渉・質量・画像・STEP を出力する。
この手順と、速く終わらせる段取り（部品の使い回し、穴に関わるユニットを先に載せる）は swkit.Project.build が受け持つ。

寸法はすべて analysis/rov_params.py から読み、部品・アセンブリ内では同名のグローバル変数と関係式になる。
座標は X = 前, Y = 上, Z = 右舷, 原点 = 耐圧筒の中心。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis"))

import rov_params as P  # noqa: E402
from swkit import (BLACK, BLUE, FLIP_X, ORANGE, SW, X_DOWN, X_TO_NEG_Z, X_TO_Y, X_TO_Z, X_TO_Z_Y_TO_X, YELLOW,
                   Project, cached_part)  # noqa: E402

CAD = ROOT / "cad"
STD = CAD / "00_既製品"
TOP = CAD / "01_水中ドローン"
D_HULL, D_FRAME = TOP / "01_耐圧容器", TOP / "02_フレーム"
D_PROP, D_BUOY, D_MANIP = TOP / "03_推進部", TOP / "04_浮力調整部", TOP / "05_マニピュレータ"
D_FAST = TOP / "06_締結部品"
D_INT, D_HARN = TOP / "07_内部機器", TOP / "08_ハーネス"
OUT = ROOT / "analysis" / "out"

VENDOR = ROOT / "cad_source" / "vendor"        # メーカー配布の 3D データ（出どころは cad_source/README.md）
CUT_2D = "ウォータージェットで板から輪郭を切り出す。板厚は素材のまま"

FACE = "HULL_LEN / 2 + CAP_PLATE_T"                  # 端蓋外面の位置
G1 = "HULL_LEN / 2 - GROOVE_POS - GROOVE_W / 2"      # Oリング溝 1 本目の中心
G2 = "HULL_LEN / 2 - GROOVE_POS - GROOVE_PITCH - GROOVE_W / 2"
# アセンブリに定義する基準平面の名前（位置の式 -> 名前）
LABELS = {
    "HULL_LEN / 2": "前端蓋 当たり面", "-HULL_LEN / 2": "後端蓋 当たり面",
    FACE: "前端蓋 外面", f"-({FACE})": "後端蓋 外面",
    f"{FACE} + WINDOW_T + RING_T / 2": "窓押え環 板厚中心",
    G1: "Oリング溝 前1", G2: "Oリング溝 前2", f"-({G1})": "Oリング溝 後1", f"-({G2})": "Oリング溝 後2",
    f"{FACE} - FACE_GROOVE_H + ORING_W / 2": "窓Oリング 中心面",
    "PEN_PCD / 2": "ペネトレータ PCD 上",
    "PEN_PCD2 / 2": "ペネトレータ 中央 PCD 上",
    "MANIP_X": "サーボ軸 前後位置", "ARM_Y": "アーム板 板厚中心", "SERVO_AXIS_Y": "サーボ軸 高さ",
    "SERVO_ZC": "サーボ本体 軸方向中心", "JAW_Z": "可動爪 板厚中心(右)", "-JAW_Z": "可動爪 板厚中心(左)",
    "MANIP_X + JAW_BAR_X": "つなぎ棒 前後位置", "SERVO_AXIS_Y + JAW_BAR_Y": "つなぎ棒 高さ",
    "TRAY_X0 + TRAY_T": "トレイ タブ内面", "TRAY_Y + TRAY_T": "トレイ 上面", "TRAY_TAP_Y": "トレイ支柱 高さ",
    "TRAY_TAP_Z": "トレイ支柱 右", "-TRAY_TAP_Z": "トレイ支柱 左",
    "BPB_X0": "BPB 後端", "BPB_Y": "BPB 板厚中心", "BPB_Y + PCB_T / 2": "BPB 上面", "CARD_Y": "差し込み基板 下端",
    "TIE_YC": "ハーネス固定 束の中心高さ", "TIE_X1": "ハーネス固定 前1", "-TIE_X1": "ハーネス固定 後1",
    "TIE_X2": "ハーネス固定 前2", "-TIE_X2": "ハーネス固定 後2",
    "TIE_DX1": "サーボケーブル固定 前", "TIE_DX2": "サーボケーブル固定 後",
    "BALLAST_XC": "バラスト 前後中心", "BATT_X": "バッテリ 中心", "TRAY_Y + TRAY_T + BATT_H / 2": "バッテリ 高さ中心",
    "SIDE_Z": "側板 板厚中心(右)", "-SIDE_Z": "側板 板厚中心(左)",
    "CRADLE_X": "筒受け 板厚中心(前)", "-CRADLE_X": "筒受け 板厚中心(後)",
    "DECK_Y": "底板 板厚中心", "HORZ_Y": "水平スラスタ 推力軸の高さ",
    "VERT_X": "垂直スラスタ 前", "-VERT_X": "垂直スラスタ 後", "VERT_Z": "垂直スラスタ 右", "-VERT_Z": "垂直スラスタ 左",
    "FOAM_YC": "浮力材 厚さ中心", "FOAM_XC": "浮力材 前後中心", "BALLAST_Z": "バラスト 右", "-BALLAST_Z": "バラスト 左",
    "ROD_X_TOP": "横通しボルト(上) 前", "-ROD_X_TOP": "横通しボルト(上) 後", "ROD_Y_TOP": "横通しボルト(上) 高さ",
    "ROD_X_LOW": "横通しボルト(下) 前", "-ROD_X_LOW": "横通しボルト(下) 後", "ROD_Y_LOW": "横通しボルト(下) 高さ",
    "NUT_Z": "ナット 右", "-NUT_Z": "ナット 左",
}



class Builder(Project):
    def __init__(self, use_cache=True):
        super().__init__(P, CAD, LABELS, use_cache=use_cache)

    # ------------------------------------------------------------ レイアウト（トップアセンブリのスケッチ）
    def layout(self, top):
        """トップアセンブリのレイアウトスケッチ。配置の骨格で、寸法は部品と同じ変数につながる。"""
        s = top.sketch("front")                             # 側面: 耐圧筒・側板の外形・底板・スラスタ
        s.rect("-HULL_LEN / 2", "HULL_LEN / 2", "-HULL_OD / 2", "HULL_OD / 2")
        s.rect("-SIDE_X", "SIDE_X", "SIDE_BOTTOM", "SIDE_TOP")
        s.rect("-DECK_X", "DECK_X", "DECK_BOTTOM", "DECK_TOP")
        for sx in ("", "-"):
            s.circle(f"{sx}HORZ_X", "HORZ_Y", "THR_DUCT_OD")
        top.keep_sketch("側面レイアウト")
        s = top.sketch("top")                               # 平面: 耐圧筒・側板・垂直スラスタ位置
        s.rect("-HULL_LEN / 2", "HULL_LEN / 2", "-HULL_OD / 2", "HULL_OD / 2")
        s.rect("-SIDE_X", "SIDE_X", "-OUTER_HALF_W", "OUTER_HALF_W")
        for sz in ("", "-"):
            for sx in ("", "-"):
                s.circle(f"{sx}VERT_X", f"{sz}VERT_Z", "THR_DUCT_OD")
        top.keep_sketch("平面レイアウト")

    # ------------------------------------------------------------ 01 耐圧容器
    @cached_part
    def tube(self):
        """基準: 中心軸と長さの中央。両端は同じ加工なので前端を作って中央面でミラーする。"""
        p = self.new_part()
        s = p.sketch("front", revolve=True)
        s.centerline("HULL_LEN / 2 + 10")
        s.rect("-HULL_LEN / 2", "HULL_LEN / 2", "HULL_ID / 2", "HULL_OD / 2")
        p.revolve("素材 パイプ切断・端面仕上げ")
        s = p.sketch("front", revolve=True)
        s.centerline("HULL_LEN / 2 + 10")
        end = "HULL_LEN / 2"
        s.poly([(f"{end} - SEAL_LEN", "HULL_ID / 2"), (f"{end} - SEAL_LEN", "SEAL_BORE / 2"),
                (f"{end} - LEAD_AX", "SEAL_BORE / 2"), (end, "SEAL_BORE / 2 + LEAD_RAD"), (end, "HULL_ID / 2")])
        bore = p.revolve("シール面 内径仕上げ(前)", cut=True)
        p.mirror([bore], "right", "シール面 内径仕上げ(後)")
        return self.finish(p, D_HULL / "耐圧筒.SLDPRT", P.A6063,
                           加工方法="丸パイプ φ150×t5 を切断、旋盤で両端面と両端の内径 φ142 を仕上げ",
                           加工基準="中心軸、端面（シール面の深さは各端面から）",
                           備考="シール面 φ142 H9、Ra1.6。導入テーパ約 20°。生爪で全周を保持して加工する")

    @cached_part
    def cap(self, front):
        """基準A: 筒端に当たるつばの面（原点）。基準B: 中心軸。溝位置は基準A から測る。"""
        p = self.new_part()
        s = p.sketch("front", revolve=True)
        s.centerline("SPIGOT_LEN + 10")
        inner = "WINDOW_APERTURE / 2" if front else 0
        s.poly([("-CAP_PLATE_T", inner), ("-CAP_PLATE_T", "FLANGE_OD / 2"), (0, "FLANGE_OD / 2"),
                (0, "SPIGOT_OD / 2"), ("SPIGOT_LEN", "SPIGOT_OD / 2"), ("SPIGOT_LEN", "SPIGOT_ID / 2"),
                (0, "SPIGOT_ID / 2"), (0, inner)])
        p.revolve("外形旋削")
        p.chamfer([("SPIGOT_LEN", "SPIGOT_OD / 2", 0)], "SPIGOT_C", "はめ込み先端 面取り")
        s = p.sketch("front", revolve=True)
        s.centerline("SPIGOT_LEN + 10")
        s.rect("GROOVE_POS", "GROOVE_POS + GROOVE_W", "GROOVE_D / 2", "SPIGOT_OD / 2")
        g = p.revolve("Oリング溝入れ G-135", cut=True)
        p.linear([g], "GROOVE_PITCH", "GROOVE_POS + GROOVE_PITCH + GROOVE_W / 2", "Oリング溝 2 本目")
        if front:
            s = p.sketch("front", revolve=True)
            s.centerline("SPIGOT_LEN + 10")
            s.rect("-CAP_PLATE_T", "-CAP_PLATE_T + FACE_GROOVE_H", "FACE_GROOVE_ID / 2", "FACE_GROOVE_ID / 2 + FACE_GROOVE_W")
            p.revolve("窓 Oリング溝入れ G-85", cut=True)
            h = p.hole("right", "-CAP_PLATE_T", [(0, "RING_PCD / 2")], "M4", "M4 めねじ",
                       from_pos=False, depth="RING_TAP_DEPTH", thread=8)
            p.circular([h], P.RING_N, "M4 めねじ 等配")
        else:
            h = p.hole("right", "-CAP_PLATE_T", [(0, "PEN_PCD / 2")], "M10", "ペネトレータ M10", from_pos=False,
                       depth="CAP_PLATE_T + 1", thread="CAP_PLATE_T")
            p.circular([h], P.PEN_N, "ペネトレータ M10 等配")
            h = p.hole("right", "-CAP_PLATE_T", [(0, "PEN_PCD2 / 2")], "M10", "ペネトレータ M10 中央", from_pos=False,
                       depth="CAP_PLATE_T + 1", thread="CAP_PLATE_T")
            p.circular([h], P.PEN_N2, "ペネトレータ M10 中央 等配")
            # 内部トレイの固定。耐圧容器の内側から止まり穴であけ、外へ貫通させない
            h = p.hole("right", 0, [("TRAY_TAP_Z", "TRAY_TAP_Y")], "M4", "トレイ支柱 M4（内側）", depth="TRAY_TAP_DEPTH", thread=6)
            p.mirror([h], "front", "トレイ支柱 M4（内側・対称）")
        name = "前端蓋" if front else "後端蓋"
        return self.finish(p, D_HULL / f"{name}.SLDPRT", P.A6061,
                           加工方法="丸棒 φ160 から旋盤 2 工程（外面側 → はめ込み側）、外面から穴あけ。前後の端蓋は旋削形状が共通",
                           加工基準="基準A: つばの当たり面、基準B: 中心軸",
                           備考="はめ込み径 φ142 f8、Oリング溝 G-135×2" + ("、窓用 G-85 平面溝" if front else "、ペネトレータ用 M10 タップ×11"))

    @cached_part
    def window(self):
        p = self.new_part()
        s = p.sketch("front", revolve=True)
        s.centerline("WINDOW_T + 10")
        s.rect(0, "WINDOW_T", 0, "WINDOW_OD / 2")
        p.revolve("円板 切り出し")
        return self.finish(p, D_HULL / "観察窓.SLDPRT", P.ACRYL, BLUE, 0.6,
                           加工方法="キャスト板 t15 から円形に切り出し、外周を仕上げ",
                           加工基準="前端蓋に当たる面、中心軸", 備考="シール面に傷を付けない")

    @cached_part
    def ring(self):
        p = self.new_part()
        s = p.sketch("right")
        s.circle(0, 0, "RING_OD")
        s.circle(0, 0, "RING_ID")
        p.extrude_mid("RING_T", "板 外形切り出し")
        h = p.hole("right", "RING_T / 2", [(0, "RING_PCD / 2")], "Ø4.5", "M4 通し穴")
        p.circular([h], P.RING_N, "M4 通し穴 等配")
        return self.finish(p, D_HULL / "窓押え環.SLDPRT", P.HDPE, BLACK, 加工方法=CUT_2D, 加工基準="中心",
                           備考="フレームと同じ板から切り出す。M4×6 で窓を直接押さえ、ねじが窓の外周に接して芯を出す")

    @cached_part
    def oring(self, code, center_d):
        p = self.new_part()
        s = p.sketch("front", revolve=True)
        s.centerline(10)
        s.circle(0, f"({center_d}) / 2", "ORING_W")
        p.revolve("Oリング")
        return self.finish(p, STD / f"{code}.SLDPRT", P.NBR, BLACK, メーカー="森清化工（ミスミ取扱）",
                           備考=f"JIS B 2401 {code[3:]} NBR 1種A。装着状態の径で作図")

    @cached_part
    def penetrator(self):
        """WetLink ペネトレータ M10。配布 CAD（ねじ軸 = Y、シール面 y = 20）を、軸 = X・シール面 = 原点・外側 = −X にそろえる。"""
        return self.vendor(VENDOR / "WLP-M10-7.5MM-PUBLIC.SLDPRT", STD / "WetLink_WLP-M10-7.5MM.SLDPRT",
                           ((0, -1, 0), (1, 0, 0), (0, 0, 1)), (0, 20.0, 0), P.A5052, P.PEN_MASS,
                           メーカー="Blue Robotics", 備考="WetLink ペネトレータ M10（ケーブル Ø7 用 7.5mm-HC）。定格 1000 m。端蓋の M10 タップにねじ込む")

    def hull_asm(self, asm):
        u = "耐圧容器"
        face = FACE
        self.place(asm, self.tube(), unit=u)
        self.place(asm, self.cap(False), t=("-HULL_LEN / 2", 0, 0), unit=u)
        self.place(asm, self.cap(True), FLIP_X, ("HULL_LEN / 2", 0, 0), unit=u)
        self.place(asm, self.window(), t=(face, 0, 0), unit=u)
        self.place(asm, self.ring(), t=(f"{face} + WINDOW_T + RING_T / 2", 0, 0), unit=u)
        g115 = self.oring("1A-G135", "GROOVE_D + ORING_W")
        for x in (G1, G2):
            self.place(asm, g115, t=(x, 0, 0), unit=u)
            self.place(asm, g115, t=(f"-({x})", 0, 0), unit=u)
        g85 = self.oring("1A-G85", "FACE_GROOVE_ID + ORING_W")
        self.place(asm, g85, t=(f"{face} - FACE_GROOVE_H + ORING_W / 2", 0, 0), unit=u)
        pen = self.penetrator()
        self.ring_of(asm, pen, f"-({face})", "PEN_PCD", P.PEN_N, u, "ペネトレータ 等配")
        self.ring_of(asm, pen, f"-({face})", "PEN_PCD2", P.PEN_N2, u, "ペネトレータ 中央 等配")

    # ------------------------------------------------------------ 02 フレーム
    @cached_part
    def side_plate(self):
        """基準: 筒の中心線（原点）と板厚中心。前半分の窓・角穴を作り、右側面（YZ）でミラーする。"""
        p = self.new_part()
        s = p.sketch("front")
        s.rect("-SIDE_X", "SIDE_X", "SIDE_BOTTOM", "SIDE_TOP")
        p.extrude_mid("PLATE_T", "板 外形切り出し")

        def window(u0, u1, v0, v1, r, name, rname):
            s = p.sketch("front")
            s.rect(u0, u1, v0, v1)
            c = p.cut_through(name)
            f = p.fillet([(u, v, 0) for u in (u0, u1) for v in (v0, v1)], r, rname)
            return [c, f]

        jet = window("JET_X0", "JET_X1", "JET_Y0", "JET_Y1", "WINDOW_R", "噴流窓(前)", "噴流窓 内角R")
        p.mirror(jet, "right", "噴流窓(後)")
        window("-CW_X", "CW_X", "-CW_Y", "CW_Y", "WINDOW_R", "中央窓", "中央窓 内角R")
        h, w = "PLATE_T / 2 + SLOT_CL_T", "TAB_W / 2 + SLOT_CL"
        slot = window(f"CRADLE_X - ({h})", f"CRADLE_X + ({h})", f"-TAB_Y - ({w})", f"-TAB_Y + ({w})",
                      "SLOT_R", "角穴 筒受け(前)", "角穴 筒受け 内角R")
        up = p.mirror(slot, "top", "角穴 筒押え(前)")
        p.mirror(slot + [up], "right", "角穴 筒受け・筒押え(後)")
        dw = "DECK_TAB_W / 2 + SLOT_CL"
        window(f"-({dw})", dw, f"DECK_Y - ({h})", f"DECK_Y + ({h})", "SLOT_R", "角穴 底板(中央)", "角穴 底板(中央) 内角R")
        dslot = window(f"DECK_TAB_X - ({dw})", f"DECK_TAB_X + ({dw})", f"DECK_Y - ({h})", f"DECK_Y + ({h})",
                       "SLOT_R", "角穴 底板(前)", "角穴 底板(前) 内角R")
        p.mirror(dslot, "right", "角穴 底板(後)")
        window("-HANDLE_X", "HANDLE_X", "HANDLE_Y0", "HANDLE_Y1", "WINDOW_R", "持ち手穴", "持ち手穴 内角R")
        p.hole("front", "PLATE_T / 2", [(x, y) for x in ("TIE_X1", "-TIE_X1", "TIE_X2", "-TIE_X2") for y in ("TIE_Y1", "TIE_Y2")],
               "Ø5.5", "結束バンド穴（ハーネス固定）")
        p.fillet([(u, v, 0) for u in ("-SIDE_X", "SIDE_X") for v in ("SIDE_BOTTOM", "SIDE_TOP")], "SIDE_R", "外周 角R")
        return self.finish(p, D_FRAME / "側板.SLDPRT", P.HDPE, BLACK, 加工方法=CUT_2D,
                           加工基準="筒の中心線（前後・上下）", 備考="左右共通。ボルト穴・スラスタ取付穴はアセンブリの穴フィーチャから反映")

    @cached_part
    def saddle(self, upper):
        """筒受け（下）と筒押え（上）。基準: 合わせ面（筒の中心高さ）と左右中心。ほぞは右を作って左へミラー。"""
        p = self.new_part()
        edge = "CLAMP_TOP" if upper else "DECK_TOP"
        s = p.sketch("right")
        s.poly([("-CRADLE_BORE / 2", 0), ("-INNER_HALF_W", 0), ("-INNER_HALF_W", edge),
                ("INNER_HALF_W", edge), ("INNER_HALF_W", 0), ("CRADLE_BORE / 2", 0)], close=False, free=(0, 5))
        s.half_circle("CRADLE_BORE / 2", upper)
        p.extrude_mid("PLATE_T", "板 外形切り出し")
        sg = "" if upper else "-"
        v0, v1 = f"{sg}TAB_Y - TAB_W / 2", f"{sg}TAB_Y + TAB_W / 2"
        s = p.sketch("right")
        s.rect("INNER_HALF_W", "INNER_HALF_W + PLATE_T", v0, v1)
        tab = p.extrude_mid("PLATE_T", "ほぞ(右)")
        ch = p.chamfer([(0, v0, "INNER_HALF_W + PLATE_T"), (0, v1, "INNER_HALF_W + PLATE_T")], "TAB_C", "ほぞ(右) 先端面取り")
        p.mirror([tab, ch], "front", "ほぞ(左)")
        if not upper:                                    # 底板の上を通るアーム板とケーブルのくぐり穴
            s = p.sketch("right")
            s.rect("-NOTCH_W", "NOTCH_W", "DECK_TOP", "DECK_TOP + NOTCH_H")
            p.cut_through("くぐり穴")
            p.fillet([(0, "DECK_TOP + NOTCH_H", z) for z in ("-NOTCH_W", "NOTCH_W")], "CUT_R", "くぐり穴 内角R")
        name = "筒押え" if upper else "筒受け"
        return self.finish(p, D_FRAME / f"{name}.SLDPRT", P.HDPE, BLACK, 加工方法=CUT_2D,
                           加工基準="合わせ面（筒の中心高さ）、左右中心", 備考="受け面にゴムシート t0.5 を貼る")

    @cached_part
    def deck(self):
        """底板。基準: 前後・左右の中心線。ほぞは右舷前半を作ってミラーする。"""
        p = self.new_part()
        s = p.sketch("top")
        s.rect("-DECK_X", "DECK_X", "-INNER_HALF_W", "INNER_HALF_W")
        p.extrude_mid("PLATE_T", "板 外形切り出し")

        def tab(u0, u1, name):
            s = p.sketch("top")
            s.rect(u0, u1, "INNER_HALF_W", "INNER_HALF_W + PLATE_T")
            t = p.extrude_mid("PLATE_T", name)
            c = p.chamfer([(u0, 0, "INNER_HALF_W + PLATE_T"), (u1, 0, "INNER_HALF_W + PLATE_T")], "TAB_C", f"{name} 先端面取り")
            return [t, c]

        mid = tab("-DECK_TAB_W / 2", "DECK_TAB_W / 2", "ほぞ(右・中央)")
        fwd = tab("DECK_TAB_X - DECK_TAB_W / 2", "DECK_TAB_X + DECK_TAB_W / 2", "ほぞ(右・前)")
        aft = p.mirror(fwd, "right", "ほぞ(右・後)")
        p.mirror(mid + fwd + [aft], "front", "ほぞ(左)")
        p.hole("top", "PLATE_T / 2", [(x, z) for x in ("TIE_DX1", "TIE_DX2") for z in ("TIE_DZ", "-TIE_DZ")],
               "Ø5.5", "結束バンド穴（サーボケーブル固定）")
        return self.finish(p, D_FRAME / "底板.SLDPRT", P.HDPE, BLACK, 加工方法=CUT_2D,
                           加工基準="前後・左右の中心線", 備考="下面に水平スラスタ、上面にバラスト。穴はアセンブリの穴フィーチャから反映")

    def frame_asm(self, asm):
        u = "フレーム"
        side = self.side_plate()
        for z in ("SIDE_Z", "-SIDE_Z"):
            self.place(asm, side, t=(0, 0, z), unit=u)
        lower, upper = self.saddle(False), self.saddle(True)
        for x in ("CRADLE_X", "-CRADLE_X"):
            self.place(asm, lower, t=(x, 0, 0), unit=u)
            self.place(asm, upper, t=(x, 0, 0), unit=u)
        self.place(asm, self.deck(), t=(0, "DECK_Y", 0), unit=u)

    # ------------------------------------------------------------ 03 推進部
    @cached_part
    def thruster(self):
        """ApisQueen U2 Mini。配布 IGES（推力軸 = Z、取付面が −Y 側）を、推力軸 = X・取付面 −Y・原点 = ダクトと取付座の中央にそろえる。"""
        return self.vendor(VENDOR / "U2_Mini.igs", STD / "ApisQueen_U2-Mini.SLDPRT",
                           ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), (177.185, -41.69 + P.THR_FOOT_H, -18.28), P.THRUSTER_MAT, P.THR_MASS,
                           axis=True, メーカー="ApisQueen", 備考="メーカー配布の 3D データ。取付ねじ 4-M3 の軸方向ピッチは現物で確かめる")

    def prop_asm(self, asm):
        """垂直スラスタは基準平面、45° の水平スラスタはレイアウトスケッチの推力軸に拘束する。"""
        u = "推進部"
        thr = self.thruster()
        path = self.parts[thr][0]
        s = asm.sketch("top", asm.ref_plane(1, "HORZ_Y"))    # 水平スラスタの軸の高さの面に描く
        guide = {}
        for name, pos, d in P.THRUSTERS:
            if d[1]:
                continue
            sx, sz = ("" if pos[0] > 0 else "-"), ("" if pos[2] > 0 else "-")
            a, b = ("+", "-") if d[2] > 0 else ("-", "+")     # 軸の前端が向く側
            ends = [(f"{sx}HORZ_X + AX_K", f"{sz}HORZ_Z {a} AX_K"), (f"{sx}HORZ_X - AX_K", f"{sz}HORZ_Z {b} AX_K")]
            ln = s.poly(ends, close=False)[0]
            guide[name] = (ln, s.point(f"{sx}HORZ_X", f"{sz}HORZ_Z"))
        asm.keep_sketch("水平スラスタ 推力軸レイアウト")
        for name, pos, d in P.THRUSTERS:
            if d[1]:                                     # 垂直: 推力軸を上へ、取付面を側板へ向ける
                sg = 1 if pos[2] > 0 else -1
                rows = ((0, 1, 0), (0, 0, sg), (sg, 0, 0))
                t = (("" if pos[0] > 0 else "-") + "VERT_X", "VERT_Y", ("" if sg > 0 else "-") + "VERT_Z")
                self.place(asm, thr, rows, t, unit=u)
            else:                                        # 水平: 取付面を上（底板下面）へ向ける
                rows = (d, (0, -1, 0), (d[2], 0, -d[0]))
                comp = asm.insert(path, rows, pos)
                ln, pt = guide[name]
                asm.mate(asm.COINCIDENT, (comp, "axis"), ln)         # 推力軸をレイアウトの線に
                asm.mate(asm.COINCIDENT, (comp, "right"), pt)        # 軸方向の位置を中心点に
                asm.mate(asm.PARALLEL, (comp, "top"), asm.planes()["top"])   # 取付面を水平に
                self.record(thr, rows, pos, u, comp)

    # ------------------------------------------------------------ 04 浮力調整部
    def buoy_asm(self, asm):
        u = "浮力調整部"
        p = self.new_part()
        s = p.sketch("top")
        s.rect("-FOAM_X", "FOAM_X", "-INNER_HALF_W", "INNER_HALF_W")
        p.extrude_mid("FOAM_T", "ブロック 切り出し")
        foam = self.finish(p, D_BUOY / "浮力材.SLDPRT", P.FOAM, YELLOW, 加工方法="フォーム板からのこ・ルータで切り出し、表面を樹脂で封止",
                           加工基準="前後・左右の中心、下面", 備考="厚さは浮力釣合いで決める。横通しボルト穴はアセンブリから反映")
        self.place(asm, foam, t=("FOAM_XC", "FOAM_YC", 0), unit=u)

        p = self.new_part()
        s = p.sketch("top")
        s.rect("-BALLAST_L / 2", "BALLAST_L / 2", "-BALLAST_W / 2", "BALLAST_W / 2")
        p.extrude_mid("BALLAST_T", "フラットバー 切断")
        bal = self.finish(p, D_BUOY / "バラスト.SLDPRT", P.SUS304, 加工方法="SUS304 フラットバー 6×50 を長さ 200 に切断",
                          加工基準="中心", 備考="枚数と前後位置で釣合いを取る。穴はアセンブリから反映")
        for z in ("BALLAST_Z", "-BALLAST_Z"):
            for i in range(P.BALLAST_N):
                y = f"DECK_TOP + {i + 0.5} * BALLAST_T"
                asm.labels[y] = f"バラスト {i + 1} 枚目 厚さ中心"
                self.place(asm, bal, t=("BALLAST_XC", y, z), unit=u)

    # ------------------------------------------------------------ 05 マニピュレータ
    def manip_asm(self, asm):
        """1 自由度グリッパ。各部品の原点はサーボ軸（爪の回転中心）に置く。"""
        u = "マニピュレータ"
        p = self.new_part()                              # アーム板。先端が固定の下あご。基準: サーボ軸の真下と左右中心
        s = p.sketch("top")
        s.poly([("-ARM_BACK", "-ARM_STEM_W"), ("-ARM_NECK", "-ARM_STEM_W"), ("-ARM_NECK", "-ARM_HALF_W"), ("ARM_FRONT", "-ARM_HALF_W"),
                ("ARM_FRONT", "ARM_HALF_W"), ("-ARM_NECK", "ARM_HALF_W"), ("-ARM_NECK", "ARM_STEM_W"), ("-ARM_BACK", "ARM_STEM_W")])
        p.extrude_mid("PLATE_T", "板 外形切り出し")
        p.fillet([("-ARM_BACK", 0, "-ARM_STEM_W"), ("-ARM_BACK", 0, "ARM_STEM_W"), ("ARM_FRONT", 0, "-ARM_HALF_W"), ("ARM_FRONT", 0, "ARM_HALF_W")],
                 "ARM_R", "外周 角R")
        arm = self.finish(p, D_MANIP / "アーム板.SLDPRT", P.HDPE, BLACK, 加工方法=CUT_2D,
                          加工基準="サーボ軸の真下（爪の回転中心）、左右中心",
                          備考="底板上面に M5×4 で固定。上にサーボを載せ、下から M3×6 で止める。穴はアセンブリの穴フィーチャから反映")

        p = self.new_part()                              # 可動爪（左右共通）。基準: 回転中心
        s = p.sketch("front")
        pts = [("-JAW_HUB", "-JAW_HUB"), ("JAW_LEN", "-JAW_HUB"), ("JAW_LEN", "-JAW_TIP"), ("JAW_HUB", "JAW_HUB"), ("-JAW_HUB", "JAW_HUB")]
        s.poly(pts)
        p.extrude_mid("PLATE_T", "板 外形切り出し")
        p.fillet([(x, y, 0) for x, y in pts], "JAW_R", "角R")
        jaw = self.finish(p, D_MANIP / "可動爪.SLDPRT", P.HDPE, BLACK, 加工方法=CUT_2D, 加工基準="回転中心（サーボ軸）",
                          備考="左右共通。サーボの出力円板と従動軸に 4-M4 で固定。穴はアセンブリの穴フィーチャから反映")

        # サーボの外形モデル（寸法図から作図）。出力軸 = X（+X が出力円板）、原点 = 軸上で本体の軸方向中心、+Z = ケーブル側
        p = self.new_part()
        s = p.sketch("right")
        s.rect("-SERVO_AX_BOTTOM", "SERVO_AX_TOP", "-SERVO_W / 2", "SERVO_W / 2")
        p.extrude_mid("SERVO_BODY_L", "本体")
        s = p.sketch("front", revolve=True)
        s.centerline("SERVO_BODY_L / 2 + SERVO_DISC_T + 5")
        s.rect("SERVO_BODY_L / 2", "SERVO_BODY_L / 2 + SERVO_DISC_T", 0, "SERVO_DISC_D / 2")
        p.revolve("出力円板")
        s = p.sketch("front", revolve=True)
        s.centerline("SERVO_BODY_L / 2 + SERVO_DISC_T + 5")
        s.rect("-SERVO_BODY_L / 2 - SERVO_IDLER_T", "-SERVO_BODY_L / 2", 0, "SERVO_DISC_D / 2")
        p.revolve("従動軸")
        # ケーブルグランド（上面）。軸を通る面から上下対称に押し出す。下側は本体の中に隠れる
        s = p.sketch("front")
        s.rect("SERVO_GLAND_POS - SERVO_GLAND_D / 2", "SERVO_GLAND_POS + SERVO_GLAND_D / 2", "-SERVO_GLAND_D / 2", "SERVO_GLAND_D / 2")
        p.extrude_mid("SERVO_GLAND_SPAN", "ケーブルグランド")
        p.axis_x()
        servo = self.finish(p, STD / "ROVMaker_RM-SV-40.SLDPRT", P.THRUSTER_MAT, ORANGE, mass=P.SERVO_MASS,
                            メーカー="ROVMaker", 備考="外形モデル。使用水深 300 m。寸法は販売ページの寸法図。グランドの太さは目測")

        bar = self.existing(STD / "MISUMI_FABS5-125.SLDPRT", rho=P.SUS304.rho)     # 全ねじ。原点 = 片端、+X へ伸びる

        self.place(asm, arm, t=("MANIP_X", "ARM_Y", 0), unit=u)
        self.place(asm, servo, X_TO_Z_Y_TO_X, ("MANIP_X", "SERVO_AXIS_Y", "SERVO_ZC"), unit=u)
        for z in ("JAW_Z", "-JAW_Z"):
            self.place(asm, jaw, t=("MANIP_X", "SERVO_AXIS_Y", z), unit=u)
        self.place(asm, bar, X_TO_Z, ("MANIP_X + JAW_BAR_X", "SERVO_AXIS_Y + JAW_BAR_Y", "-JAW_BAR_LEN / 2"), unit=u)

    # ------------------------------------------------------------ 07 内部機器
    def internal_asm(self, asm):
        """耐圧容器の中身。板金トレイに BIRDS 構造の基板（BPB と差し込み基板）とバッテリを載せる。"""
        u = "内部機器"
        p = self.new_part()                              # トレイ。基準: 取付面（タブの外面）とトレイ上面
        s = p.sketch("front")
        s.poly([(0, "TRAY_TAB"), (0, 0), ("TRAY_LEN", 0)], close=False)
        p.base_flange("TRAY_W", "TRAY_T", "TRAY_R", "板金 ベースフランジ（タブ曲げ）")
        tray = self.finish(p, D_INT / "内部トレイ.SLDPRT", P.A5052, 加工方法="板金。A5052 t2 をレーザーで抜き、タブを 90° 曲げ（内 R2）",
                           加工基準="タブの内面、トレイ上面、左右中心（輪郭線。板厚は外側へ付く）", 備考="後端蓋の支柱 2 本に M4 で固定。穴はアセンブリの穴フィーチャから反映")

        # 六角支柱（片側おねじ・片側めねじ）。原点 = 六角部の端、おねじは −X へ出る。おねじを後端蓋のめねじへねじ込む
        post = self.existing(STD / "MISUMI_VSLSBG8-40.0-M4-N4.SLDPRT", rho=P.SUS304.rho)

        p = self.new_part()                              # BPB。基準: 後端と左右中心。スロット位置は BIRDS-5 の BPB と同じ
        s = p.sketch("top")
        s.rect(0, "BPB_LEN", "-BPB_W / 2", "BPB_W / 2")
        p.extrude_mid("PCB_T", "基板")
        bpb = self.finish(p, D_INT / "BPB_バックプレーン基板.SLDPRT", P.THRUSTER_MAT, (0.1, 0.45, 0.2), mass=P.PCB_MASS * 2,
                          備考="BIRDS-5 BPB の構造（50 ピン×6、スロット FAB/OBC/COM/M-1/M-2/RAB、スロット位置は元のまま）。幅を 96 → 70 に詰めた")
        # 50 ピンコネクタ。配布 STEP（長さ = X、高さ = Z、基板面 z = 0）を、幅 = X・高さ = Y・長さ = Z にそろえる
        conn = self.vendor(VENDOR / "A3C-50DA-2DSA.stp", STD / "Hirose_A3C-50DA-2DSA(71).SLDPRT",
                           ((0, 1, 0), (0, 0, 1), (1, 0, 0)), (0, 0, 0), P.THRUSTER_MAT, 0.004, color=(0.9, 0.9, 0.85),
                           メーカー="ヒロセ電機", 備考="メーカー配布の 3D データ。2×25 ピン、2 mm ピッチ")
        p = self.new_part()                              # 差し込み基板。基準: 下端（コネクタ側）と左右中心
        s = p.sketch("right")
        s.rect("-CARD_W / 2", "CARD_W / 2", 0, "CARD_H")
        p.extrude_mid("PCB_T", "基板")
        card = self.finish(p, D_INT / "差し込み基板.SLDPRT", P.THRUSTER_MAT, (0.1, 0.45, 0.2), mass=P.PCB_MASS,
                           備考="BPB に直角に差す基板。外形は BIRDS-5 の 91.2×87 のまま")
        p = self.new_part()
        s = p.sketch("top")
        s.rect("-BATT_L / 2", "BATT_L / 2", "-BATT_W / 2", "BATT_W / 2")
        p.extrude_mid("BATT_H", "外形")
        batt = self.finish(p, STD / "LiPo_4S-10Ah.SLDPRT", P.THRUSTER_MAT, BLUE, mass=P.BATT_MASS, 備考="外形モデル。寸法は仮")

        # 板厚は輪郭線からタブでは後ろ、板では下へ付く。取付面と下面が設計位置に来るよう板厚分ずらして置く
        self.place(asm, tray, t=("TRAY_X0 + TRAY_T", "TRAY_Y + TRAY_T", 0), unit=u)
        for z in ("TRAY_TAP_Z", "-TRAY_TAP_Z"):
            self.place(asm, post, t=("-HULL_LEN / 2", "TRAY_TAP_Y", z), unit=u)
        self.place(asm, bpb, t=("BPB_X0", "BPB_Y", 0), unit=u)
        for i, nm in enumerate(P.BPB_SLOT_NAMES, 1):
            x = f"BPB_X0 + BPB_S{i}"
            asm.labels[x] = f"スロット {nm}"
            self.place(asm, conn, t=(x, "BPB_Y + PCB_T / 2", 0), unit=u)
            self.place(asm, card, t=(x, "CARD_Y", 0), unit=u)
        self.place(asm, batt, t=("BATT_X", "TRAY_Y + TRAY_T + BATT_H / 2", 0), unit=u)

    # ------------------------------------------------------------ 08 ハーネス
    def harness_paths(self):
        """ケーブルの経路（機体座標 mm）。

        側板の外面に片舷ずつ束ねて沿わせ、固定点（結束バンド）を必ず通す。後ろの噴流窓から内側へ入り、
        後端で折り返してペネトレータに入れる。束の中の位置は 1 本ずつ決めてあり、重ならない。
        """
        px, lx = P.PEN_END_X, P.HARNESS_LOOP_X
        ring = {a: (P.PEN_PCD / 2 * math.cos(math.radians(a)), P.PEN_PCD / 2 * math.sin(math.radians(a))) for a in range(0, 360, 45)}
        mid = {a: (P.PEN_PCD2 / 2 * math.cos(math.radians(a)), P.PEN_PCD2 / 2 * math.sin(math.radians(a))) for a in (0, 120, 240)}
        assign = {"V1 前右": 45, "V3 後右": 90, "H3 後右": 135, "H1 前右": 180, "H4 後左": 225, "V4 後左": 270, "V2 前左": 315, "H2 前左": 0}
        # 束の中の位置（束の中心高さからの上下、側板の外面からの距離）
        slot = {"V前": (4, 6), "H前": (-4, 6), "V後": (4, 14)}

        def at(x, key, sg):
            dy, dz = slot[key]
            return (x, P.TIE_YC + dy, sg * (P.OUTER_HALF_W + dz))

        def run(xs, key, sg):
            """固定点 xs を前から順に通る。各固定点の前後 15 mm にも点を置き、結束バンドの中をまっすぐ通す。"""
            return [at(x + dx, key, sg) for x in xs for dx in (15, 0, -15)]

        def tail(sg, k, py, pz):
            """後ろの固定点から、噴流窓 → 機体内側 → 後端の折り返し → ペネトレータ。"""
            lane = P.JET_Y1 - 12 - 9 * k                 # 窓を通る高さ（1 本ずつずらす）
            return [(-P.TIE_X2 - 24, lane, sg * (P.OUTER_HALF_W + 10)), (-P.TIE_X2 - 24, lane, sg * (P.INNER_HALF_W - 14)),
                    (-255, lane + 12, sg * 55), (lx, min(py, -45) - 12, pz), (lx, py, pz), (px, py, pz)]

        out = {}
        for name, pos, d in P.THRUSTERS:
            x, y, z = pos
            sg = 1 if z > 0 else -1
            fwd = x > 0
            py, pz = ring[assign[name]]
            if d[1]:                                     # 垂直: モータ下端から外面を下って束へ
                key = "V前" if fwd else "V後"
                pts = [(x, y - P.THR_LEN / 2, z), (x - 8, P.TIE_YC + 30, sg * (P.OUTER_HALF_W + 22))]
                xs = (P.TIE_X1, -P.TIE_X1, -P.TIE_X2) if fwd else (-P.TIE_X2,)
                pts += run(xs, key, sg) + tail(sg, 0 if fwd else 1, py, pz)
            elif fwd:                                    # 前の水平: モータ後端から前の噴流窓を抜けて束へ
                pts = [(x - P.THR_LEN / 2 * d[0], y, z - P.THR_LEN / 2 * d[2]), (x - 62 * d[0], y + 8, z - 62 * d[2]),
                       (P.TIE_X1 + 22, P.JET_Y1 - 10, sg * (P.OUTER_HALF_W + 6))]
                pts += run((P.TIE_X1, -P.TIE_X1, -P.TIE_X2), "H前", sg) + tail(sg, 2, py, pz)
            else:                                        # 後ろの水平: 底板の下から後端へ直接回す
                pts = [(x - P.THR_LEN / 2 * d[0], y, z - P.THR_LEN / 2 * d[2]), (x - 65 * d[0], y + 5, z - 65 * d[2]),
                       (-258, y + 25, sg * 40), (lx, min(py, -45) - 20, pz), (lx, py, pz), (px, py, pz)]
            out[name] = (pts, P.THR_CABLE_D)
        # サーボ: 上面のグランドから出し、本体の後ろを下りてアーム板の外側を回り、底板の下の中央を最短で後ろへ通す。
        # 付属ケーブルは 0.7 m で後端蓋まで届かないので、途中で延長する（長さは経路から求めて部品表に載せる）
        sy, sz = mid[240]
        cy = P.SERVO_CABLE_Y
        zs = P.ARM_HALF_W + 8                            # アーム板の幅広部の外側。前側の抜け止めボルトからも離す
        gx, gy, gz = P.MANIP_X, P.SERVO_TOP + P.SERVO_GLAND_H, P.SERVO_ZC + P.SERVO_GLAND_POS
        back = P.MANIP_X - P.SERVO_W / 2                 # 本体の後面
        pts = [(gx, gy + 1, gz), (gx - 6, gy + 14, gz), (back - 12, gy + 6, gz + 4), (back - 16, P.SERVO_TOP - 22, gz + 14),
               (253, P.ARM_TOP - 1, zs), (P.DECK_X + 11, P.DECK_Y - 2, zs), (P.DECK_X + 3, cy, 25)]
        pts += [(x + dx, cy, 0) for x in (P.TIE_DX1, P.TIE_DX2) for dx in (15, 0, -15)]
        pts += [(-150, cy, 0), (-P.DECK_X - 8, cy, 0), (-262, cy + 12, sz / 2), (lx, sy - 50, sz), (lx, sy, sz), (px, sy, sz)]
        out["サーボ"] = (pts, P.SERVO_CABLE_D)
        ty, tz = mid[0]
        out["テザー"] = ([(px, ty, tz), (px - 30, ty, tz), (px - 55, ty + 8, tz)], 8.0)
        return out

    def harness_asm(self, asm):
        """ケーブルの経路と固定。結束バンドは側板の穴 2 個を通して束を留める（片舷 4 か所）。"""
        u = "ハーネス"
        p = self.new_part()
        for name, (pts, d) in self.harness_paths().items():
            p.cable(pts, d, f"ケーブル {name}")
        h = self.finish(p, D_HARN / "ハーネス.SLDPRT", P.Mat("ケーブル", P.CABLE_RHO), (0.25, 0.25, 0.28),
                        備考="配線経路の検討用。経路は 3D スケッチの点で決めてある。長さ・曲げ半径・固定点の確認に使う")
        self.place(asm, h, unit=u)

        p = self.new_part()                              # 結束バンド。基準: 側板の板厚中心と束の中心高さ
        s = p.sketch("right")
        zi, zo = "-(PLATE_T / 2 + BAND_T)", "PLATE_T / 2 + BAND_OUT + BAND_T"
        yl, yh = "TIE_Y2 - TIE_YC - BAND_T / 2", "TIE_Y1 - TIE_YC + BAND_T / 2"
        s.rect(zi, zo, yl, yh)
        s.rect("-(PLATE_T / 2)", "PLATE_T / 2 + BAND_OUT", "TIE_Y2 - TIE_YC + BAND_T / 2", "TIE_Y1 - TIE_YC - BAND_T / 2")
        p.extrude_mid("BAND_W", "バンド")
        band = self.finish(p, STD / "結束バンド_幅4.8.SLDPRT", P.Mat("PA66（耐候）", 1140), (0.05, 0.05, 0.05), メーカー="ミスミ",
                           備考="耐候性の結束バンド。側板の穴 2 個を通してケーブルの束を留める。形は締めた状態の代用")
        for x in ("TIE_X1", "-TIE_X1", "TIE_X2", "-TIE_X2"):
            self.place(asm, band, t=(x, "TIE_YC", "SIDE_Z"), unit=u)
            self.place(asm, band, FLIP_X, (x, "TIE_YC", "-SIDE_Z"), unit=u)
        for x in ("TIE_DX1", "TIE_DX2"):                 # 底板の下面。バンドの輪を下へ向ける
            self.place(asm, band, ((1, 0, 0), (0, 0, 1), (0, -1, 0)), (x, "DECK_Y", 0), unit=u)

    # ------------------------------------------------------------ 06 締結部品
    def fastener_asm(self, asm):
        """横通しボルトとナット。専用のサブアセンブリにまとめる。

        トップアセンブリの穴フィーチャは対象部品を指定して開けるので、ボルトが先にあっても削られない。
        穴フィーチャを入れたあとのトップアセンブリは合致 1 件ごとの再計算が重いので、先に配置を済ませる。
        """
        u = "締結部品"
        rod = self.existing(STD / "MISUMI_FABS5-250.SLDPRT", rho=P.SUS304.rho)     # 全ねじ。原点 = 片端、+X へ伸びる
        self.nut = self.existing(STD / "MISUMI_SLBNR5.SLDPRT", rho=P.SUS304.rho)   # 座面 = 原点、本体は −X 側
        self.washer = self.existing(STD / "MISUMI_SPWF5.SLDPRT", rho=P.SUS304.rho)  # 当たり面 = 原点、本体は −X 側
        for x, y in (("ROD_X_TOP", "ROD_Y_TOP"), ("-ROD_X_TOP", "ROD_Y_TOP"), ("ROD_X_LOW", "ROD_Y_LOW"), ("-ROD_X_LOW", "ROD_Y_LOW")):
            self.place(asm, rod, X_TO_Z, (x, y, "-ROD_LEN / 2"), unit=u)
            self.nut_washer(asm, u, 2, (x, y, "OUTER_HALF_W"), +1)
            self.nut_washer(asm, u, 2, (x, y, "-OUTER_HALF_W"), -1)
        # 可動爪のつなぎ棒: 爪を外と内からナットではさむ
        x, y = "MANIP_X + JAW_BAR_X", "SERVO_AXIS_Y + JAW_BAR_Y"
        self.nut_washer(asm, u, 2, (x, y, "JAW_FACE"), +1)
        self.nut_washer(asm, u, 2, (x, y, "JAW_FACE_IN"), -1)
        self.nut_washer(asm, u, 2, (x, y, "-JAW_FACE"), -1)
        self.nut_washer(asm, u, 2, (x, y, "-JAW_FACE_IN"), +1)
        self.bolts(asm, u)

    def nut_washer(self, asm, u, axis, t, side):
        """面に平座金を当て、その外にナットを置く。axis: 面の法線の軸（1 = Y, 2 = Z）。side: 面から見て置く側（+1 / −1）。"""
        rows = {(2, +1): X_TO_NEG_Z, (2, -1): X_TO_Z, (1, +1): X_DOWN, (1, -1): X_TO_Y}[(axis, side)]
        self.place(asm, self.washer, rows, t, unit=u)
        t2 = list(t)
        t2[axis] = f"{t[axis]} + WASHER_T" if side > 0 else f"{t[axis]} - WASHER_T"
        self.place(asm, self.nut, rows, tuple(t2), unit=u)

    def bolts(self, asm, u):
        """六角穴付きボルト。MISUMI RAPiD Design で取り込んだモデル（型番・単価・出荷日のプロパティ付き）を合致で配置する。

        モデルの原点は座面（頭の下）、ねじ部は +X。取り込みは `python -m swkit.rapid cad/00_既製品 <型番> ...`。
        """
        b = {k: self.existing(STD / f"MISUMI_{k}.SLDPRT", rho=P.SUS304.rho) for k in ("SCB3-16", "SCB3-14", "SCB4-14", "SCB4-30", "SCB5-35", "SCB4-8")}
        # 水平スラスタ: 底板の上面から下へ
        for sx in ("", "-"):
            for sz in ("", "-"):
                for x, z in ((f"{sx}(HORZ_X + HOLE_KP)", f"{sz}(HORZ_Z - HOLE_KM)"), (f"{sx}(HORZ_X + HOLE_KM)", f"{sz}(HORZ_Z - HOLE_KP)"),
                             (f"{sx}(HORZ_X - HOLE_KM)", f"{sz}(HORZ_Z + HOLE_KP)"), (f"{sx}(HORZ_X - HOLE_KP)", f"{sz}(HORZ_Z + HOLE_KM)")):
                    self.place(asm, b["SCB3-16"], X_DOWN, (x, "DECK_TOP", z), unit=u)
        # 垂直スラスタ: 側板の内面から外へ
        for sx in ("", "-"):
            for a in ("+", "-"):
                for c in ("+", "-"):
                    x, y = f"{sx}(VERT_X {a} THR_HOLE_W / 2)", f"VERT_Y {c} THR_HOLE_AX / 2"
                    self.place(asm, b["SCB3-16"], X_TO_Z, (x, y, "INNER_HALF_W"), unit=u)
                    self.place(asm, b["SCB3-16"], X_TO_NEG_Z, (x, y, "-INNER_HALF_W"), unit=u)
        # サーボ: アーム板の下面から上へ（めねじ深さ 5 に対し、ねじ込み 4）
        for a in ("+", "-"):
            for z in ("SERVO_HOLE_Z1", "SERVO_HOLE_Z2", "SERVO_HOLE_Z3"):
                self.place(asm, b["SCB3-14"], X_TO_Y, (f"MANIP_X {a} SERVO_HOLE_P / 2", "ARM_BOTTOM", z), unit=u)
        # 可動爪: 外面から出力円板・従動軸へ
        r = "SERVO_DISC_PCD / 2"
        for x, y in ((f"MANIP_X + {r}", "SERVO_AXIS_Y"), (f"MANIP_X - {r}", "SERVO_AXIS_Y"), ("MANIP_X", f"SERVO_AXIS_Y + {r}"), ("MANIP_X", f"SERVO_AXIS_Y - {r}")):
            self.place(asm, b["SCB4-14"], X_TO_NEG_Z, (x, y, "JAW_FACE"), unit=u)
            self.place(asm, b["SCB4-14"], X_TO_Z, (x, y, "-JAW_FACE"), unit=u)
        # 窓押え環: 前面から前端蓋のめねじへ。1 本を合致で決め、中心軸まわりに等配する
        xr = f"{FACE} + WINDOW_T + RING_T"
        asm.labels[xr] = "窓押え環 前面"
        seed = self.place(asm, b["SCB4-30"], FLIP_X, (xr, "RING_PCD / 2", 0), unit=u)
        asm.circular(seed, P.RING_N, "窓押えボルト 等配")
        for i in range(1, P.RING_N):
            t = math.radians(360 * i / P.RING_N)
            self.record(b["SCB4-30"], FLIP_X, (asm.val(xr), P.RING_PCD / 2 * math.cos(t), P.RING_PCD / 2 * math.sin(t)), u)
        # アーム板とバラスト: 上から底板を貫通し、下でナット止め
        for x in ("ARM_BOLT_X1", "ARM_BOLT_X2"):
            for z in ("ARM_BOLT_Z", "-ARM_BOLT_Z"):
                self.place(asm, self.washer, X_DOWN, (x, "ARM_TOP", z), unit=u)      # 樹脂板なので頭の下にも座金
                self.place(asm, b["SCB5-35"], X_DOWN, (x, "ARM_TOP + WASHER_T", z), unit=u)
                self.nut_washer(asm, u, 1, (x, "DECK_BOTTOM", z), -1)
        for sx in ("+", "-"):
            for z in ("BALLAST_Z", "-BALLAST_Z"):
                self.place(asm, b["SCB5-35"], X_DOWN, (f"BALLAST_XC {sx} BALLAST_HOLE_X", "BALLAST_TOP", z), unit=u)
                self.nut_washer(asm, u, 1, (f"BALLAST_XC {sx} BALLAST_HOLE_X", "DECK_BOTTOM", z), -1)
        # 内部トレイ: タブの内面から支柱へ
        for z in ("TRAY_TAP_Z", "-TRAY_TAP_Z"):
            self.place(asm, b["SCB4-8"], FLIP_X, ("TRAY_X0 + TRAY_T", "TRAY_TAP_Y", z), unit=u)

    # ------------------------------------------------------------ 共締め穴の宣言
    def shared_holes(self):
        """相手と共締めする穴。トップアセンブリの穴フィーチャとして開け、加工部品へ反映される（swkit.Project.build）。

        対象は加工部品だけ。購入品（スラスタ・サーボ）は自身の図面どおりの穴を持ち、位置は同じ変数で決まる。
        側板・バラスト・可動爪は同じ部品ファイルを 2 か所で使うので、1 個目だけを対象にする。
        """
        H = self.shared_hole
        fr, bu, mn = "フレーム", "浮力調整部", "マニピュレータ"
        side, deck, arm, jaw = (fr, "側板", True), (fr, "底板"), (mn, "アーム板"), (mn, "可動爪", True)
        through = "PLATE_T + 2"
        thr = []
        for sx in ("", "-"):
            for sz in ("", "-"):
                thr += [(f"{sx}(HORZ_X + HOLE_KP)", f"{sz}(HORZ_Z - HOLE_KM)"), (f"{sx}(HORZ_X + HOLE_KM)", f"{sz}(HORZ_Z - HOLE_KP)"),
                        (f"{sx}(HORZ_X - HOLE_KM)", f"{sz}(HORZ_Z + HOLE_KP)"), (f"{sx}(HORZ_X - HOLE_KP)", f"{sz}(HORZ_Z + HOLE_KM)")]
        vert = [(f"{sx}(VERT_X {a} THR_HOLE_W / 2)", f"VERT_Y {b} THR_HOLE_AX / 2") for sx in ("", "-") for a in ("+", "-") for b in ("+", "-")]
        rods = [("ROD_X_TOP", "ROD_Y_TOP"), ("-ROD_X_TOP", "ROD_Y_TOP"), ("ROD_X_LOW", "ROD_Y_LOW"), ("-ROD_X_LOW", "ROD_Y_LOW")]
        r = "SERVO_DISC_PCD / 2"
        return [
            H("front", "OUTER_HALF_W", rods, "Ø5.5", "横通しボルト穴 M5（側板）", [side], through),
            H("front", "INNER_HALF_W", rods[:2], "Ø5.5", "横通しボルト穴 M5（浮力材）", [(bu, "浮力材")], "2 * INNER_HALF_W + 2"),
            H("top", "DECK_TOP", thr, "Ø3.4", "水平スラスタ取付穴 M3", [deck], through),
            H("front", "INNER_HALF_W", vert, "Ø3.4", "垂直スラスタ取付穴 M3", [side], through, from_pos=False),
            H("top", "ARM_TOP", [(x, z) for x in ("ARM_BOLT_X1", "ARM_BOLT_X2") for z in ("ARM_BOLT_Z", "-ARM_BOLT_Z")],
              "Ø5.5", "アーム板固定穴 M5", [arm, deck], "2 * PLATE_T + 2"),
            H("top", "ARM_BOTTOM", [(f"MANIP_X {a} SERVO_HOLE_P / 2", z) for a in ("+", "-")
                                    for z in ("SERVO_HOLE_Z1", "SERVO_HOLE_Z2", "SERVO_HOLE_Z3")],
              "Ø3.4", "サーボ取付穴 M3", [arm], through, from_pos=False),
            H("front", "JAW_FACE", [(f"MANIP_X + {r}", "SERVO_AXIS_Y"), (f"MANIP_X - {r}", "SERVO_AXIS_Y"),
                                    ("MANIP_X", f"SERVO_AXIS_Y + {r}"), ("MANIP_X", f"SERVO_AXIS_Y - {r}")],
              "Ø4.5", "出力円板・従動軸 取付穴 M4", [jaw], through),
            H("front", "JAW_FACE", [("MANIP_X + JAW_BAR_X", "SERVO_AXIS_Y + JAW_BAR_Y")], "Ø5.5", "つなぎ棒穴 M5", [jaw], through),
            H("right", "TRAY_X0 + TRAY_T", [("TRAY_TAP_Z", "TRAY_TAP_Y"), ("-TRAY_TAP_Z", "TRAY_TAP_Y")],
              "Ø4.5", "トレイ取付穴 M4", [("内部機器", "内部トレイ")], "TRAY_T + 1"),
            # 穴位置を指示した面の部品（1 枚目のバラスト）にも穴が開くので、対象は底板だけでよい
            H("top", "BALLAST_TOP", [(f"BALLAST_XC {sx} BALLAST_HOLE_X", f"{sz}BALLAST_Z") for sx in ("+", "-") for sz in ("", "-")],
              "Ø5.5", "バラスト固定穴 M5", [deck], "BALLAST_N * BALLAST_T + PLATE_T + 2"),
        ]

    # ------------------------------------------------------------ 全体
    def run(self):
        units = (("耐圧容器", D_HULL, self.hull_asm), ("フレーム", D_FRAME, self.frame_asm), ("推進部", D_PROP, self.prop_asm),
                 ("浮力調整部", D_BUOY, self.buoy_asm), ("マニピュレータ", D_MANIP, self.manip_asm), ("締結部品", D_FAST, self.fastener_asm),
                 ("内部機器", D_INT, self.internal_asm), ("ハーネス", D_HARN, self.harness_asm))
        self.build(TOP / "UWD-01_水中ドローン.SLDASM", units, self.shared_holes(), layout=self.layout, title="水中ドローン UWD-01",
                   out_dir=OUT, image_dir=ROOT / "doc" / "03_設計" / "図", prefix="UWD-01")

    def single(self, names):
        """部品を単体で作る（作り方の確認用）。"""
        makers = {"耐圧筒": self.tube, "後端蓋": lambda: self.cap(False), "前端蓋": lambda: self.cap(True),
                  "観察窓": self.window, "窓押え環": self.ring, "側板": self.side_plate,
                  "筒受け": lambda: self.saddle(False), "筒押え": lambda: self.saddle(True),
                  "底板": self.deck, "スラスタ": self.thruster, "ペネトレータ": self.penetrator}
        unit = {"内部機器": (self.internal_asm, D_INT), "ハーネス": (self.harness_asm, D_HARN), "推進部": (self.prop_asm, D_PROP)}
        if names in unit:                                # ユニット単位の試作（サブアセンブリごと作る）
            fn, d = unit[names]
            a = self.new_asm(d / f"{names}.SLDASM")
            fn(a)
            a.save()
            print("  拘束されていない構成部品:", a.unconstrained() or "なし")
            return
        for n in names.split(","):
            makers[n]()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    SW.SHOW = "--show" in sys.argv                       # 画面更新を止めずに作る（録画用）
    b = Builder(use_cache="--no-cache" not in sys.argv)
    try:
        if args:
            b.single(args[0])
        else:
            b.run()
    finally:
        b.sw.restore()
