using System.Collections.ObjectModel;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Microsoft.Win32;
using PdfBookmarkEditor.Core;

namespace PdfBookmarkEditor.App;

public partial class MainWindow : Window
{
    public static readonly RoutedUICommand ExportJsonCommand = new("JSON書き出し", nameof(ExportJsonCommand), typeof(MainWindow));
    public static readonly RoutedUICommand ImportJsonCommand = new("JSON取り込み", nameof(ImportJsonCommand), typeof(MainWindow));
    public static readonly RoutedUICommand AddSiblingCommand = new("しおりを追加", nameof(AddSiblingCommand), typeof(MainWindow));
    public static readonly RoutedUICommand AddChildCommand = new("子しおりを追加", nameof(AddChildCommand), typeof(MainWindow));
    public static readonly RoutedUICommand DeleteCommand = new("削除", nameof(DeleteCommand), typeof(MainWindow));
    public static readonly RoutedUICommand MoveUpCommand = new("上へ移動", nameof(MoveUpCommand), typeof(MainWindow));
    public static readonly RoutedUICommand MoveDownCommand = new("下へ移動", nameof(MoveDownCommand), typeof(MainWindow));
    public static readonly RoutedUICommand OutdentCommand = new("階層を上げる", nameof(OutdentCommand), typeof(MainWindow));
    public static readonly RoutedUICommand IndentCommand = new("階層を下げる", nameof(IndentCommand), typeof(MainWindow));
    public static readonly RoutedUICommand ReloadCommand = new("編集を破棄して再読込", nameof(ReloadCommand), typeof(MainWindow));

    private readonly ObservableCollection<BookmarkNode> _roots = new();
    private readonly TreeChangeTracker _tracker;
    private string? _sourcePath;
    private int _pageCount;
    private bool _dirty;

    public MainWindow()
    {
        InitializeComponent();
        BookmarkTreeView.ItemsSource = _roots;
        _tracker = new TreeChangeTracker(_roots, MarkDirty);
        UpdateTitle();
    }

    private BookmarkNode? SelectedNode => BookmarkTreeView.SelectedItem as BookmarkNode;

    private bool HasDocument => _sourcePath != null;

    // ---- 状態管理 --------------------------------------------------------

    private void MarkDirty()
    {
        if (!_dirty)
        {
            _dirty = true;
            UpdateTitle();
        }
        UpdateStatus();
    }

    private void UpdateTitle()
    {
        string name = _sourcePath == null ? "" : Path.GetFileName(_sourcePath) + " - ";
        Title = (_dirty ? "*" : "") + name + "PdfBookmarkEditor";
    }

    private void UpdateStatus()
    {
        StatusPathText.Text = _sourcePath ?? "PDFを開いてください (Ctrl+O)";
        StatusInfoText.Text = HasDocument
            ? $"総ページ数: {_pageCount} / しおり: {BookmarkTree.Count(_roots)} 件"
            : "";
        PageCountText.Text = HasDocument ? $"/ {_pageCount}" : "";
    }

    private void LoadDocument(string path)
    {
        var info = PdfBookmarkService.Load(path);
        _sourcePath = path;
        _pageCount = info.PageCount;
        _roots.Clear();
        foreach (var node in info.Bookmarks)
        {
            _roots.Add(node);
        }
        _tracker.Reset();
        _dirty = false;
        UpdateTitle();
        UpdateStatus();
    }

    /// <summary>未保存の変更を破棄してよいか確認する。破棄してよければ true。</summary>
    private bool ConfirmDiscardChanges()
    {
        if (!_dirty)
        {
            return true;
        }
        var result = MessageBox.Show(
            "保存されていない変更があります。破棄してよろしいですか?",
            "確認", MessageBoxButton.YesNo, MessageBoxImage.Warning);
        return result == MessageBoxResult.Yes;
    }

    private static void ShowError(string message)
    {
        MessageBox.Show(message, "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
    }

    // ---- ファイル操作 ----------------------------------------------------

    private void OpenPdf_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        if (!ConfirmDiscardChanges())
        {
            return;
        }
        var dialog = new OpenFileDialog
        {
            Title = "PDFを開く",
            Filter = "PDFファイル (*.pdf)|*.pdf|すべてのファイル (*.*)|*.*",
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }
        try
        {
            LoadDocument(dialog.FileName);
        }
        catch (PdfBookmarkException ex)
        {
            ShowError(ex.Message);
        }
    }

    private void SaveAs_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        if (_sourcePath == null)
        {
            return;
        }
        CommitPageTextBox();
        try
        {
            PdfBookmarkService.Validate(_roots.ToList(), _pageCount);
        }
        catch (BookmarkValidationException ex)
        {
            ShowError(ex.Message);
            return;
        }

        var dialog = new SaveFileDialog
        {
            Title = "名前を付けて保存",
            Filter = "PDFファイル (*.pdf)|*.pdf",
            InitialDirectory = Path.GetDirectoryName(_sourcePath) ?? "",
            FileName = Path.GetFileName(_sourcePath),
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }

        string dest = dialog.FileName;
        bool samePath = string.Equals(
            Path.GetFullPath(dest), Path.GetFullPath(_sourcePath),
            StringComparison.OrdinalIgnoreCase);
        if (samePath)
        {
            var result = MessageBox.Show(
                "元のファイルを上書きします。よろしいですか?",
                "確認", MessageBoxButton.YesNo, MessageBoxImage.Warning);
            if (result != MessageBoxResult.Yes)
            {
                return;
            }
        }

        try
        {
            PdfBookmarkService.Save(_sourcePath, dest, _roots.ToList());
            _sourcePath = dest;
            _dirty = false;
            UpdateTitle();
            UpdateStatus();
        }
        catch (PdfBookmarkException ex)
        {
            ShowError(ex.Message);
        }
    }

    private void ExportJson_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        CommitPageTextBox();
        var dialog = new SaveFileDialog
        {
            Title = "しおりをJSONに書き出す",
            Filter = "JSONファイル (*.json)|*.json",
            FileName = Path.GetFileNameWithoutExtension(_sourcePath ?? "bookmarks") + ".json",
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }
        try
        {
            File.WriteAllText(dialog.FileName, BookmarkJsonSerializer.Export(_roots));
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            ShowError($"JSONを書き出せません: {ex.Message}");
        }
    }

    private void ImportJson_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        var confirm = MessageBox.Show(
            "JSONを取り込むと、現在のしおりはすべて置き換えられます。よろしいですか?",
            "確認", MessageBoxButton.YesNo, MessageBoxImage.Warning);
        if (confirm != MessageBoxResult.Yes)
        {
            return;
        }

        var dialog = new OpenFileDialog
        {
            Title = "しおりJSONを取り込む",
            Filter = "JSONファイル (*.json)|*.json|すべてのファイル (*.*)|*.*",
        };
        if (dialog.ShowDialog(this) != true)
        {
            return;
        }

        try
        {
            string json = File.ReadAllText(dialog.FileName);
            var imported = BookmarkJsonSerializer.Import(json, _pageCount);
            _roots.Clear();
            foreach (var node in imported)
            {
                _roots.Add(node);
            }
            MarkDirty();
        }
        catch (PdfBookmarkException ex)
        {
            ShowError(ex.Message);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            ShowError($"JSONを読み込めません: {ex.Message}");
        }
    }

    private void Reload_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        if (_sourcePath == null || !ConfirmDiscardChanges())
        {
            return;
        }
        try
        {
            LoadDocument(_sourcePath);
        }
        catch (PdfBookmarkException ex)
        {
            ShowError(ex.Message);
        }
    }

    private void Exit_Click(object sender, RoutedEventArgs e)
    {
        Close();
    }

    private void Window_Closing(object sender, System.ComponentModel.CancelEventArgs e)
    {
        if (!ConfirmDiscardChanges())
        {
            e.Cancel = true;
        }
    }

    // ---- しおり操作 ------------------------------------------------------

    private BookmarkNode CreateNewNode()
    {
        return new BookmarkNode
        {
            Title = "新しいしおり",
            Page = SelectedNode?.Page ?? Math.Min(1, _pageCount),
        };
    }

    private void AddSibling_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        var node = CreateNewNode();
        if (BookmarkTree.AddSibling(_roots, SelectedNode, node))
        {
            MarkDirty();
            SelectNodeLater(node);
        }
    }

    private void AddChild_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        var selected = SelectedNode;
        if (selected == null)
        {
            return;
        }
        var node = CreateNewNode();
        BookmarkTree.AddChild(selected, node);
        MarkDirty();
        SelectNodeLater(node);
    }

    private void Delete_Executed(object sender, ExecutedRoutedEventArgs e)
    {
        var selected = SelectedNode;
        if (selected == null)
        {
            return;
        }
        if (selected.Children.Count > 0)
        {
            var result = MessageBox.Show(
                $"「{selected.Title}」には子しおりが {BookmarkTree.Count(selected.Children)} 件あります。まとめて削除しますか?",
                "確認", MessageBoxButton.YesNo, MessageBoxImage.Warning);
            if (result != MessageBoxResult.Yes)
            {
                return;
            }
        }
        if (BookmarkTree.Remove(_roots, selected))
        {
            MarkDirty();
        }
    }

    private void MoveUp_Executed(object sender, ExecutedRoutedEventArgs e) =>
        RunTreeOperation(node => BookmarkTree.MoveUp(_roots, node));

    private void MoveDown_Executed(object sender, ExecutedRoutedEventArgs e) =>
        RunTreeOperation(node => BookmarkTree.MoveDown(_roots, node));

    private void Outdent_Executed(object sender, ExecutedRoutedEventArgs e) =>
        RunTreeOperation(node => BookmarkTree.Outdent(_roots, node));

    private void Indent_Executed(object sender, ExecutedRoutedEventArgs e) =>
        RunTreeOperation(node => BookmarkTree.Indent(_roots, node));

    private void RunTreeOperation(Func<BookmarkNode, bool> operation)
    {
        var selected = SelectedNode;
        if (selected != null && operation(selected))
        {
            MarkDirty();
            SelectNodeLater(selected);
        }
    }

    private void RequiresDocument_CanExecute(object sender, CanExecuteRoutedEventArgs e)
    {
        e.CanExecute = HasDocument;
    }

    private void RequiresSelection_CanExecute(object sender, CanExecuteRoutedEventArgs e)
    {
        e.CanExecute = HasDocument && SelectedNode != null;
    }

    // ---- 編集パネル ------------------------------------------------------

    private void BookmarkTreeView_SelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e)
    {
        var selected = SelectedNode;
        EditPanel.IsEnabled = selected != null;
        EditPanel.DataContext = selected;
        PageTextBox.Text = selected?.Page?.ToString() ?? "";
    }

    private void PageTextBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter)
        {
            CommitPageTextBox();
            e.Handled = true;
        }
    }

    private void PageTextBox_LostFocus(object sender, RoutedEventArgs e)
    {
        CommitPageTextBox();
    }

    /// <summary>ページ欄の入力値を検証して選択ノードへ反映する。不正値は差し戻す。</summary>
    private void CommitPageTextBox()
    {
        var selected = SelectedNode;
        if (selected == null)
        {
            return;
        }
        string text = PageTextBox.Text.Trim();
        if (text.Length == 0)
        {
            selected.Page = null;
            return;
        }
        if (!int.TryParse(text, out int page) || page < 1 || page > _pageCount)
        {
            ShowError($"ページ番号は 1〜{_pageCount} の整数で入力してください。");
            PageTextBox.Text = selected.Page?.ToString() ?? "";
            return;
        }
        selected.Page = page;
    }

    // ---- ツリー選択の補助 ------------------------------------------------

    /// <summary>レイアウト更新後に node をツリー上で選択状態にする。</summary>
    private void SelectNodeLater(BookmarkNode node)
    {
        Dispatcher.BeginInvoke(new Action(() => SelectNode(node)),
            System.Windows.Threading.DispatcherPriority.Background);
    }

    private void SelectNode(BookmarkNode node)
    {
        // ルートから node までの経路を作る
        var chain = new List<BookmarkNode>();
        var current = node;
        while (true)
        {
            chain.Insert(0, current);
            var container = BookmarkTree.FindContainer(_roots, current);
            if (container?.Parent == null)
            {
                break;
            }
            current = container.Value.Parent!;
        }

        ItemsControl parent = BookmarkTreeView;
        foreach (var item in chain)
        {
            parent.UpdateLayout();
            if (parent.ItemContainerGenerator.ContainerFromItem(item) is not TreeViewItem container)
            {
                return;
            }
            if (ReferenceEquals(item, node))
            {
                container.IsSelected = true;
                container.BringIntoView();
            }
            else
            {
                container.IsExpanded = true;
            }
            parent = container;
        }
    }
}
