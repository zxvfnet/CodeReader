# 開発者向けメモ

## ステップ1：デコーダ比較（2026-10-18）

### 実行方法
```
pip install pyzbar zxing-cpp segno Pillow
python scripts/generate_samples.py   # scripts/samples/ にサンプル画像と expected.json を生成
python scripts/compare_decoders.py   # pyzbar / zxing-cpp / zxing+2倍拡大 を比較
```
Linux で pyzbar を使う場合は libzbar0 が別途必要。
Windows では pip wheel に libzbar-64.dll が同梱されるが、その依存として Visual C++ 2013 再頒布可能パッケージ（x64）が必要。
入っていないと `FileNotFoundError: Could not find module 'libiconv.dll'` / `libzbar-64.dll` で import に失敗する（pyzbar の README に記載、2026-10-18 に WinPython 3.14 で発生）。

### 検証環境
Linux（クラウド）, Python 3.13, zxing-cpp 3.1.1, pyzbar 0.1.9, segno 1.6.6。Windows / WinPython では未検証。

### 結果（正解数 / 期待数）
| 画像 | pyzbar | zxing-cpp | zxing+2倍拡大 |
|---|---|---|---|
| 01_clean（QR×3, Code128, EAN13, Code39, DataMatrix） | 6/7 | 7/7 | 7/7 |
| 02_photo_like（7°回転・ぼかし・ノイズ・JPEG） | 5/7 + 誤読1 | 4/7 | 6/7 + 誤読1 |
| 03_small（1/2縮小） | 6/7 | 5/7 | 7/7 |
| 04_no_code | 0/0 | 0/0 | 0/0 |

### わかったこと
- pyzbar は DataMatrix を読めない（3画像すべてで未検出）。
- zxing-cpp はそのままだと細い1次元バーコードを取りこぼすが、2倍に拡大した画像でも読むと回復する。
- 日本語 QR は UTF-8・漢字モード（Shift_JIS）とも、きれいな画像では両ライブラリで文字化けなし。
- ぼやけた画像では EAN13 がチェックディジットを通過する別の値に誤読されることがある（両ライブラリで発生）。
  本番では「位置が重なる同種コードで値が食い違う」場合の扱いを決める必要がある。
- 2倍拡大の併用で処理時間は約5〜8倍（1800×1100画像で約0.3秒）。

## ステップ2：読み取り処理と TSV 出力（2026-10-18）

### 構成
```
code_reader/
  decoder.py     画像1枚 → DecodedCode のリスト（原寸＋2倍拡大の2回読み、位置で統合）
  files.py       ファイル／フォルダ展開（フォルダは1階層のみ）、一括読み取り（壊れた画像はエラー行にして続行）
  csv_writer.py  CSV 出力（BOM付きUTF-8、CRLF）※当初は TSV
  __main__.py    GUIなしで確認するためのCLI
tests/
  support/code_images.py  テスト用のコード画像生成（複数テストで共用）
```

### 使い方
```
pip install -r requirements.txt
python -m code_reader 画像やフォルダ ... -o result.csv
python -m pytest --disable-warnings -q
```

### 設計メモ
- 2回の読み取りで同じ位置・同じ種別なのに値が違う場合は、原寸の値を残し「備考」に要確認と拡大時の値を書く。
  拡大時にしか見つからなかったコードは食い違いを検出できない（サンプルの写真風画像の EAN13 誤読はこのケース）。
- Excel 対策：数字だけの値は `="0012"` 形式（先頭0の欠落・指数表示を防ぐ）、`= + - @` で始まる値は先頭に `'` を付ける（数式インジェクション対策）。
  `="..."` はダブルクォートで囲むと Excel が数式として扱わない可能性があるため、タブ・改行を含むセルだけを囲む独自の書き出しにしている。
  Excel 上の表示は 2026-10-18 にユーザーが Windows の Excel で確認済み（TSV 時点）。
- 行の並びは各画像内で上→下、左→右。

## ステップ3：GUI（2026-10-18）

### 起動
```
pip install -r requirements.txt
python -m code_reader.gui        # またはエクスプローラーで run_gui.pyw をダブルクリック
```

### 構成
- `code_reader/gui.py`：ttkbootstrap（テーマ bootstrap-light）＋ tkinterdnd2 のドラッグ＆ドロップ。
  - 左：画像ファイル一覧（件数・状態）、右上：プレビュー（検出位置を枠表示、選択中はオレンジ）、右下：読み取り結果（ダブルクリックでコピー）。
  - Delete キーで選択ファイルを一覧から外す。保存後に「開きますか？」で Excel 等を起動（Windows のみ）。
- 読み取りは別スレッドで実行し、`queue` 経由で結果を受け取りメインスレッドの `after` で反映（Tk はスレッドセーフでないため）。
  処理中は追加・クリア・保存ボタンを無効化する。
- `run_gui.pyw`：コンソールなしで起動するためのランチャー。
- `scripts/gui_screenshot.py`：サンプルを読み込んだ画面を自動でキャプチャ（レイアウト確認用）。

### 注意
- ttkbootstrap 2.x では旧テーマ名（flatly など）が非推奨。2.x のテーマ名（`Style().theme_names()`）を使う。
- tkinterdnd2 のルートは `TkinterDnD.Tk()`。その上で `tb.Style(theme=...)` を作るとテーマが適用される。
- 画面テストは表示環境がないと skip される。Linux では `xvfb-run -a python -m pytest` で実行できる。
- 検証は Linux（Python 3.12, ttkbootstrap 2.2.3, tkinterdnd2 0.6.4, Xvfb）。Windows 実機では未検証。

## 変更：出力を TSV から CSV へ（2026-10-18）
- `tsv_writer.py` → `csv_writer.py`（`write_csv` / `to_csv_field`）、区切りはカンマ。
- クォートするのは「カンマ・改行を含む」または「`"` で始まる」セルだけ（`="0012"` を囲まないため）。タブは CSV では普通の文字として扱う。
- 文字コード（BOM付きUTF-8）・改行（CRLF）・Excel 対策（`="..."`、先頭 `'`）は TSV と同じ。

## 追加：検出数上限の警告（2026-10-18）
- zxing-cpp の Python `read_barcodes` は1回の呼び出しで最大255個（`wrappers/python/zxing.cpp` v3.1.1 の `max_number_of_symbols = 0xff`、Python から変更不可）。
  実測でも 300 個並べた画像で 255 個まで（2倍拡大パスも同じ）。
- `decoder.MAX_SYMBOLS_PER_PASS = 255`。`files.read_files` で検出数が 255 以上なら `FileResult.warning` に `NOTE_LIMIT` を入れる。
- CSV ではそのファイルの先頭に警告行を1行追加、GUI では状態を「要確認」にし、結果表の先頭に警告行を表示。
- ユーザー確認（2026-10-18）：1枚に255個を超えるコードが写ることはない → タイル分割は実装しない。

## ステップ4：exe 化（2026-10-19）
- `code_reader.spec`（PyInstaller、1フォルダ形式、コンソールなし、exe 名 `CodeReader`）。`build_exe.bat` で依存インストール → pytest → ビルド。
- tkinterdnd2 の tkdnd DLL は pyinstaller-hooks-contrib の `hook-tkinterdnd2.py`、ttkbootstrap の画像は ttkbootstrap 同梱フックが自動で収集する。
- `PIL._tkinter_finder` は hiddenimports 必須。無いと起動時に ttkbootstrap のテーマ生成で
  `ModuleNotFoundError: No module named 'PIL._tkinter_finder'` で落ちた（Linux の試しビルドで確認）。
- 1ファイル形式（--onefile）にしない理由：起動のたびに一時フォルダへ展開されて遅く、ウイルス対策ソフトの誤検知も起きやすいため。
- 試しビルド：Linux（Python 3.12, PyInstaller 6.22.3）でビルド・起動・サンプル読み取りまで確認、約 57MB。Windows でのビルドは未検証。
- bat のメッセージは英語（ASCII）。cmd のコードページで日本語が化けるのを避けるため。

### トラブル：tkinterdnd2 の `win-x64-tcl9/tkdnd.tcl` が見つからない（2026-10-19）
- 症状：WinPython 3.14（Tcl/Tk 9）で pytest 中に
  `TclError: couldn't read file ...\tkinterdnd2\tkdnd\win-x64-tcl9/tkdnd.tcl`。
- tkinterdnd2 0.6.0〜0.6.4 の wheel にはいずれも同ファイルが含まれる（確認済み）。
  原因は pip 更新時の不完全なインストールと推測（Python 実行中でファイルがロックされていた可能性。未確定）。
- 対処：Python のウィンドウをすべて閉じてから
  `python -m pip install --force-reinstall --no-deps tkinterdnd2` → 解消（ユーザー確認済み）。
