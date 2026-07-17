using System.Windows;

namespace PdfBookmarkEditor.App;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // 想定外の例外でも即終了せず、内容を表示して可能な限り継続する
        DispatcherUnhandledException += (_, args) =>
        {
            MessageBox.Show(
                $"予期しないエラーが発生しました:\n{args.Exception.Message}",
                "エラー", MessageBoxButton.OK, MessageBoxImage.Error);
            args.Handled = true;
        };
    }
}
