"""meviy へアップロードする部品ファイルを書き出す。

    python quote/meviy/export_for_meviy.py

parts.csv で見積対象（○・△）になっている部品を、SOLIDWORKS で開いて STEP に書き出し、
元の SLDPRT と一緒に quote/meviy/upload/<日付>_UWD-01/ へ置く。meviy 側では同じ名前のフォルダを作って入れる。
アセンブリの穴フィーチャから反映した穴も部品に入った状態で書き出される。
"""
from __future__ import annotations

import csv
import datetime
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from swkit import NOTHING, SW  # noqa: E402
from swkit.core import _byref_int  # noqa: E402


def main():
    rows = [r for r in csv.DictReader(open(HERE / "parts.csv", encoding="utf-8")) if r["見積対象"] in ("○", "△")]
    folder = f"{datetime.date.today():%Y%m%d}_UWD-01"
    dst = HERE / "upload" / folder
    dst.mkdir(parents=True, exist_ok=True)
    sw = SW()
    try:
        out = []
        for r in rows:
            src = ROOT / r["cad"]
            doc = sw.open(src)
            sw.activate(doc)
            step = dst / f"{r['部品']}.step"
            e, w = _byref_int(), _byref_int()
            ok = doc.Extension.SaveAs(str(step), 0, 1, NOTHING, e, w)
            shutil.copy2(src, dst / src.name)
            out.append({**r, "STEP": step.name, "SLDPRT": src.name})
            print(f"{'OK ' if ok else 'NG '} {r['部品']:<8} ×{r['数量']}  {r['meviy区分']}")
        with open(dst / "upload_list.csv", "w", newline="", encoding="utf-8-sig") as f:
            w_ = csv.DictWriter(f, fieldnames=list(out[0]))
            w_.writeheader()
            w_.writerows(out)
        print(f"\n{dst}\nmeviy 側のフォルダ名: {folder}")
    finally:
        sw.restore()


if __name__ == "__main__":
    main()
