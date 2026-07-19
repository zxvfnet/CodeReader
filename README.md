# CodeReader

## PdfBookmarkEditor — PDFしおり編集アプリ

PDFのしおり(アウトライン)を編集・作成・追加・削除できるWindowsデスクトップアプリです。

### 構成

| プロジェクト | 内容 |
|---|---|
| `PdfBookmarkEditor.Core` | しおり操作ロジック(PDFsharp使用、クロスプラットフォーム) |
| `PdfBookmarkEditor.App` | WPF GUI(Windows専用) |
| `PdfBookmarkEditor.Core.Tests` | xUnit 単体テスト |

### 主な機能

- PDFを開いて既存しおりを階層ツリー表示
- しおりの追加(同階層/子)・削除・上下移動・階層の上げ下げ
- タイトル / ジャンプ先ページ / 太字 / 斜体 / 初期展開状態の編集
- しおり階層のJSON書き出し・取り込み(一括編集用、形式 `PdfBookmarkEditor/1`)
- 保存は常に一時ファイル経由で行い、失敗時に元ファイルを壊さない

### ビルドと実行(Windows)

```powershell
dotnet build -c Release
dotnet run --project PdfBookmarkEditor.App
```

.NET 10 SDK が必要です。Linux/macOS では GUI は実行できませんが、
`EnableWindowsTargeting` によりビルドとテストは可能です。

### テスト

```bash
dotnet test
```

テストはPDFsharpでテスト用PDF(しおり付き・宛先なし・暗号化など)を生成し、
読取・編集・保存・再読込の往復とJSON入出力を検証します。

### 操作方法

1. `Ctrl+O` でPDFを開く
2. 左のツリーでしおりを選択し、右のパネルでタイトル・ページ等を編集
3. ツールバーで追加(`Ins`)/子を追加/削除(`Del`)/移動(`Alt+矢印`)
4. `Ctrl+Shift+S` で名前を付けて保存(元ファイル上書き時は確認あり)
5. 大量編集は「ファイル → JSON書き出し」→ テキスト編集 → 「JSON取り込み」

JSON形式の例:

```json
{
  "format": "PdfBookmarkEditor/1",
  "bookmarks": [
    {
      "title": "第1章 はじめに",
      "page": 1,
      "bold": true,
      "expanded": true,
      "children": [
        { "title": "1.1 背景", "page": 2 }
      ]
    }
  ]
}
```

`page` を `null` または省略すると「ページ未設定」のしおりになります。

### 制限事項

- パスワード付き(暗号化)PDFは開けません
- ジャンプ位置は「指定ページの先頭」固定です(位置・倍率の指定は不可)
- Undo/Redoは未対応です(「編集を破棄して再読込」で代替)
- しおりのジャンプ先は**明示的な宛先のみ**ページ番号に解決します。他ツールが作った
  「名前付き宛先(named destination)」を使うしおりは「ページ未設定」として読み込まれます
- 保存時はPDFsharpがファイル全体を書き直します(タグ付きPDF等の一部の高度な構造は
  保持されない場合があります)

### ライセンスに関する注意

PDF処理に [PDFsharp](https://www.pdfsharp.net/) 6.2.4(**MITライセンス**)を使用しています。
商用・クローズドソースを含め自由に利用・配布できます。
