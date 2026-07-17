using iText.Kernel.Pdf;
using iText.Kernel.Pdf.Navigation;

namespace PdfBookmarkEditor.Core.Tests;

/// <summary>テスト用PDFを生成するヘルパー。</summary>
public static class TestPdf
{
    /// <summary>指定ページ数の空PDFを作成する。</summary>
    public static string CreateBlank(string dir, int pageCount, string name = "blank.pdf")
    {
        string path = Path.Combine(dir, name);
        using var pdf = new PdfDocument(new PdfWriter(path));
        for (int i = 0; i < pageCount; i++)
        {
            pdf.AddNewPage();
        }
        return path;
    }

    /// <summary>
    /// 3階層のしおり付きPDF(5ページ)を作成する。構成:
    ///   第1章(p1, 太字, 展開)
    ///     1.1節(p2, 斜体)
    ///       1.1.1項(p3)
    ///   第2章(p4)
    /// </summary>
    public static string CreateWithOutlines(string dir, string name = "outlined.pdf")
    {
        string path = Path.Combine(dir, name);
        using var pdf = new PdfDocument(new PdfWriter(path));
        for (int i = 0; i < 5; i++)
        {
            pdf.AddNewPage();
        }
        var root = pdf.GetOutlines(false);

        var chapter1 = root.AddOutline("第1章 はじめに");
        chapter1.AddDestination(PdfExplicitDestination.CreateFit(pdf.GetPage(1)));
        chapter1.SetStyle(PdfOutline.FLAG_BOLD);
        chapter1.SetOpen(true);

        var section11 = chapter1.AddOutline("1.1節 背景");
        section11.AddDestination(PdfExplicitDestination.CreateFit(pdf.GetPage(2)));
        section11.SetStyle(PdfOutline.FLAG_ITALIC);
        section11.SetOpen(false);

        var item111 = section11.AddOutline("1.1.1項 詳細");
        item111.AddDestination(PdfExplicitDestination.CreateFit(pdf.GetPage(3)));

        var chapter2 = root.AddOutline("第2章 応用");
        chapter2.AddDestination(PdfExplicitDestination.CreateFit(pdf.GetPage(4)));

        return path;
    }

    /// <summary>名前付き宛先を使うしおりと、宛先なしのしおりを持つPDF(3ページ)。</summary>
    public static string CreateWithNamedAndMissingDest(string dir, string name = "named.pdf")
    {
        string path = Path.Combine(dir, name);
        using var pdf = new PdfDocument(new PdfWriter(path));
        for (int i = 0; i < 3; i++)
        {
            pdf.AddNewPage();
        }
        pdf.AddNamedDestination("chap2", PdfExplicitDestination.CreateFit(pdf.GetPage(2)).GetPdfObject());

        var root = pdf.GetOutlines(false);
        var named = root.AddOutline("名前付き宛先のしおり");
        named.AddDestination(new PdfStringDestination("chap2"));
        root.AddOutline("宛先なしのしおり");

        return path;
    }

    /// <summary>パスワード付き(AES-128暗号化)PDFを作成する。</summary>
    public static string CreateEncrypted(string dir, string name = "encrypted.pdf")
    {
        string path = Path.Combine(dir, name);
        var props = new WriterProperties().SetStandardEncryption(
            System.Text.Encoding.ASCII.GetBytes("user"),
            System.Text.Encoding.ASCII.GetBytes("owner"),
            EncryptionConstants.ALLOW_PRINTING,
            EncryptionConstants.ENCRYPTION_AES_128);
        using var pdf = new PdfDocument(new PdfWriter(path, props));
        pdf.AddNewPage();
        return path;
    }
}
