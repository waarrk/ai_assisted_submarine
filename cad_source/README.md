# メーカー配布の 3D データ

購入品は外形の代用モデルではなく、メーカーが配布している 3D データを取り込んで使う（干渉確認の精度のため）。
`src/uwd01/build.py` が、ここのファイルを原点と向きをそろえて `cad/00_既製品/` の部品にする。

| ファイル | 品目 | 入手元（2026-11-25 取得） |
|---|---|---|
| `vendor/U2_Mini.igs` | ApisQueen U2 Mini 水中スラスタ | underwaterthruster.com の商品ページ「3D Drawing Download」 |
| `vendor/WLP-M10-7.5MM-PUBLIC.SLDPRT` ほか | Blue Robotics WetLink ペネトレータ M10 | cad.bluerobotics.com（商品ページ Technical Details） |
| `vendor/A3C-50DA-2DSA.stp` | ヒロセ電機 A3C-50DA-2DSA(71) 50 ピンコネクタ | hirose.com の製品ページ「3D model (STEP)」 |

配布データの利用条件は各社のサイトに従う。再配布はしない前提で、リポジトリを公開する場合はこのフォルダを除く。

データが見つからず、寸法図から作図しているもの: ROVMaker 水中サーボ、本多通信工業 LPC-50M2LG（差し込み基板側のコネクタ、未作図）、LiPo バッテリ。
