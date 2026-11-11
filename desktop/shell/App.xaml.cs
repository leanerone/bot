using System.IO;
using System.Threading;
using System.Windows;

namespace FabBot.Desktop;

public partial class App : System.Windows.Application
{
    private static Mutex? _mutex;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        _mutex = new Mutex(true, "FabBot.Desktop.SingleInstance", out var createdNew);
        if (!createdNew)
        {
            System.Windows.MessageBox.Show("Fab Bot 已在运行。", "Fab Bot", MessageBoxButton.OK, MessageBoxImage.Information);
            Shutdown();
            return;
        }
        var win = new MainWindow();
        win.Show();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        _mutex?.ReleaseMutex();
        base.OnExit(e);
    }
}
