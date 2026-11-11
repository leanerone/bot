using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;
using Microsoft.Web.WebView2.Core;
using WF = System.Windows.Forms;
using Application = System.Windows.Application;

namespace FabBot.Desktop;

public partial class MainWindow : Window
{
    private Process? _backend;
    private string _baseUrl = "";
    private WF.NotifyIcon? _tray;
    private const int HotkeyId = 9001;
    private const uint MOD_CONTROL = 0x2, MOD_ALT = 0x1;
    private const uint VK_F = 0x46;

    public MainWindow()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            ApplyWindowChrome();
            InitTray();
            RegisterGlobalHotkey();
            await StartBackendAsync();
            await InitWebViewAsync();
        };
        StateChanged += (_, _) => { if (WindowState == WindowState.Minimized) Hide(); };
        Closing += (_, _) => Cleanup();
    }

    /* ── 窗口外观: Win11 圆角 + Mica 材质 (失败静默, Win10 降级纯色) ── */
    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);

    private void ApplyWindowChrome()
    {
        var hwnd = new WindowInteropHelper(this).Handle;
        var pref = 2; // DWMWCP_ROUND
        DwmSetWindowAttribute(hwnd, 33, ref pref, sizeof(int));
        var backdrop = 2; // Mica — Win11 22H2+ 生效, 旧系统静默失败
        DwmSetWindowAttribute(hwnd, 38, ref backdrop, sizeof(int));
    }

    /* ── 后端 sidecar ── */
    private static int FreePort()
    {
        for (var p = 8100; p <= 8109; p++)
        {
            try
            {
                var l = System.Net.Sockets.TcpListener.Create(p);
                l.Start(); l.Stop();
                return p;
            }
            catch { /* 占用, 试下一个 */ }
        }
        return 8100;
    }

    private static string? FindBackendExe()
    {
        var dir = AppDomain.CurrentDomain.BaseDirectory;
        for (var i = 0; i < 4 && dir != null; i++, dir = Path.GetDirectoryName(dir))
        {
            var cand = Path.Combine(dir, "backend", "FabBotBackend", "FabBotBackend.exe");
            if (File.Exists(cand)) return cand;
        }
        return null;
    }

    private async Task StartBackendAsync()
    {
        var port = FreePort();
        _baseUrl = $"http://127.0.0.1:{port}";
        var exe = FindBackendExe();
        var psi = new ProcessStartInfo
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        if (exe != null)
        {
            psi.FileName = exe;
            psi.WorkingDirectory = Path.GetDirectoryName(exe)!;
            psi.EnvironmentVariables["FABBOT_ROOT"] = psi.WorkingDirectory;
            psi.EnvironmentVariables["FABBOT_PORT"] = port.ToString();
        }
        else
        {
            // 开发回退: 仓库源码 + 系统 python (向上查找 app/main.py)
            var dir = AppDomain.CurrentDomain.BaseDirectory;
            string? repo = null;
            for (var i = 0; i < 6 && dir != null; i++, dir = Path.GetDirectoryName(dir))
                if (File.Exists(Path.Combine(dir, "app", "main.py"))) { repo = dir; break; }
            if (repo == null)
            {
                StateText.Text = "未找到后端 (backend/FabBotBackend.exe 或源码)";
                return;
            }
            psi.FileName = "python";
            psi.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port " + port;
            psi.WorkingDirectory = repo;
            psi.EnvironmentVariables["FABBOT_ROOT"] = repo;
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        }
        _backend = Process.Start(psi);

        using var http = new System.Net.Http.HttpClient();
        for (var i = 0; i < 60; i++)
        {
            try
            {
                await http.GetStringAsync(_baseUrl + "/api/health");
                StateText.Text = "";
                return;
            }
            catch { /* 未就绪, 继续等 */ }
            await Task.Delay(500);
            if (_backend.HasExited)
            {
                StateText.Text = "后端进程异常退出";
                return;
            }
        }
        StateText.Text = "后端启动超时";
    }

    private async Task InitWebViewAsync()
    {
        var userData = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "FabBot", "WebView2");
        var env = await CoreWebView2Environment.CreateAsync(null, userData);
        await Web.EnsureCoreWebView2Async(env);
        var settings = Web.CoreWebView2.Settings;
        settings.AreDefaultContextMenusEnabled = false;
        settings.IsZoomControlEnabled = false;
        settings.AreBrowserAcceleratorKeysEnabled = false;
        Web.NavigationStarting += (_, e) =>
        { // 仅允许同源与 about:blank
            if (!e.Uri.StartsWith(_baseUrl) && e.Uri != "about:blank") e.Cancel = true;
        };
        LoadingMask.Visibility = Visibility.Collapsed;
        Web.CoreWebView2.Navigate(_baseUrl);
        _tray?.ShowBalloonTip(1500, "Fab Bot", "后台服务已就绪, 可以开始使用", WF.ToolTipIcon.Info);
    }

    /* ── 托盘 ── */
    private void InitTray()
    {
        _tray = new WF.NotifyIcon
        {
            Icon = System.Drawing.SystemIcons.Shield,
            Text = "Fab Bot",
            Visible = true,
        };
        var menu = new WF.ContextMenuStrip();
        menu.Items.Add("显示主窗口", null, (_, _) => ShowFromTray());
        menu.Items.Add("退出", null, (_, _) => RealExit());
        _tray.ContextMenuStrip = menu;
        _tray.DoubleClick += (_, _) => ShowFromTray();
    }

    private void ShowFromTray()
    {
        Show();
        WindowState = WindowState.Normal;
        Activate();
    }

    private void RealExit()
    {
        Cleanup();
        Application.Current.Shutdown();
    }

    private void Cleanup()
    {
        try
        {
            if (_backend is { HasExited: false })
            {
                _backend.Kill(true);
                _backend.Dispose();
            }
        }
        catch { /* 已退出 */ }
        try { _tray?.Dispose(); } catch { /* */ }
        try { UnregisterHotKey(new WindowInteropHelper(this).Handle, HotkeyId); } catch { /* */ }
    }

    /* ── 全局快捷键 Ctrl+Alt+F 唤起 ── */
    [DllImport("user32.dll")]
    private static extern bool RegisterHotKey(IntPtr hwnd, uint id, uint mods, uint vk);

    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr hwnd, uint id);

    private void RegisterGlobalHotkey()
    {
        var hwnd = new WindowInteropHelper(this).Handle;
        RegisterHotKey(hwnd, HotkeyId, MOD_CONTROL | MOD_ALT, VK_F);
        var src = HwndSource.FromHwnd(hwnd);
        src?.AddHook(HwndHook);
    }

    private IntPtr HwndHook(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        const int WM_HOTKEY = 0x0312;
        if (msg == WM_HOTKEY && wParam.ToInt32() == HotkeyId)
        {
            ShowFromTray();
            handled = true;
        }
        return IntPtr.Zero;
    }

    /* ── 窗口控制 ── */
    private void Strip_Drag(object sender, MouseButtonEventArgs e)
    {
        if (e.ClickCount == 2) { ToggleMax(); return; }
        if (e.OriginalSource is DependencyObject d && IsOnInteractive(d)) return;
        try { DragMove(); } catch { /* 非按下状态 */ }
    }

    private void Strip_DblClick(object sender, MouseButtonEventArgs e) => ToggleMax();

    private static bool IsOnInteractive(DependencyObject d)
    {
        while (d != null)
        {
            if (d is System.Windows.Controls.Button) return true;
            d = System.Windows.Media.VisualTreeHelper.GetParent(d);
        }
        return false;
    }

    private void ToggleMax()
    {
        WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
    }

    private void BtnClose_Click(object sender, RoutedEventArgs e) => Hide();      // 关窗 -> 托盘
    private void BtnMin_Click(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;
    private void BtnMax_Click(object sender, RoutedEventArgs e) => ToggleMax();
}
