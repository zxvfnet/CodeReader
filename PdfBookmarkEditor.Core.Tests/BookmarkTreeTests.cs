using System.Collections.ObjectModel;

namespace PdfBookmarkEditor.Core.Tests;

public class BookmarkTreeTests
{
    private static (ObservableCollection<BookmarkNode> Roots,
                    BookmarkNode A, BookmarkNode B, BookmarkNode B1, BookmarkNode B2, BookmarkNode C)
        BuildTree()
    {
        // A, B(B1, B2), C
        var b1 = new BookmarkNode { Title = "B1" };
        var b2 = new BookmarkNode { Title = "B2" };
        var a = new BookmarkNode { Title = "A" };
        var b = new BookmarkNode { Title = "B" };
        b.Children.Add(b1);
        b.Children.Add(b2);
        var c = new BookmarkNode { Title = "C" };
        return (new ObservableCollection<BookmarkNode> { a, b, c }, a, b, b1, b2, c);
    }

    private static string[] Titles(IEnumerable<BookmarkNode> nodes) =>
        nodes.Select(n => n.Title).ToArray();

    [Fact]
    public void AddSibling_InsertsAfterSelected()
    {
        var (roots, a, _, _, _, _) = BuildTree();
        var added = new BookmarkNode { Title = "X" };

        Assert.True(BookmarkTree.AddSibling(roots, a, added));

        Assert.Equal(new[] { "A", "X", "B", "C" }, Titles(roots));
    }

    [Fact]
    public void AddSibling_NoSelection_AppendsToRoot()
    {
        var (roots, _, _, _, _, _) = BuildTree();

        Assert.True(BookmarkTree.AddSibling(roots, null, new BookmarkNode { Title = "X" }));

        Assert.Equal(new[] { "A", "B", "C", "X" }, Titles(roots));
    }

    [Fact]
    public void AddSibling_NestedSelection_InsertsInParentList()
    {
        var (roots, _, b, b1, _, _) = BuildTree();

        Assert.True(BookmarkTree.AddSibling(roots, b1, new BookmarkNode { Title = "X" }));

        Assert.Equal(new[] { "B1", "X", "B2" }, Titles(b.Children));
    }

    [Fact]
    public void AddChild_AppendsToChildren()
    {
        var (roots, a, _, _, _, _) = BuildTree();

        Assert.True(BookmarkTree.AddChild(a, new BookmarkNode { Title = "X" }));

        Assert.Equal(new[] { "X" }, Titles(a.Children));
        Assert.Equal(3, roots.Count);
    }

    [Fact]
    public void Remove_DeletesNodeWithDescendants()
    {
        var (roots, _, b, _, _, _) = BuildTree();

        Assert.True(BookmarkTree.Remove(roots, b));

        Assert.Equal(new[] { "A", "C" }, Titles(roots));
        Assert.Equal(2, BookmarkTree.Count(roots));
    }

    [Fact]
    public void Remove_NestedNode()
    {
        var (roots, _, b, b1, _, _) = BuildTree();

        Assert.True(BookmarkTree.Remove(roots, b1));

        Assert.Equal(new[] { "B2" }, Titles(b.Children));
    }

    [Fact]
    public void MoveUpDown_SwapsWithinSiblings()
    {
        var (roots, a, b, _, _, c) = BuildTree();

        Assert.True(BookmarkTree.MoveUp(roots, b));
        Assert.Equal(new[] { "B", "A", "C" }, Titles(roots));

        Assert.True(BookmarkTree.MoveDown(roots, b));
        Assert.Equal(new[] { "A", "B", "C" }, Titles(roots));

        Assert.False(BookmarkTree.MoveUp(roots, a));
        Assert.False(BookmarkTree.MoveDown(roots, c));
    }

    [Fact]
    public void Outdent_MovesToAfterParent()
    {
        var (roots, _, b, b1, b2, _) = BuildTree();

        Assert.True(BookmarkTree.Outdent(roots, b1));

        Assert.Equal(new[] { "A", "B", "B1", "C" }, Titles(roots));
        Assert.Equal(new[] { "B2" }, Titles(b.Children));
    }

    [Fact]
    public void Outdent_RootLevel_Fails()
    {
        var (roots, a, _, _, _, _) = BuildTree();

        Assert.False(BookmarkTree.Outdent(roots, a));
    }

    [Fact]
    public void Indent_MovesUnderPreviousSibling()
    {
        var (roots, a, b, _, _, _) = BuildTree();

        Assert.True(BookmarkTree.Indent(roots, b));

        Assert.Equal(new[] { "A", "C" }, Titles(roots));
        Assert.Equal(new[] { "B" }, Titles(a.Children));
        Assert.Equal(2, b.Children.Count);
    }

    [Fact]
    public void Indent_FirstSibling_Fails()
    {
        var (roots, a, _, b1, _, _) = BuildTree();

        Assert.False(BookmarkTree.Indent(roots, a));
        Assert.False(BookmarkTree.Indent(roots, b1));
    }

    [Fact]
    public void Count_And_Flatten_CoverAllNodes()
    {
        var (roots, _, _, _, _, _) = BuildTree();

        Assert.Equal(5, BookmarkTree.Count(roots));
        Assert.Equal(new[] { "A", "B", "B1", "B2", "C" },
            Titles(BookmarkTree.Flatten(roots)));
    }

    [Fact]
    public void Clone_CopiesDeeply()
    {
        var (roots, _, b, _, _, _) = BuildTree();
        b.Bold = true;
        b.Page = 7;

        var copy = b.Clone();
        copy.Title = "changed";
        copy.Children[0].Title = "changed-child";

        Assert.Equal("B", b.Title);
        Assert.Equal("B1", b.Children[0].Title);
        Assert.True(copy.Bold);
        Assert.Equal(7, copy.Page);
        Assert.Equal(3, roots.Count);
    }
}
