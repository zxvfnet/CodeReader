using PdfSharp.Pdf;

namespace PdfBookmarkEditor.Core.Tests;

/// <summary>テスト用PDFを PDFsharp で生成するヘルパー。</summary>
public static class TestPdf
{
    /// <summary>指定ページ数の空PDFを作成する。</summary>
    public static string CreateBlank(string dir, int pageCount, string name = "blank.pdf")
    {
        string path = Path.Combine(dir, name);
        using var doc = new PdfDocument();
        for (int i = 0; i < pageCount; i++)
        {
            doc.AddPage();
        }
        doc.Save(path);
        return path;
    }

    /// <summary>
    /// 3階層のしおり付きPDF(5ページ)を作成する。構成:
    ///   第1章(p1, 太字, 展開)
    ///     1.1節(p2, 斜体, 折りたたみ)
    ///       1.1.1項(p3)
    ///   第2章(p4)
    /// 展開状態は実PDF同様 /Count の符号で表現する。
    /// </summary>
    public static string CreateWithOutlines(string dir, string name = "outlined.pdf")
    {
        string path = Path.Combine(dir, name);
        using var doc = new PdfDocument();
        for (int i = 0; i < 5; i++)
        {
            doc.AddPage();
        }

        var chapter1 = doc.Outlines.Add("第1章 はじめに", doc.Pages[0], true, PdfOutlineStyle.Bold);
        var section11 = chapter1.Outlines.Add("1.1節 背景", doc.Pages[1], false, PdfOutlineStyle.Italic);
        section11.Outlines.Add("1.1.1項 詳細", doc.Pages[2]);
        doc.Outlines.Add("第2章 応用", doc.Pages[3]);

        chapter1.Elements.SetInteger("/Count", 1);   // 展開(正)
        section11.Elements.SetInteger("/Count", -1);  // 折りたたみ(負)

        doc.Save(path);
        return path;
    }

    /// <summary>
    /// ページ宛先を持つしおりと、宛先なし(ページ未設定)のしおりを持つPDF(3ページ)。
    /// </summary>
    public static string CreateWithMissingDest(string dir, string name = "missing.pdf")
    {
        string path = Path.Combine(dir, name);
        using var doc = new PdfDocument();
        for (int i = 0; i < 3; i++)
        {
            doc.AddPage();
        }
        doc.Outlines.Add("2ページ目のしおり", doc.Pages[1]);
        doc.Outlines.Add("宛先なしのしおり", null!);
        doc.Save(path);
        return path;
    }

    /// <summary>パスワード付き(暗号化)PDFを作成する。</summary>
    public static string CreateEncrypted(string dir, string name = "encrypted.pdf")
    {
        string path = Path.Combine(dir, name);
        using var doc = new PdfDocument();
        doc.AddPage();
        doc.SecuritySettings.UserPassword = "user";
        doc.SecuritySettings.OwnerPassword = "owner";
        doc.Save(path);
        return path;
    }
}
