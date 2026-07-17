using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace PdfBookmarkEditor.Core;

/// <summary>
/// PDFのしおり(アウトライン)1件。WPFのTreeViewから直接バインドできるよう
/// INotifyPropertyChanged と ObservableCollection を実装する。
/// </summary>
public class BookmarkNode : INotifyPropertyChanged
{
    private string _title = "";
    private int? _page;
    private bool _bold;
    private bool _italic;
    private bool _expanded;

    /// <summary>表示タイトル。保存時は空文字不可。</summary>
    public string Title
    {
        get => _title;
        set => Set(ref _title, value);
    }

    /// <summary>ジャンプ先ページ番号(1始まり)。null は「ページ未設定」。</summary>
    public int? Page
    {
        get => _page;
        set => Set(ref _page, value);
    }

    public bool Bold
    {
        get => _bold;
        set => Set(ref _bold, value);
    }

    public bool Italic
    {
        get => _italic;
        set => Set(ref _italic, value);
    }

    /// <summary>PDFビューアで開いた際に子階層を展開表示するか。</summary>
    public bool Expanded
    {
        get => _expanded;
        set => Set(ref _expanded, value);
    }

    public ObservableCollection<BookmarkNode> Children { get; } = new();

    public event PropertyChangedEventHandler? PropertyChanged;

    private void Set<T>(ref T field, T value, [CallerMemberName] string? name = null)
    {
        if (!Equals(field, value))
        {
            field = value;
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
        }
    }

    /// <summary>子孫を含む複製を返す。</summary>
    public BookmarkNode Clone()
    {
        var copy = new BookmarkNode
        {
            Title = Title,
            Page = Page,
            Bold = Bold,
            Italic = Italic,
            Expanded = Expanded,
        };
        foreach (var child in Children)
        {
            copy.Children.Add(child.Clone());
        }
        return copy;
    }
}
