"""水中ドローン UWD-01 の設計パラメータ。事前計算と CAD 生成の両方がここだけを読む。

座標系（機体・SOLIDWORKS 共通）: X = 前, Y = 上, Z = 右舷。原点は耐圧筒の中心。単位は mm, kg, N。
ここの大文字の数値は、CAD の部品・アセンブリの中で同名のグローバル変数になり、寸法の関係式から
参照される。

出典の区分
  [要求] 依頼で指定された値
  [規格] JIS B 2401 の値
  [図面] メーカーの販売ページに載っている寸法図・仕様表の値（2026-11-25 に実ブラウザで確認）
  [調査] 販売ページの検索結果で見た値。図面・現物では未確認
  [仮]   根拠資料がなく、設計を進めるために置いた値
"""
from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.80665
RHO_FRESH, RHO_SEA = 1000.0, 1025.0     # kg/m3

# ---------------------------------------------------------------- 使用条件
DEPTH_RATED = 100.0                      # m [仮] 設計水深
SAFETY_BUCKLING = 3.0                    # 座屈の安全率の下限
SAFETY_YIELD = 2.0                       # 降伏の安全率の下限


# ---------------------------------------------------------------- 材料
@dataclass(frozen=True)
class Mat:
    name: str
    rho: float                           # kg/m3
    E: float = 0.0                       # MPa
    sy: float = 0.0                      # 耐力 MPa
    nu: float = 0.33
    sw: str = ""                         # SOLIDWORKS 材料名。空なら密度だけ設定する


A6063 = Mat("A6063-T5", 2700, 68_600, 145, 0.33, "6063-T5")
A6061 = Mat("A6061-T6", 2700, 68_900, 245, 0.33, "6061-T6 (SS)")
A5052 = Mat("A5052-H32", 2680, 70_000, 195, 0.33, "5052-H32")
SUS304 = Mat("SUS304", 8000, 193_000, 205, 0.29, "AISI 304")
ACRYL = Mat("アクリル(キャスト)", 1190, 3_000, 70, 0.37)   # sy は短期引張強さの目安
HDPE = Mat("HDPE", 950, 1_000, 25, 0.42)
NBR = Mat("NBR-70", 1200)
FOAM = Mat("Divinycell HCP30 相当", 200)     # 水中用の独立気泡 PVC フォーム。密度は [調査]
FOAM_STRENGTH = 3.0                      # MPa。HCP30 の水圧つぶれ点 30 bar（体積が 5 % 減る圧力）[調査]
THRUSTER_MAT = Mat("スラスタ(見かけ)", 0)  # 質量はカタログ値に合わせる

# ---------------------------------------------------------------- 耐圧容器
HULL_ID = 140.0                          # 与圧部内径。依頼は 120 以上。BIRDS の差し込み基板 91.2×87 を立てて入れるため 140 にした
HULL_CLEAR_LEN = 400.0                   # [要求] 与圧部の有効長（両端蓋のはめ込み先端の間）
HULL_T = 5.0                             # A6063 丸パイプ 150×5（藤野金属の在庫寸法表に掲載）
HULL_OD = HULL_ID + 2 * HULL_T
SPIGOT_LEN = 25.0                        # 端蓋のはめ込み長さ
HULL_LEN = HULL_CLEAR_LEN + 2 * SPIGOT_LEN
# 押出パイプの内径公差は Oリングのシール面に使えないので、両端だけ内径を仕上げる
SEAL_BORE = 142.0                        # シール面の仕上げ内径（製作図では H9）
SEAL_LEN = 30.0                          # 仕上げ深さ
LEAD_AX, LEAD_RAD = 1.5, 0.55            # Oリングを傷つけない導入テーパ（約 20°）
SPIGOT_OD = 141.9                        # はめ込み径（製作図では φ142 f8）
SPIGOT_ID = 124.0                        # はめ込み部の肉抜き径
SPIGOT_C = 1.0                           # はめ込み先端の面取り
CAP_PLATE_T = 12.0                       # 端蓋の受圧板厚（つばも同じ厚さ）
FLANGE_OD = 158.0                        # φ160 丸棒から外径を一皮むいて仕上げる径

# Oリング [規格] JIS B 2401 G シリーズ（W = 3.1）
ORING_W, ORING_W_TOL = 3.1, 0.10
GSEAL_ID = 134.4                         # G-135。円筒面固定・端蓋はめ込み部 ×2 段
GROOVE_D = SEAL_BORE - 5.0               # 溝底径 d（0/-0.10）。径方向の溝深さは規格と同じ 2.5
GROOVE_BORE = SEAL_BORE                  # 穴径 D（+0.10/0）
GROOVE_W = 4.1                           # 溝幅 G（バックアップリングなし, +0.25/0）
GROOVE_POS = 5.0                         # 基準A（つばの当たり面）から 1 本目の溝の手前端まで
GROOVE_PITCH = 9.0                       # 2 本目までのピッチ
GROOVE_N = 2
G85_ID = 84.4                            # 平面固定・観察窓
FACE_GROOVE_ID = 85.0                    # 外圧なので溝内径に Oリングを沿わせる
FACE_GROOVE_H = 2.4                      # 溝深さ
FACE_GROOVE_W = 4.1

# 観察窓（前端蓋）。窓押えは平板リングを市販カラーで浮かせて M4 で締める
WINDOW_OD, WINDOW_T = 104.0, 15.0
WINDOW_APERTURE = 80.0                   # 前端蓋の開口径（窓の無支持径）
RING_OD, RING_ID, RING_T = 124.0, 88.0, 10.0     # 窓押え環。フレームと同じ HDPE t10 から切り出す
RING_N, RING_PCD = 6, 108.5              # M4 を窓の外周に接する位置に置き、窓の芯出しを兼ねる
RING_TAP_DEPTH = 10.0                    # 前端蓋 M4 めねじの下穴深さ（板厚 12 を貫通させない）
TRAY_TAP_Z, TRAY_TAP_Y, TRAY_TAP_DEPTH = 22.0, -45.0, 8.0   # 後端蓋の内側、内部トレイの支柱用 M4 止まり穴（±Z の 2 か所。ペネトレータ穴の間）

# ケーブル貫通（後端蓋）: Blue Robotics WetLink ペネトレータ M10。圧縮シール式で樹脂封止が要らない。
# [図面] 定格水深 1000 m、二面幅 16、締付 3.5 N·m。取付はキリ穴 Ø10.0〜10.2＋ナット、または M10×1.5 タップ（下穴 Ø8.5）
# 端蓋の板厚 12 にナットが掛かるねじ長さがあるか確認できないので、端蓋に M10 タップを切る方を使う
PEN_N, PEN_PCD = 8, 90.0                 # スラスタ 8 本（ケーブル Ø7 → M10-7.5mm-HC）
PEN_N2, PEN_PCD2 = 3, 30.0               # 中央 3 本: テザー、ベントプラグ、サーボ（ケーブル Ø4 → M10-4.5mm-HC）
PEN_OUT = 25.0                           # [図面] ペネトレータが端蓋の外面から突き出す長さ（配布 CAD から）
PEN_MASS = 0.012                         # [仮] 1 個の質量 kg

# 内部機器。板金トレイを後端蓋の支柱 2 本に固定し、後端蓋と一緒に引き抜く
TRAY_STANDOFF = 40.0                     # 後端蓋の内面からトレイの取付面まで（ペネトレータとケーブルの曲げを避ける）
TRAY_X0 = -HULL_LEN / 2 + TRAY_STANDOFF  # トレイの取付面（曲げたタブの外面）
TRAY_Y = -57.0                           # トレイ下面の高さ（板厚は上へ）
TRAY_LEN, TRAY_W, TRAY_T, TRAY_R = 335.0, 70.0, 2.0, 2.0     # A5052 t2、内 R2
TRAY_TAB = 20.0                          # 上へ曲げたタブの高さ
# 基板: BIRDS-5 オープンソースのバックプレーン基板 (BPB) の構造を使う。[図面] BPB_FM1.brd（MIT ライセンス）から
#   50 ピンコネクタ（ヒロセ A3C-50DA-2DSA(71)、2×25・2 mm ピッチ）6 個、スロットは FAB/OBC/COM/M-1/M-2/RAB
# 差し込み基板 91.2×87 は BIRDS のまま使う。BPB は幅だけ 96 → 70 に詰める（設計変更してよいとの指示）
BPB_LEN, BPB_W, PCB_T = 96.0, 70.0, 1.6  # BPB の長さとスロット位置は元のまま、幅は 96 → 70
BPB_S1, BPB_S2, BPB_S3, BPB_S4, BPB_S5, BPB_S6 = 11.55, 39.85, 47.0, 67.95, 76.4, 84.9   # [図面] スロット位置
BPB_SLOT_NAMES = ("FAB", "OBC", "COM", "M-1", "M-2", "RAB")
CONN_H = 4.2                             # [図面] A3C-50DA-2DSA の基板上の高さ（配布 CAD から。外形 50.0×4.0）
CARD_GAP = 1.0                           # [仮] コネクタ上面から差し込み基板の下端まで（相手側コネクタ LPC-50M2LG の寸法で決まる）
BPB_X0 = -170.0                          # BPB の後端
BPB_Y = TRAY_Y + TRAY_T + 5.0 + PCB_T / 2   # BPB の板厚中心（トレイ上面から 5 mm のスペーサで浮かせる）
CARD_W, CARD_H = 91.2, 87.0              # [図面] 差し込み基板（BIRDS-5 RAB 1U の外形）。コネクタは 91.2 の辺
CARD_Y = BPB_Y + PCB_T / 2 + CONN_H + CARD_GAP   # 差し込み基板の下端
BATT_L, BATT_W, BATT_H, BATT_MASS = 170.0, 70.0, 45.0, 0.9   # [仮] 4S 10 Ah LiPo
BATT_X = 15.0                            # バッテリ中心の前後位置。前後の釣合いの微調整に使う
PCB_MASS = 0.05                          # [仮] 基板 1 枚
# 未作図の内部機器 [仮]: ESC×8、カメラ、配線
PAYLOAD_MASS = 1.3
PAYLOAD_CG = (80.0, 10.0, 0.0)

# ---------------------------------------------------------------- スラスタ ApisQueen U2 Mini
# [図面] underwaterthruster.com の寸法図と推力試験表。12〜16 V、海水可、ケーブル Ø7×1.5 m、210 g
THR_THRUST_KGF = 1.3                     # [図面] 16 V・8 A 版の前進推力。12 A 版は 2.1 kgf（表が 2 種類あり低い方を使う）
THR_REV_RATIO = 1.2 / 1.3                # [図面] 同じ表の逆転 1.20 kgf
THR_MASS = 0.21                          # [図面] 空中質量 kg
THR_I_MAX = 8.0                          # [図面] A（12 A 版は 12）
THR_CABLE_D = 7.0                        # [図面]
THR_DUCT_OD, THR_DUCT_ID, THR_DUCT_LEN = 72.21, 65.11, 36.53   # [図面]
THR_LEN = 95.8                           # [図面] 全長
THR_POD_D = 30.0                         # [仮] モータ胴径（図面に寸法なし）
THR_FOOT_H = 40.85                       # [図面] 推力軸から取付面まで
THR_FOOT_L, THR_FOOT_W = 36.6, 22.6      # [図面] 取付座 軸方向×幅（配布 3D データを測った値）
THR_FOOT_T = THR_FOOT_H - THR_DUCT_OD / 2 + 2.5          # 取付座の厚さ（ダクト外周に 2.5 食い込ませて一体にする）
THR_HOLE_W = 15.0                        # [図面] 取付ねじ 4-M3 の幅方向ピッチ
THR_HOLE_AX = 30.0                       # [図面] 同 軸方向ピッチ。寸法図の 30 をこう読んだ（取付座の長さ 36.6 と整合）。現物で確かめる
THR_TAP_DEPTH = 6.0                      # [仮] 取付座の M3 めねじ深さ
THR_HOLE_DEPTH = 10.0                    # 板側のキリ穴深さ（＝板厚。板を貫通させる）

# ---------------------------------------------------------------- フレーム
# 全部品を HDPE 10 mm の板 1 枚から切り出す。ほぞを側板の角穴に差し、横通しボルト 4 本で挟む。
# ねじ切り・曲げ・溶接はない。
PLATE_T = 10.0
SLOT_CL = 0.2                            # 角穴の片側すきま（ほぞ幅方向）
SLOT_CL_T = 0.6                          # 同（板厚方向）。HDPE 板の板厚公差が大きいので広く取る
SLOT_R = 0.5                             # 角穴の内角 R（ウォータージェットの切り幅程度。ほぞの角に当たらない大きさ）
TAB_C = 1.5                              # ほぞ先端の面取り（角穴の内角 R を逃がす）
SIDE_Z = 110.0                           # 側板の板厚中心
SIDE_X = 320.0                           # 前後端 ±。後端はペネトレータ（蓋の外へ 25 突き出す）とケーブルの折り返しを囲う長さ
SIDE_BOTTOM, SIDE_TOP = -210.0, 160.0    # 下端（そり）, 上端
HANDLE_X, HANDLE_Y0, HANDLE_Y1 = 50.0, 128.0, 148.0      # 持ち手穴（浮力材の上）
# ハーネスの固定: 側板の外面にケーブルを束ねて沿わせ、穴 2 個に結束バンドを通して留める。片舷 4 か所
TIE_X1, TIE_X2 = 100.0, 205.0            # 固定点の前後位置 ±
TIE_Y1, TIE_Y2 = -66.0, -92.0            # 結束バンドを通す穴 Ø5.5 の上下（中央窓の下、底板の上）
TIE_YC = (TIE_Y1 + TIE_Y2) / 2           # ケーブル束の中心高さ
TIE_DX1, TIE_DX2 = 100.0, 62.0           # 底板の下面でサーボのケーブルを留める固定点の前後位置（バラストの無い範囲）
TIE_DZ = (TIE_Y1 - TIE_Y2) / 2           # 同 穴の左右 ±（結束バンドは側板と同じ寸法）
BAND_W, BAND_T, BAND_OUT = 4.8, 1.5, 25.0   # 結束バンドの幅・厚さ、側板の外面からバンド内側まで（束の厚さ）
SIDE_R = 30.0                            # 外周の角 R
WINDOW_R = 8.0                           # 窓の内角 R
JET_X0, JET_X1, JET_Y0, JET_Y1 = 45.0, 235.0, -194.0, -115.0   # 水平スラスタの噴流を通す窓
CW_X, CW_Y = 85.0, 70.0                  # 中央の肉抜き窓 ±
INNER_HALF_W = SIDE_Z - PLATE_T / 2      # 側板内面
OUTER_HALF_W = SIDE_Z + PLATE_T / 2      # 側板外面
CRADLE_X = HULL_LEN / 2 - PLATE_T / 2 - 1.0   # 筒受け・筒押えの位置 ±。端蓋のつばのすぐ内側に置き、筒の前後の動きを止める
NOTCH_W, NOTCH_H = 37.0, 10.5            # 筒受け下部のくぐり穴（アーム板とケーブルを通す）半幅・高さ
CUT_R = 1.0                              # くぐり穴の内角 R
CRADLE_BORE = HULL_OD + 1.0              # 筒外径 + ゴムシート 0.5
CLAMP_TOP = 94.0                         # 筒押えの上端（浮力材を載せる面）
TAB_W, TAB_Y = 30.0, 45.0                # 筒受けのほぞ幅と中心高さ ±
DECK_Y = -100.0                          # 底板の板厚中心
DECK_X = 225.0
DECK_TAB_W, DECK_TAB_X = 40.0, 170.0     # 底板のほぞ幅と位置（中央と ±）
DECK_TOP = DECK_Y + PLATE_T / 2
DECK_BOTTOM = DECK_Y - PLATE_T / 2
SERVO_CABLE_Y = DECK_BOTTOM - 6.0        # サーボのケーブルが底板の下を通る高さ
FOAM_T = 23.0                            # 浮力材の厚さ。浮力釣合いの計算（buoyancy_balance.py）で決めた値
FOAM_YC = CLAMP_TOP + FOAM_T / 2         # 浮力材の厚さ中心
ROD_X_TOP, ROD_Y_TOP = 150.0, FOAM_YC    # 横通しボルト M5。上 2 本は浮力材の厚さ中心を貫通して押さえる
# 下 2 本は端蓋のつばのすぐ外側を通し、端蓋の抜け止めを兼ねる（開けるときはこの 1 本を抜く）
ROD_X_LOW = HULL_LEN / 2 + CAP_PLATE_T + 3.5
ROD_Y_LOW = -(FLANGE_OD / 2 - 3.0)
ROD_D, ROD_LEN = 5.0, 250.0              # MISUMI FABS5-250（全長指定ねじ SUS304 の最大長）。外面 ±115 から座金 1 ＋ナット 4 ＋余長 5
WASHER_T = 1.0                           # 平座金 SPWF5 の厚さ
NUT_Z = OUTER_HALF_W + 2.0               # ナット厚さ中心の位置 ±

# スラスタ配置。(名前, 位置, 推力方向)。推力方向は正転時に機体へ与える力の向き
VERT_X, VERT_Y = 170.0, 0.0
VERT_Z = OUTER_HALF_W + THR_FOOT_H
HORZ_X, HORZ_Z = 170.0, 56.0
HORZ_Y = DECK_BOTTOM - THR_FOOT_H
C45 = math.sqrt(0.5)
HOLE_KP = (THR_HOLE_AX / 2 + THR_HOLE_W / 2) * C45   # 45° に振った取付穴 4 個の X・Z 方向の振り分け
HOLE_KM = (THR_HOLE_AX / 2 - THR_HOLE_W / 2) * C45
AX_K = THR_LEN / 2 * C45                 # レイアウトに描く推力軸の線の X・Z 方向の半長
THRUSTERS = (
    ("H1 前右", (HORZ_X, HORZ_Y, HORZ_Z), (C45, 0.0, -C45)),
    ("H2 前左", (HORZ_X, HORZ_Y, -HORZ_Z), (C45, 0.0, C45)),
    ("H3 後右", (-HORZ_X, HORZ_Y, HORZ_Z), (C45, 0.0, C45)),
    ("H4 後左", (-HORZ_X, HORZ_Y, -HORZ_Z), (C45, 0.0, -C45)),
    ("V1 前右", (VERT_X, VERT_Y, VERT_Z), (0.0, 1.0, 0.0)),
    ("V2 前左", (VERT_X, VERT_Y, -VERT_Z), (0.0, 1.0, 0.0)),
    ("V3 後右", (-VERT_X, VERT_Y, VERT_Z), (0.0, 1.0, 0.0)),
    ("V4 後左", (-VERT_X, VERT_Y, -VERT_Z), (0.0, 1.0, 0.0)),
)

# ---------------------------------------------------------------- 浮力材・バラスト
FOAM_X = 224.0                           # 前後 ±。筒押えの上に載る長さ
FOAM_XC = 20.0                           # 浮力材の中心の前後位置。前後の釣合いをここで取る（バッテリは基板に当たるので動かさない）
BALLAST_L, BALLAST_T, BALLAST_W = 200.0, 6.0, 50.0   # SUS304 フラットバー 6×50 を切断
BALLAST_HOLE_X, BALLAST_Z = 80.0, 25.0   # 固定穴の前後 ±、左右位置 ±（水平スラスタの取付ねじを避けて中央寄り）
BALLAST_XC = -50.0                       # バラスト中心の前後位置。前後の水平スラスタの取付ねじ（x = ±154〜186）の頭に乗らない範囲 ±50 に収める
BALLAST_N = 1                            # 片舷あたりの重ね枚数。浮力釣合いの計算で決める
BALLAST_TOP = DECK_TOP + BALLAST_N * BALLAST_T

# ---------------------------------------------------------------- マニピュレータ（1 自由度グリッパ）
# 水深定格のあるサーボを底板上のアーム板に載せて固定し、出力円板と反対側の従動軸に付けた 2 枚の可動爪を
# アーム板の先端（固定の下あご）へ向けて閉じる。板物はフレームと同じ HDPE t10 から切り出す。
# サーボ: ROVMaker RM-SV-40（AliExpress「AI Robot Store」、2026-11-25 に在庫 985 個を確認）。
#         [図面] 使用水深 300 m、定格 12 V、ピーク 4.3 A、動作トルク 1.5 N·m、ピーク 3.0 N·m、PWM 500〜2500 µs、
#         360 g、ケーブル Ø4×0.7 m、本体 66（軸方向）×55.5×35.5、片側に出力円板 Ø30、反対側に従動軸 Ø30、全長 80.1
MANIP_X = 316.0                          # サーボ軸の前後位置（爪の回転中心）
ARM_Y = DECK_TOP + PLATE_T / 2           # アーム板の板厚中心（底板の上に重ねる）
ARM_TOP = ARM_Y + PLATE_T / 2
ARM_BOTTOM = ARM_Y - PLATE_T / 2
ARM_BACK, ARM_FRONT, ARM_HALF_W = 166.0, 100.0, 38.0     # サーボ軸から後端・前端（下あごの先）まで、サーボを載せる部分の半幅（爪の内面 40.05 より内側）
ARM_NECK, ARM_STEM_W = 76.0, 36.0        # 幅が変わる位置（サーボ軸から後ろ）、底板に載る部分の半幅（スラスタ取付ねじを避ける）
ARM_R = 10.0
ARM_BOLT_X1, ARM_BOLT_X2, ARM_BOLT_Z = 160.0, 195.0, 22.0   # 底板への固定 M5×4（機体座標）
SERVO_BODY_L, SERVO_W, SERVO_HT = 66.0, 35.5, 55.5       # [図面] 本体 軸方向の長さ × 幅（前後）× 高さ
SERVO_AX_TOP = 18.1                      # [図面] 軸からケーブル側の面（上面）まで
SERVO_AX_BOTTOM = SERVO_HT - SERVO_AX_TOP                # 軸から取付面（下面）まで
SERVO_DISC_D, SERVO_DISC_PCD = 30.0, 24.0                # [図面] 出力円板・従動軸の径、4-M4 深さ 5 の PCD
SERVO_IDLER_T = 5.1                      # [図面] 従動軸の出っ張り
SERVO_DISC_T = 80.1 - SERVO_BODY_L - SERVO_IDLER_T       # [図面] 全長 80.1 から。出力円板 厚さ 8 と本体とのすき間 1 を含む
SERVO_ZC = -(SERVO_DISC_T - SERVO_IDLER_T) / 2           # 本体の軸方向中心の左右位置。爪の取付面を左右対称にするため従動軸側へ寄せる
SERVO_HOLE_P = 18.0                      # [図面] 取付ねじ M3 深さ 5（下面 6 個）の幅方向ピッチ
SERVO_HOLE_Z1 = SERVO_ZC - SERVO_BODY_L / 2 + 10.0       # [図面] 取付ねじの軸方向位置。本体の従動軸側の端から 10、25、40
SERVO_HOLE_Z2 = SERVO_HOLE_Z1 + 15.0
SERVO_HOLE_Z3 = SERVO_HOLE_Z2 + 15.0
SERVO_GLAND_POS = -SERVO_BODY_L / 2 + 51.0               # [図面] ケーブルグランドの軸方向位置（本体中心から。従動軸側の端から 51）
SERVO_GLAND_D, SERVO_GLAND_H = 12.0, 69.0 - SERVO_HT     # グランドの太さ（[仮] 図からの目測）、高さ（[図面] 全高 69 から）
SERVO_GLAND_SPAN = 2 * (SERVO_AX_TOP + SERVO_GLAND_H)    # 外形モデルでグランドを軸から上下対称に押し出す長さ（下側は本体内）
SERVO_AXIS_Y = ARM_TOP + SERVO_AX_BOTTOM                 # サーボ軸の高さ
SERVO_TOP = ARM_TOP + SERVO_HT           # 本体上面
SERVO_MASS = 0.36                        # [図面] kg
SERVO_TORQUE = 1.5                       # [図面] 動作トルク N·m（ピーク 3.0）
SERVO_CABLE_D = 4.0                      # [図面]
SERVO_CABLE_LEN = 700.0                  # [図面] 付属ケーブルの長さ。後端蓋まで届かないので延長する
JAW_FACE_IN = SERVO_BODY_L / 2 + (SERVO_DISC_T + SERVO_IDLER_T) / 2   # 可動爪の取付面（内面）±
JAW_Z = JAW_FACE_IN + PLATE_T / 2        # 可動爪の板厚中心 ±
JAW_FACE = JAW_Z + PLATE_T / 2           # 可動爪の外面 ±
JAW_HUB, JAW_LEN, JAW_TIP = 22.0, 100.0, 8.0             # 回転中心まわりの半幅、中心から先端まで、先端の上縁
JAW_BAR_X, JAW_BAR_Y = 90.0, -15.0       # 左右の爪をつなぐ棒 M5 の位置（回転中心から）
JAW_BAR_LEN = 125.0
JAW_R = 3.0

# ---------------------------------------------------------------- ハーネス
CABLE_RHO = 1300.0                       # [仮] ケーブルの見かけ密度 kg/m3
PEN_END_X = -(HULL_LEN / 2 + CAP_PLATE_T + PEN_OUT)      # ペネトレータの外側の端（ケーブルが入る位置）
HARNESS_LOOP_X = -302.0                  # 後端でケーブルを折り返す位置（側板の後端 -320 より内側、曲げ半径 約 35）
