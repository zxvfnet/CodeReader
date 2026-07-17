namespace PdfBookmarkEditor.Core.Tests;

public class BookmarkJsonSerializerTests
{
    private static List<BookmarkNode> SampleTree()
    {
        var chapter = new BookmarkNode
        {
            Title = "第1章 はじめに",
            Page = 1,
            Bold = true,
            Expanded = true,
        };
        chapter.Children.Add(new BookmarkNode { Title = "1.1 背景", Page = 2, Italic = true });
        chapter.Children.Add(new BookmarkNode { Title = "1.2 目的", Page = null });
        return new List<BookmarkNode> { chapter, new BookmarkNode { Title = "第2章", Page = 5 } };
    }

    [Fact]
    public void ExportImport_RoundTripsHierarchyAndAttributes()
    {
        var original = SampleTree();

        string json = BookmarkJsonSerializer.Export(original);
        var imported = BookmarkJsonSerializer.Import(json, pageCount: 10);

        Assert.Equal(2, imported.Count);
        Assert.Equal("第1章 はじめに", imported[0].Title);
        Assert.Equal(1, imported[0].Page);
        Assert.True(imported[0].Bold);
        Assert.True(imported[0].Expanded);
        Assert.Equal(2, imported[0].Children.Count);
        Assert.Equal("1.1 背景", imported[0].Children[0].Title);
        Assert.True(imported[0].Children[0].Italic);
        Assert.Null(imported[0].Children[1].Page);
        Assert.Equal(5, imported[1].Page);
    }

    [Fact]
    public void Export_ContainsFormatId_AndReadableJapanese()
    {
        string json = BookmarkJsonSerializer.Export(SampleTree());

        Assert.Contains(BookmarkJsonSerializer.FormatId, json);
        Assert.Contains("第1章 はじめに", json);
    }

    [Fact]
    public void Import_OmittedOptionalFields_UseDefaults()
    {
        string json = """
            {
              "format": "PdfBookmarkEditor/1",
              "bookmarks": [ { "title": "最小構成", "page": 3 } ]
            }
            """;

        var imported = BookmarkJsonSerializer.Import(json, pageCount: 5);

        var node = Assert.Single(imported);
        Assert.Equal("最小構成", node.Title);
        Assert.Equal(3, node.Page);
        Assert.False(node.Bold);
        Assert.False(node.Italic);
        Assert.False(node.Expanded);
        Assert.Empty(node.Children);
    }

    [Fact]
    public void Import_SyntaxError_ThrowsJsonException()
    {
        var ex = Assert.Throws<BookmarkJsonException>(
            () => BookmarkJsonSerializer.Import("{ this is not json", pageCount: 5));

        Assert.Contains("構文エラー", ex.Message);
    }

    [Fact]
    public void Import_WrongFormatId_Throws()
    {
        string json = """{ "format": "SomethingElse/9", "bookmarks": [] }""";

        var ex = Assert.Throws<BookmarkJsonException>(
            () => BookmarkJsonSerializer.Import(json, pageCount: 5));

        Assert.Contains("PdfBookmarkEditor/1", ex.Message);
    }

    [Fact]
    public void Import_MissingTitleAndPageOutOfRange_ReportsAllErrorsAndAborts()
    {
        string json = """
            {
              "format": "PdfBookmarkEditor/1",
              "bookmarks": [
                { "title": "", "page": 1 },
                { "title": "親", "page": 2,
                  "children": [ { "title": "範囲外の子", "page": 100 } ] }
              ]
            }
            """;

        var ex = Assert.Throws<BookmarkValidationException>(
            () => BookmarkJsonSerializer.Import(json, pageCount: 10));

        Assert.Equal(2, ex.Errors.Count);
        Assert.Contains(ex.Errors, e => e.Contains("title は必須"));
        Assert.Contains(ex.Errors, e => e.Contains("100"));
        Assert.Contains(ex.Errors, e => e.Contains("2-1"));
    }

    [Fact]
    public void Import_PageBelowOne_IsRejected()
    {
        string json = """
            { "format": "PdfBookmarkEditor/1", "bookmarks": [ { "title": "x", "page": 0 } ] }
            """;

        Assert.Throws<BookmarkValidationException>(
            () => BookmarkJsonSerializer.Import(json, pageCount: 5));
    }

    [Fact]
    public void Import_WithoutPageCount_SkipsRangeCheck()
    {
        string json = """
            { "format": "PdfBookmarkEditor/1", "bookmarks": [ { "title": "x", "page": 9999 } ] }
            """;

        var imported = BookmarkJsonSerializer.Import(json, pageCount: null);

        Assert.Equal(9999, Assert.Single(imported).Page);
    }
}
