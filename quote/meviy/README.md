# meviy 加工品 自動見積もり

UWD-01 の加工品を [meviy](https://meviy.misumi-ec.com/ja-jp/app/fa/mypage) にアップロードし、見積り（単価・納期）を
読み取って表にするためのフォルダです。ミスミの規格部品（購入品）の見積りは対象外で、そちらは RAPiD Design を使います。

## 守ること

- **注文はしない。** スクリプトが行うのは、フォルダ作成・アップロード・見積条件の読み取りまで。
  「注文」「カート」「購入」などの文言を含むボタンは押さない（`meviy_browser.py` の `FORBIDDEN`）。
- **meviy 側では必ずフォルダを作って入れる。** フォルダ名は `<日付>_UWD-01`（`upload/` の下のフォルダ名と同じ）。
  マイページの直下にファイルを置かない。
- ログインは人が行う。パスワードはスクリプトにも設定ファイルにも書かない。
  ログイン後の状態は `.profile/`（Git 管理外）に残る。
- meviy の利用規約で自動操作が許されているかは確認できていない。利用の可否は利用者が判断する。
  アクセスは人が操作する程度の頻度にとどめる。

## ファイル

| ファイル | 役割 |
|---|---|
| `parts.csv` | 見積対象の一覧。部品、数量、meviy の区分、材質、表面処理、対象かどうか |
| `export_for_meviy.py` | 対象部品を STEP に書き出し、SLDPRT と一緒に `upload/<日付>_UWD-01/` へ置く |
| `meviy_browser.py` | 専用 Chrome の起動、ログイン待ち、画面の記録 |
| `upload/` | アップロードするファイル（生成物、Git 管理外） |
| `explore/` | 画面構成を調べたときのスクリーンショットと要素一覧（Git 管理外） |
| `result/` | 読み取った見積り（CSV） |

## 手順

```powershell
.venv\Scripts\pip install playwright
.venv\Scripts\python quote\meviy\export_for_meviy.py    # アップロード用ファイルを書き出す
.venv\Scripts\python quote\meviy\meviy_browser.py       # 初回だけ: 開いた Chrome でログインする
```

## 見積対象の区分

`parts.csv` の「見積対象」は、○ = そのまま見積り、△ = meviy の対応範囲（寸法・材質）を確かめながら見積り、× = 対象外。
HDPE の板物は、meviy の取扱材料に無ければ POM で代替見積りを取り、ウォータージェット加工先の見積りと比べる。
