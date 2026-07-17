using System.Collections.ObjectModel;
using System.Collections.Specialized;
using PdfBookmarkEditor.Core;

namespace PdfBookmarkEditor.App;

/// <summary>
/// しおりツリー全体の変更(属性編集・追加・削除・並べ替え)を監視し、
/// 変更があるたびにコールバックを呼ぶ。未保存フラグの管理に使う。
/// </summary>
public class TreeChangeTracker
{
    private readonly ObservableCollection<BookmarkNode> _roots;
    private readonly Action _onChanged;
    private readonly HashSet<BookmarkNode> _attached = new();
    private bool _suppress;

    public TreeChangeTracker(ObservableCollection<BookmarkNode> roots, Action onChanged)
    {
        _roots = roots;
        _onChanged = onChanged;
        _roots.CollectionChanged += OnCollectionChanged;
    }

    /// <summary>ドキュメント読み込み直後に呼ぶ。既存ノードを監視対象にし、変更通知は発火しない。</summary>
    public void Reset()
    {
        _suppress = true;
        try
        {
            foreach (var node in BookmarkTree.Flatten(_roots))
            {
                Attach(node);
            }
        }
        finally
        {
            _suppress = false;
        }
    }

    private void Attach(BookmarkNode node)
    {
        if (!_attached.Add(node))
        {
            return;
        }
        node.PropertyChanged += (_, _) => NotifyChanged();
        node.Children.CollectionChanged += OnCollectionChanged;
        foreach (var child in node.Children)
        {
            Attach(child);
        }
    }

    private void OnCollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        if (e.NewItems != null)
        {
            foreach (BookmarkNode node in e.NewItems)
            {
                Attach(node);
            }
        }
        NotifyChanged();
    }

    private void NotifyChanged()
    {
        if (!_suppress)
        {
            _onChanged();
        }
    }
}
