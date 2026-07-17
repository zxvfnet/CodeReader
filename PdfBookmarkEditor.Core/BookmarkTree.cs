namespace PdfBookmarkEditor.Core;

/// <summary>
/// しおりツリー(ルートのノードリスト)に対する構造操作。
/// すべての操作は成功時 true、対象が見つからない・移動できない場合 false を返す。
/// </summary>
public static class BookmarkTree
{
    /// <summary>node が属するリストとその親ノードを探す。ルート直下なら parent は null。</summary>
    public static (IList<BookmarkNode> List, BookmarkNode? Parent)? FindContainer(
        IList<BookmarkNode> roots, BookmarkNode node)
    {
        if (roots.Contains(node))
        {
            return (roots, null);
        }
        foreach (var root in roots)
        {
            var found = FindContainerUnder(root, node);
            if (found != null)
            {
                return found;
            }
        }
        return null;
    }

    private static (IList<BookmarkNode>, BookmarkNode?)? FindContainerUnder(
        BookmarkNode parent, BookmarkNode node)
    {
        if (parent.Children.Contains(node))
        {
            return (parent.Children, parent);
        }
        foreach (var child in parent.Children)
        {
            var found = FindContainerUnder(child, node);
            if (found != null)
            {
                return found;
            }
        }
        return null;
    }

    /// <summary>selected の直後に兄弟として追加。selected が null ならルート末尾に追加。</summary>
    public static bool AddSibling(IList<BookmarkNode> roots, BookmarkNode? selected, BookmarkNode newNode)
    {
        if (selected == null)
        {
            roots.Add(newNode);
            return true;
        }
        var container = FindContainer(roots, selected);
        if (container == null)
        {
            return false;
        }
        var (list, _) = container.Value;
        list.Insert(list.IndexOf(selected) + 1, newNode);
        return true;
    }

    /// <summary>selected の子の末尾に追加。</summary>
    public static bool AddChild(BookmarkNode selected, BookmarkNode newNode)
    {
        selected.Children.Add(newNode);
        return true;
    }

    /// <summary>node を子孫ごと削除。</summary>
    public static bool Remove(IList<BookmarkNode> roots, BookmarkNode node)
    {
        var container = FindContainer(roots, node);
        if (container == null)
        {
            return false;
        }
        container.Value.List.Remove(node);
        return true;
    }

    /// <summary>同一階層内で1つ上へ移動。</summary>
    public static bool MoveUp(IList<BookmarkNode> roots, BookmarkNode node)
    {
        var container = FindContainer(roots, node);
        if (container == null)
        {
            return false;
        }
        var (list, _) = container.Value;
        int index = list.IndexOf(node);
        if (index <= 0)
        {
            return false;
        }
        list.RemoveAt(index);
        list.Insert(index - 1, node);
        return true;
    }

    /// <summary>同一階層内で1つ下へ移動。</summary>
    public static bool MoveDown(IList<BookmarkNode> roots, BookmarkNode node)
    {
        var container = FindContainer(roots, node);
        if (container == null)
        {
            return false;
        }
        var (list, _) = container.Value;
        int index = list.IndexOf(node);
        if (index < 0 || index >= list.Count - 1)
        {
            return false;
        }
        list.RemoveAt(index);
        list.Insert(index + 1, node);
        return true;
    }

    /// <summary>階層を上げる(アウトデント): 親の直後の兄弟に移動。ルート直下では不可。</summary>
    public static bool Outdent(IList<BookmarkNode> roots, BookmarkNode node)
    {
        var container = FindContainer(roots, node);
        if (container?.Parent == null)
        {
            return false;
        }
        var (list, parent) = container.Value;
        var parentContainer = FindContainer(roots, parent!);
        if (parentContainer == null)
        {
            return false;
        }
        list.Remove(node);
        var (parentList, _) = parentContainer.Value;
        parentList.Insert(parentList.IndexOf(parent!) + 1, node);
        return true;
    }

    /// <summary>階層を下げる(インデント): 直前の兄弟の子の末尾に移動。先頭要素では不可。</summary>
    public static bool Indent(IList<BookmarkNode> roots, BookmarkNode node)
    {
        var container = FindContainer(roots, node);
        if (container == null)
        {
            return false;
        }
        var (list, _) = container.Value;
        int index = list.IndexOf(node);
        if (index <= 0)
        {
            return false;
        }
        var newParent = list[index - 1];
        list.RemoveAt(index);
        newParent.Children.Add(node);
        return true;
    }

    /// <summary>全ノード数(子孫含む)。</summary>
    public static int Count(IEnumerable<BookmarkNode> roots)
    {
        int count = 0;
        foreach (var node in roots)
        {
            count += 1 + Count(node.Children);
        }
        return count;
    }

    /// <summary>全ノードを深さ優先で列挙する。</summary>
    public static IEnumerable<BookmarkNode> Flatten(IEnumerable<BookmarkNode> roots)
    {
        foreach (var node in roots)
        {
            yield return node;
            foreach (var descendant in Flatten(node.Children))
            {
                yield return descendant;
            }
        }
    }
}
