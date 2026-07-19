using PdfSharp.Pdf;
using PdfSharp.Pdf.IO;

namespace PdfBookmarkEditor.Core;

/// <summary>PDF読み込み結果。</summary>
public class PdfDocumentInfo
{
    public int PageCount { get; }
    public List<BookmarkNode> Bookmarks { get; }

    public PdfDocumentInfo(int pageCount, List<BookmarkNode> bookmarks)
    {
        PageCount = pageCount;
        Bookmarks = bookmarks;
    }
}

/// <summary>
/// PDFsharp を用いた PDF しおり(アウトライン)の読み書き。
/// 保存はしおりを差し替えてファイル全体を書き直す(本文・ページは保持)。
/// </summary>
public static class PdfBookmarkService
{
    /// <summary>PDFを読み込み、ページ数としおり階層を返す。</summary>
    /// <exception cref="PdfEncryptedException">パスワード付きPDFの場合。</exception>
    /// <exception cref="PdfLoadException">破損・非PDFなど読み込み不能の場合。</exception>
    public static PdfDocumentInfo Load(string path)
    {
        PdfDocument doc = OpenForModify(path);
        using (doc)
        {
            int pageCount = doc.PageCount;
            var pageIndex = BuildPageIndex(doc);
            var bookmarks = new List<BookmarkNode>();
            foreach (var outline in doc.Outlines)
            {
                bookmarks.Add(ReadOutline(outline, pageIndex));
            }
            return new PdfDocumentInfo(pageCount, bookmarks);
        }
    }

    /// <summary>
    /// sourcePath のPDFのしおりを bookmarks で差し替えて destPath に保存する。
    /// 一時ファイルへ書き出してから置換するため、失敗時に既存ファイルを壊さない
    /// (destPath が sourcePath と同一の場合も安全)。
    /// </summary>
    /// <exception cref="BookmarkValidationException">タイトル空・ページ範囲外がある場合。</exception>
    /// <exception cref="PdfEncryptedException">パスワード付きPDFの場合。</exception>
    /// <exception cref="PdfSaveException">書き込みに失敗した場合。</exception>
    public static void Save(string sourcePath, string destPath, IReadOnlyList<BookmarkNode> bookmarks)
    {
        string writePath = destPath + ".tmp-" + Guid.NewGuid().ToString("N");
        try
        {
            using (var doc = OpenForModify(sourcePath))
            {
                Validate(bookmarks, doc.PageCount);

                doc.Outlines.Clear();
                foreach (var node in bookmarks)
                {
                    WriteOutline(doc.Outlines, node, doc);
                }
                doc.Save(writePath);
            }
            File.Move(writePath, destPath, overwrite: true);
        }
        catch (PdfBookmarkException)
        {
            CleanupTemp(writePath);
            throw;
        }
        catch (Exception e)
        {
            CleanupTemp(writePath);
            throw new PdfSaveException(destPath, e);
        }
    }

    /// <summary>タイトル・ページ番号を検証し、問題があれば全件まとめて例外にする。</summary>
    public static void Validate(IReadOnlyList<BookmarkNode> bookmarks, int pageCount)
    {
        var errors = new List<string>();
        ValidateNodes(bookmarks, pageCount, "", errors);
        if (errors.Count > 0)
        {
            throw new BookmarkValidationException(errors);
        }
    }

    // ---- 読み込み補助 ----------------------------------------------------

    /// <summary>PDFを編集モードで開く。暗号化・破損を専用例外に変換する。</summary>
    private static PdfDocument OpenForModify(string path)
    {
        try
        {
            return PdfReader.Open(path, PdfDocumentOpenMode.Modify);
        }
        catch (PdfReaderException e) when (IsPasswordError(e))
        {
            throw new PdfEncryptedException(path, e);
        }
        catch (Exception e)
        {
            throw new PdfLoadException(path, e);
        }
    }

    private static bool IsPasswordError(Exception e) =>
        e.Message.Contains("password", StringComparison.OrdinalIgnoreCase);

    /// <summary>ページオブジェクト→ページ番号(1始まり)の対応表を作る。</summary>
    private static Dictionary<PdfPage, int> BuildPageIndex(PdfDocument doc)
    {
        var map = new Dictionary<PdfPage, int>(ReferenceEqualityComparer.Instance);
        for (int i = 0; i < doc.PageCount; i++)
        {
            map[doc.Pages[i]] = i + 1;
        }
        return map;
    }

    private static BookmarkNode ReadOutline(PdfOutline outline, Dictionary<PdfPage, int> pageIndex)
    {
        var node = new BookmarkNode
        {
            Title = outline.Title ?? "",
            Page = ResolvePage(outline, pageIndex),
            Bold = outline.Style is PdfOutlineStyle.Bold or PdfOutlineStyle.BoldItalic,
            Italic = outline.Style is PdfOutlineStyle.Italic or PdfOutlineStyle.BoldItalic,
            Expanded = IsExpanded(outline),
        };
        foreach (var child in outline.Outlines)
        {
            node.Children.Add(ReadOutline(child, pageIndex));
        }
        return node;
    }

    /// <summary>
    /// しおりのジャンプ先ページ(1始まり)を返す。明示的宛先のみ解決し、
    /// 名前付き宛先など解決不能なものは null(ページ未設定)とする。
    /// </summary>
    private static int? ResolvePage(PdfOutline outline, Dictionary<PdfPage, int> pageIndex)
    {
        var page = outline.DestinationPage;
        if (page != null && pageIndex.TryGetValue(page, out int number))
        {
            return number;
        }
        return null;
    }

    /// <summary>
    /// PDFsharp の Opened プロパティは /Count を反映しないため、
    /// アウトライン辞書の /Count の符号(正=展開)から自前で判定する。
    /// </summary>
    private static bool IsExpanded(PdfOutline outline)
    {
        return outline.Elements.ContainsKey("/Count")
            && outline.Elements.GetInteger("/Count") > 0;
    }

    // ---- 書き込み補助 ----------------------------------------------------

    private static void WriteOutline(PdfOutlineCollection parent, BookmarkNode node, PdfDocument doc)
    {
        PdfPage? page = node.Page is int pageNumber ? doc.Pages[pageNumber - 1] : null;
        var style = (node.Bold, node.Italic) switch
        {
            (true, true) => PdfOutlineStyle.BoldItalic,
            (true, false) => PdfOutlineStyle.Bold,
            (false, true) => PdfOutlineStyle.Italic,
            _ => PdfOutlineStyle.Regular,
        };

        // page が null(ページ未設定)でも PDFsharp は宛先なしのしおりとして受け付ける。
        var outline = parent.Add(node.Title, page!, node.Expanded, style);

        foreach (var child in node.Children)
        {
            WriteOutline(outline.Outlines, child, doc);
        }

        // 展開/折りたたみは /Count の符号で表す(PDFsharp は自動出力しない)。
        // 絶対値は展開時に見える子孫数。子を持つノードにのみ書く。
        if (node.Children.Count > 0)
        {
            int visible = VisibleDescendantCount(node);
            outline.Elements.SetInteger("/Count", node.Expanded ? visible : -visible);
        }
    }

    /// <summary>node を展開したときにその下に表示される項目数(子孫の展開状態を考慮)。</summary>
    private static int VisibleDescendantCount(BookmarkNode node)
    {
        int total = 0;
        foreach (var child in node.Children)
        {
            total += 1;
            if (child.Expanded && child.Children.Count > 0)
            {
                total += VisibleDescendantCount(child);
            }
        }
        return total;
    }

    // ---- 検証 ------------------------------------------------------------

    private static void ValidateNodes(
        IReadOnlyList<BookmarkNode> nodes, int pageCount, string parentPath, List<string> errors)
    {
        for (int i = 0; i < nodes.Count; i++)
        {
            var node = nodes[i];
            string path = parentPath.Length == 0 ? $"{i + 1}" : $"{parentPath}-{i + 1}";
            if (string.IsNullOrWhiteSpace(node.Title))
            {
                errors.Add($"しおり {path}: タイトルが空です。");
            }
            if (node.Page is int page && (page < 1 || page > pageCount))
            {
                errors.Add($"しおり {path} 「{node.Title}」: ページ {page} は範囲外です(1〜{pageCount})。");
            }
            ValidateNodes(node.Children, pageCount, path, errors);
        }
    }

    private static void CleanupTemp(string writePath)
    {
        try { File.Delete(writePath); } catch { /* 後始末失敗は無視 */ }
    }
}
