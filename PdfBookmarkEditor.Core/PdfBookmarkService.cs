using iText.Commons.Exceptions;
using iText.Kernel.Exceptions;
using iText.Kernel.Pdf;
using iText.Kernel.Pdf.Navigation;

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
/// iText を用いた PDF しおり(アウトライン)の読み書き。
/// 保存はしおりのみ差し替え、本文・注釈・メタデータは変更しない。
/// </summary>
public static class PdfBookmarkService
{
    /// <summary>PDFを読み込み、ページ数としおり階層を返す。</summary>
    /// <exception cref="PdfEncryptedException">パスワード付きPDFの場合。</exception>
    /// <exception cref="PdfLoadException">破損・非PDFなど読み込み不能の場合。</exception>
    public static PdfDocumentInfo Load(string path)
    {
        try
        {
            using var pdf = new PdfDocument(new PdfReader(path));
            int pageCount = pdf.GetNumberOfPages();
            var bookmarks = new List<BookmarkNode>();
            var root = pdf.GetOutlines(true);
            if (root != null)
            {
                foreach (var child in root.GetAllChildren())
                {
                    bookmarks.Add(ReadOutline(child, pdf));
                }
            }
            return new PdfDocumentInfo(pageCount, bookmarks);
        }
        catch (BadPasswordException e)
        {
            throw new PdfEncryptedException(path, e);
        }
        catch (Exception e) when (e is ITextException or IOException)
        {
            throw new PdfLoadException(path, e);
        }
    }

    /// <summary>
    /// sourcePath のPDFのしおりを bookmarks で差し替えて destPath に保存する。
    /// destPath が sourcePath と同一の場合は一時ファイル経由で安全に置換する。
    /// </summary>
    /// <exception cref="BookmarkValidationException">タイトル空・ページ範囲外がある場合。</exception>
    /// <exception cref="PdfSaveException">書き込みに失敗した場合。</exception>
    public static void Save(string sourcePath, string destPath, IReadOnlyList<BookmarkNode> bookmarks)
    {
        // 常に一時ファイルへ書き出し、成功時のみ destPath へ置換する。
        // 途中失敗しても既存の destPath(= sourcePath の場合を含む)を壊さない。
        string writePath = destPath + ".tmp-" + Guid.NewGuid().ToString("N");
        try
        {
            using (var pdf = new PdfDocument(new PdfReader(sourcePath), new PdfWriter(writePath)))
            {
                Validate(bookmarks, pdf.GetNumberOfPages());

                // 既存アウトラインを取り除いてから空のルートを作り直す
                pdf.GetCatalog().GetPdfObject().Remove(PdfName.Outlines);
                var root = pdf.GetOutlines(true)
                    ?? throw new InvalidOperationException("アウトラインルートを作成できません。");
                foreach (var node in bookmarks)
                {
                    WriteOutline(root, node, pdf);
                }
            }

            File.Move(writePath, destPath, overwrite: true);
        }
        catch (BookmarkValidationException)
        {
            CleanupTemp(writePath);
            throw;
        }
        catch (Exception e) when (e is ITextException or IOException or UnauthorizedAccessException)
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

    private static BookmarkNode ReadOutline(PdfOutline outline, PdfDocument pdf)
    {
        var content = outline.GetContent();
        int flags = content.GetAsNumber(PdfName.F)?.IntValue() ?? 0;
        var count = content.GetAsNumber(PdfName.Count);

        var node = new BookmarkNode
        {
            Title = outline.GetTitle(),
            Page = ResolvePage(outline, pdf),
            Italic = (flags & 1) != 0,
            Bold = (flags & 2) != 0,
            Expanded = count != null && count.IntValue() > 0,
        };
        foreach (var child in outline.GetAllChildren())
        {
            node.Children.Add(ReadOutline(child, pdf));
        }
        return node;
    }

    /// <summary>
    /// しおりのジャンプ先をページ番号(1始まり)へ解決する。
    /// /Dest、名前付き宛先、/A の GoTo アクションに対応。解決不能なら null。
    /// </summary>
    private static int? ResolvePage(PdfOutline outline, PdfDocument pdf)
    {
        var dest = outline.GetDestination();
        if (dest == null)
        {
            var action = outline.GetContent().GetAsDictionary(PdfName.A);
            if (action != null && PdfName.GoTo.Equals(action.GetAsName(PdfName.S)))
            {
                var d = action.Get(PdfName.D);
                if (d != null)
                {
                    dest = PdfDestination.MakeDestination(d);
                }
            }
        }
        if (dest == null)
        {
            return null;
        }

        try
        {
            var names = pdf.GetCatalog().GetNameTree(PdfName.Dests);
            var pageObj = dest.GetDestinationPage(names);
            if (pageObj is PdfDictionary pageDict)
            {
                int number = pdf.GetPageNumber(pageDict);
                return number >= 1 ? number : null;
            }
        }
        catch (PdfException)
        {
            // 壊れた宛先は「ページ未設定」として扱う
        }
        return null;
    }

    private static void WriteOutline(PdfOutline parent, BookmarkNode node, PdfDocument pdf)
    {
        var outline = parent.AddOutline(node.Title);
        if (node.Page is int pageNumber)
        {
            var page = pdf.GetPage(pageNumber);
            // [page /XYZ null top null] : ページ上端へ、左位置とズームは現状維持
            var destArray = new PdfArray();
            destArray.Add(page.GetPdfObject());
            destArray.Add(PdfName.XYZ);
            destArray.Add(PdfNull.PDF_NULL);
            destArray.Add(new PdfNumber(page.GetPageSize().GetTop()));
            destArray.Add(PdfNull.PDF_NULL);
            outline.AddDestination(PdfDestination.MakeDestination(destArray));
        }

        int style = (node.Italic ? PdfOutline.FLAG_ITALIC : 0) | (node.Bold ? PdfOutline.FLAG_BOLD : 0);
        if (style != 0)
        {
            outline.SetStyle(style);
        }
        outline.SetOpen(node.Expanded);

        foreach (var child in node.Children)
        {
            WriteOutline(outline, child, pdf);
        }
    }
}
