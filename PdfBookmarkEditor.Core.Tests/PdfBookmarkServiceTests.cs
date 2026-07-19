namespace PdfBookmarkEditor.Core.Tests;

public class PdfBookmarkServiceTests : IDisposable
{
    private readonly string _dir;

    public PdfBookmarkServiceTests()
    {
        _dir = Path.Combine(Path.GetTempPath(), "PdfBookmarkEditorTests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_dir);
    }

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch { }
    }

    [Fact]
    public void Load_ReadsHierarchyTitlesPagesAndStyles()
    {
        string path = TestPdf.CreateWithOutlines(_dir);

        var info = PdfBookmarkService.Load(path);

        Assert.Equal(5, info.PageCount);
        Assert.Equal(2, info.Bookmarks.Count);

        var chapter1 = info.Bookmarks[0];
        Assert.Equal("第1章 はじめに", chapter1.Title);
        Assert.Equal(1, chapter1.Page);
        Assert.True(chapter1.Bold);
        Assert.False(chapter1.Italic);
        Assert.True(chapter1.Expanded);

        var section11 = Assert.Single(chapter1.Children);
        Assert.Equal("1.1節 背景", section11.Title);
        Assert.Equal(2, section11.Page);
        Assert.True(section11.Italic);
        Assert.False(section11.Bold);
        Assert.False(section11.Expanded);

        var item111 = Assert.Single(section11.Children);
        Assert.Equal("1.1.1項 詳細", item111.Title);
        Assert.Equal(3, item111.Page);
        Assert.Empty(item111.Children);

        var chapter2 = info.Bookmarks[1];
        Assert.Equal("第2章 応用", chapter2.Title);
        Assert.Equal(4, chapter2.Page);
        Assert.Empty(chapter2.Children);
    }

    [Fact]
    public void SaveAndReload_RoundTripsAllAttributes()
    {
        string source = TestPdf.CreateWithOutlines(_dir);
        var original = PdfBookmarkService.Load(source);

        string dest = Path.Combine(_dir, "roundtrip.pdf");
        PdfBookmarkService.Save(source, dest, original.Bookmarks);
        var reloaded = PdfBookmarkService.Load(dest);

        Assert.Equal(original.PageCount, reloaded.PageCount);
        AssertTreesEqual(original.Bookmarks, reloaded.Bookmarks);
    }

    [Fact]
    public void Save_EditedTree_PersistsChanges()
    {
        string source = TestPdf.CreateWithOutlines(_dir);
        var info = PdfBookmarkService.Load(source);

        // 編集: タイトル変更、ページ変更、追加、削除、移動
        info.Bookmarks[0].Title = "第1章(改訂)";
        info.Bookmarks[0].Children[0].Page = 5;
        BookmarkTree.AddSibling(info.Bookmarks, info.Bookmarks[1],
            new BookmarkNode { Title = "付録", Page = 5, Bold = true });
        BookmarkTree.Remove(info.Bookmarks, info.Bookmarks[0].Children[0].Children[0]);
        BookmarkTree.MoveUp(info.Bookmarks, info.Bookmarks[1]);

        string dest = Path.Combine(_dir, "edited.pdf");
        PdfBookmarkService.Save(source, dest, info.Bookmarks);
        var reloaded = PdfBookmarkService.Load(dest);

        Assert.Equal(3, reloaded.Bookmarks.Count);
        Assert.Equal("第2章 応用", reloaded.Bookmarks[0].Title);
        Assert.Equal("第1章(改訂)", reloaded.Bookmarks[1].Title);
        Assert.Equal(5, reloaded.Bookmarks[1].Children[0].Page);
        Assert.Empty(reloaded.Bookmarks[1].Children[0].Children);
        Assert.Equal("付録", reloaded.Bookmarks[2].Title);
        Assert.True(reloaded.Bookmarks[2].Bold);
    }

    [Fact]
    public void Load_PdfWithoutOutlines_ReturnsEmptyAndCanAddBookmarks()
    {
        string source = TestPdf.CreateBlank(_dir, pageCount: 3);

        var info = PdfBookmarkService.Load(source);
        Assert.Equal(3, info.PageCount);
        Assert.Empty(info.Bookmarks);

        info.Bookmarks.Add(new BookmarkNode { Title = "新しいしおり", Page = 2, Expanded = true });
        info.Bookmarks[0].Children.Add(new BookmarkNode { Title = "子しおり", Page = 3 });

        string dest = Path.Combine(_dir, "added.pdf");
        PdfBookmarkService.Save(source, dest, info.Bookmarks);
        var reloaded = PdfBookmarkService.Load(dest);

        var top = Assert.Single(reloaded.Bookmarks);
        Assert.Equal("新しいしおり", top.Title);
        Assert.Equal(2, top.Page);
        Assert.True(top.Expanded);
        var child = Assert.Single(top.Children);
        Assert.Equal("子しおり", child.Title);
        Assert.Equal(3, child.Page);
    }

    [Fact]
    public void Load_OutlineWithoutDestination_BecomesPageUnset_AndSurvivesSave()
    {
        string source = TestPdf.CreateWithMissingDest(_dir);

        var info = PdfBookmarkService.Load(source);
        Assert.Equal(2, info.Bookmarks.Count);
        Assert.Equal(2, info.Bookmarks[0].Page);
        Assert.Null(info.Bookmarks[1].Page);

        string dest = Path.Combine(_dir, "unset.pdf");
        PdfBookmarkService.Save(source, dest, info.Bookmarks);
        var reloaded = PdfBookmarkService.Load(dest);

        Assert.Equal("宛先なしのしおり", reloaded.Bookmarks[1].Title);
        Assert.Null(reloaded.Bookmarks[1].Page);
    }

    [Fact]
    public void Save_ToSamePath_ReplacesFileSafely()
    {
        string source = TestPdf.CreateWithOutlines(_dir);
        var info = PdfBookmarkService.Load(source);
        info.Bookmarks[0].Title = "上書き確認";

        PdfBookmarkService.Save(source, source, info.Bookmarks);

        var reloaded = PdfBookmarkService.Load(source);
        Assert.Equal("上書き確認", reloaded.Bookmarks[0].Title);
        Assert.Empty(Directory.GetFiles(_dir, "*.tmp-*"));
    }

    [Fact]
    public void Save_InvalidPageOrEmptyTitle_ThrowsValidationWithAllErrors()
    {
        string source = TestPdf.CreateBlank(_dir, pageCount: 2);
        var bookmarks = new List<BookmarkNode>
        {
            new() { Title = "", Page = 1 },
            new() { Title = "範囲外", Page = 99 },
        };

        string dest = Path.Combine(_dir, "invalid.pdf");
        var ex = Assert.Throws<BookmarkValidationException>(
            () => PdfBookmarkService.Save(source, dest, bookmarks));

        Assert.Equal(2, ex.Errors.Count);
        Assert.Contains(ex.Errors, e => e.Contains("タイトルが空"));
        Assert.Contains(ex.Errors, e => e.Contains("99"));
        Assert.False(File.Exists(dest), "検証エラー時に出力ファイルを作成してはならない");
        Assert.Empty(Directory.GetFiles(_dir, "*.tmp-*"));
    }

    [Fact]
    public void Load_EncryptedPdf_ThrowsPdfEncryptedException()
    {
        string path = TestPdf.CreateEncrypted(_dir);

        Assert.Throws<PdfEncryptedException>(() => PdfBookmarkService.Load(path));
    }

    [Fact]
    public void Load_NonPdfFile_ThrowsPdfLoadException()
    {
        string path = Path.Combine(_dir, "notpdf.txt");
        File.WriteAllText(path, "これはPDFではありません");

        Assert.Throws<PdfLoadException>(() => PdfBookmarkService.Load(path));
    }

    private static void AssertTreesEqual(
        IReadOnlyList<BookmarkNode> expected, IReadOnlyList<BookmarkNode> actual)
    {
        Assert.Equal(expected.Count, actual.Count);
        for (int i = 0; i < expected.Count; i++)
        {
            Assert.Equal(expected[i].Title, actual[i].Title);
            Assert.Equal(expected[i].Page, actual[i].Page);
            Assert.Equal(expected[i].Bold, actual[i].Bold);
            Assert.Equal(expected[i].Italic, actual[i].Italic);
            if (expected[i].Children.Count > 0)
            {
                // 展開状態は子を持つノードにのみ意味を持つ
                Assert.Equal(expected[i].Expanded, actual[i].Expanded);
            }
            AssertTreesEqual(expected[i].Children, actual[i].Children);
        }
    }
}
