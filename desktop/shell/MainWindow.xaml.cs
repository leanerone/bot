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
    // 标题栏拖拽 / 边缘缩放：用屏幕坐标增量改变窗口，不依赖 WebView2 的鼠标捕获
    private bool _dragging;
    private double _dragMouseX, _dragMouseY, _dragWinX, _dragWinY;
    private string _resizeEdge = "";
    private double _rsMouseX, _rsMouseY, _rsLeft, _rsTop, _rsWidth, _rsHeight;
    private const int HotkeyId = 9001;
    private const uint MOD_CONTROL = 0x2, MOD_ALT = 0x1;
    private const uint VK_F = 0x46;

    private static void Log(string msg)
    {
        try
        {
            var dir = AppDomain.CurrentDomain.BaseDirectory;
            File.AppendAllText(Path.Combine(dir, "shell.log"),
                $"{DateTime.Now:HH:mm:ss} {msg}{Environment.NewLine}");
        }
        catch { /* 日志失败不影响主流程 */ }
    }

    public MainWindow()
    {
        InitializeComponent();
        Loaded += async (_, _) =>
        {
            try
            {
                Log("窗口已加载, 开始启动后端");
                ApplyWindowChrome();
                Log("step1 外观完成");
                InitTray();
                Log("step2 托盘完成");
                RegisterGlobalHotkey();
                Log("step3 热键完成, 准备启动后端");
                await StartBackendAsync();
                Log("step4 后端流程结束");
                await InitWebViewAsync();
                Log("step5 界面加载完成");
            }
            catch (Exception ex)
            {
                Log("启动异常: " + ex);
                StateText.Text = "启动失败: " + ex.Message;
            }
        };
        StateChanged += (_, _) =>
        {
            Log("窗口状态变更: " + WindowState);
            if (WindowState == WindowState.Minimized) Hide();
        };
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
        Log("进入 StartBackendAsync");
        var port = FreePort();
        Log("空闲端口: " + port);
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
            // 开发回退: 仓库源码 + 项目虚拟环境 (向上查找 app/main.py)
            var dir = AppDomain.CurrentDomain.BaseDirectory;
            string? repo = null;
            // BaseDirectory 带尾部反斜杠, GetDirectoryName 会先原地消耗一次, 需多留几层
            for (var i = 0; i < 10 && dir != null; i++, dir = Path.GetDirectoryName(dir))
                if (File.Exists(Path.Combine(dir, "app", "main.py"))) { repo = dir; break; }
            if (repo == null)
            {
                Log("未找到仓库根目录 (app/main.py)");
                StateText.Text = "未找到后端 (backend/FabBotBackend.exe 或源码)";
                return;
            }
            // 优先用仓库内 .venv, 避免系统 python 缺少 fastapi/uvicorn 导致后端起不来
            var venvPython = Path.Combine(repo, ".venv", "Scripts", "python.exe");
            psi.FileName = File.Exists(venvPython) ? venvPython : "python";
            psi.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port " + port;
            // venv 的 launcher 需要自身目录在 PATH 中才能定位基础解释器 DLL
            var oldPath = psi.EnvironmentVariables.ContainsKey("PATH")
                ? psi.EnvironmentVariables["PATH"] : "";
            psi.EnvironmentVariables["PATH"] = Path.GetDirectoryName(psi.FileName)! + ";" + oldPath;
            psi.WorkingDirectory = repo;
            psi.EnvironmentVariables["FABBOT_ROOT"] = repo;
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        }
        Log($"后端命令: {psi.FileName} {psi.Arguments} (cwd={psi.WorkingDirectory})");
        try
        {
            _backend = Process.Start(psi);
            Log($"进程已创建, pid={_backend?.Id}");
        }
        catch (Exception ex)
        {
            Log("Process.Start 失败: " + ex);
            StateText.Text = "后端启动失败: " + ex.Message;
            return;
        }

        using var http = new System.Net.Http.HttpClient();
        for (var i = 0; i < 60; i++)
        {
            try
            {
                await http.GetStringAsync(_baseUrl + "/api/health");
                StateText.Text = "";
                Log("后端就绪: " + _baseUrl);
                return;
            }
            catch { /* 未就绪, 继续等 */ }
            await Task.Delay(500);
            if (_backend?.HasExited == true)
            {
                string output = "";
                try { output = _backend.StandardError.ReadToEnd() + _backend.StandardOutput.ReadToEnd(); }
                catch { /* 忽略 */ }
                Log("后端进程提前退出: " + output);
                StateText.Text = "后端进程异常退出";
                return;
            }
        }
        StateText.Text = "后端启动超时";
        Log("后端启动超时: " + _baseUrl);
    }

    private async Task InitWebViewAsync()
    {
        var userData = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "FabBot", "WebView2");
        // 底色与网页光场(#EEF2FB)对齐：窗口缩放时 WebView2 未绘制的区域不会露出异色块
        Web.DefaultBackgroundColor = System.Drawing.Color.FromArgb(0xEE, 0xF2, 0xFB);
        var env = await CoreWebView2Environment.CreateAsync(null, userData);
        await Web.EnsureCoreWebView2Async(env);
        var settings = Web.CoreWebView2.Settings;
        settings.AreDefaultContextMenusEnabled = false;
        settings.IsZoomControlEnabled = false;
        settings.AreBrowserAcceleratorKeysEnabled = false;
        settings.IsStatusBarEnabled = false;
        settings.IsWebMessageEnabled = true;

        // WebView2 是独立 HWND，WPF 元素无法叠在它上面 (airspace)。
        // 标题栏/拖拽区由网页实现，这里注入桌面标识并关掉网页的默认选中/右键/拖拽。
        await Web.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(@"
(function () {
  var mark = function () {
    if (document.documentElement) document.documentElement.setAttribute('data-desktop', '1');
  };
  mark();
  document.addEventListener('DOMContentLoaded', mark);
  var allow = 'input,textarea,[contenteditable=""true""],.selectable';
  ['selectstart', 'contextmenu', 'dragstart'].forEach(function (type) {
    document.addEventListener(type, function (e) {
      var t = e.target;
      if (t && t.closest && t.closest(allow)) return;
      e.preventDefault();
    });
  });
})();");
        Web.WebMessageReceived += (_, e) => OnWebMessage(e.WebMessageAsJson);
        Web.NavigationStarting += (_, e) =>
        { // 仅允许同源与 about:blank
            if (!e.Uri.StartsWith(_baseUrl) && e.Uri != "about:blank") e.Cancel = true;
        };
        Web.CoreWebView2.NavigationCompleted += (_, e) =>
        {
            if (!e.IsSuccess)
            {
                StateText.Text = "界面加载失败, 请检查后端服务";
                Log("导航失败: " + _baseUrl);
                return;
            }
            Web.Visibility = Visibility.Visible;
            LoadingMask.Visibility = Visibility.Collapsed;
            Log("界面已显示");
        };
        // desktop=1 让前端无竞争地识别「运行在桌面壳内」
        Web.CoreWebView2.Navigate(_baseUrl + "/?desktop=1");
        _tray?.ShowBalloonTip(1500, "Fab Bot", "后台服务已就绪, 可以开始使用", WF.ToolTipIcon.Info);
    }

    /* ── 托盘 ── */
    // 统一使用嵌入资源里的应用图标 (UMC × 晶圆)，替换原来的 Windows 默认盾牌
    private static System.Drawing.Icon AppIcon()
    {
        try
        {
            var info = Application.GetResourceStream(
                new Uri("pack://application:,,,/Assets/fabbot.ico"));
            if (info?.Stream != null)
            {
                using var s = info.Stream;
                return new System.Drawing.Icon(s);
            }
        }
        catch (Exception ex) { Log("应用图标加载失败: " + ex.Message); }
        return System.Drawing.SystemIcons.Application;
    }

    private void InitTray()
    {
        _tray = new WF.NotifyIcon
        {
            Icon = AppIcon(),
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
        ShowWindow(new WindowInteropHelper(this).Handle, 9); // SW_RESTORE
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

    /* ── 网页标题栏 → 窗口控制 ──────────────────────────────────────
     * 网页里点击/按下会 postMessage 一个字符串，这里映射到窗口动作。 */
    private static readonly System.Globalization.CultureInfo Inv = System.Globalization.CultureInfo.InvariantCulture;

    private static bool TryXY(string s, out double x, out double y)
    {
        x = y = 0;
        var p = s.Split(',');
        if (p.Length != 2) return false;
        return double.TryParse(p[0], System.Globalization.NumberStyles.Float, Inv, out x)
            && double.TryParse(p[1], System.Globalization.NumberStyles.Float, Inv, out y);
    }

    private void OnWebMessage(string json)
    {
        var action = json.Trim().Trim('"');

        // 拖拽消息频率高，单独处理且不写日志
        if (action.StartsWith("dragStart:"))
        {
            if (TryXY(action.Substring(10), out var x, out var y))
            {
                _dragMouseX = x; _dragMouseY = y;
                _dragWinX = Left; _dragWinY = Top;
                _dragging = WindowState != WindowState.Maximized;
                Log($"拖拽开始: {x:F0},{y:F0} 可用={_dragging}");
            }
            return;
        }
        if (action.StartsWith("dragMove:"))
        {
            if (_dragging && TryXY(action.Substring(9), out var x, out var y))
            {
                Left = _dragWinX + (x - _dragMouseX);
                Top = _dragWinY + (y - _dragMouseY);
            }
            return;
        }
        if (action == "dragEnd") { _dragging = false; Log($"拖拽结束, 位置 {Left:F0},{Top:F0}"); return; }

        // 窗口边缘 / 四角缩放：WebView2 盖住了 WindowChrome 的原生缩放边框，
        // 所以同样由网页上的透明热区上报坐标，这里换算成窗口矩形。
        if (action.StartsWith("resizeStart:"))
        {
            var body = action.Substring("resizeStart:".Length);
            var i = body.IndexOf(':');
            if (i > 0 && TryXY(body.Substring(i + 1), out var x, out var y))
            {
                _resizeEdge = body.Substring(0, i);
                _rsMouseX = x; _rsMouseY = y;
                _rsLeft = Left; _rsTop = Top;
                _rsWidth = ActualWidth; _rsHeight = ActualHeight;
                Log($"缩放开始: {_resizeEdge} {_rsWidth:F0}x{_rsHeight:F0}");
            }
            return;
        }
        if (action.StartsWith("resizeMove:"))
        {
            if (_resizeEdge.Length > 0 && WindowState != WindowState.Maximized
                && TryXY(action.Substring("resizeMove:".Length), out var x, out var y))
                ApplyResize(x - _rsMouseX, y - _rsMouseY);
            return;
        }
        if (action == "resizeEnd") { _resizeEdge = ""; Log("缩放结束"); return; }

        // 菜单栏里的「接口文档 / 管理后台」：仅允许同源，交给系统默认浏览器
        if (action.StartsWith("openexternal:"))
        {
            var url = action.Substring("openexternal:".Length);
            if (url.StartsWith(_baseUrl, StringComparison.OrdinalIgnoreCase))
            {
                try
                {
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(url)
                    { UseShellExecute = true });
                    Log("外部打开: " + url);
                }
                catch (Exception ex) { Log("外部打开失败: " + ex.Message); }
            }
            return;
        }

        Log("WebMessage: " + action);
        switch (action)
        {
            case "hello": Log("网页标题栏握手成功, WebMessage 通道可用"); break;
            case "theme:dark":
                Web.DefaultBackgroundColor = System.Drawing.Color.FromArgb(0x08, 0x0B, 0x16);
                Background = new System.Windows.Media.SolidColorBrush(
                    System.Windows.Media.Color.FromRgb(0x08, 0x0B, 0x16));
                break;
            case "theme:light":
                Web.DefaultBackgroundColor = System.Drawing.Color.FromArgb(0xEE, 0xF2, 0xFB);
                Background = new System.Windows.Media.SolidColorBrush(
                    System.Windows.Media.Color.FromRgb(0xEE, 0xF2, 0xFB));
                break;
            case "close": HideToTray(); break;
            case "minimize": WindowState = WindowState.Minimized; break;
            case "maximize": ToggleMax(); break;
            case "reload": Web.Reload(); break;
            case "exit": RealExit(); break;
        }
    }

    private void HideToTray()
    {
        Hide();
        _tray?.ShowBalloonTip(1800, "Fab Bot", "已收起到托盘，右键托盘图标可完全退出", WF.ToolTipIcon.Info);
    }

    private void ApplyResize(double dx, double dy)
    {
        bool right = _resizeEdge is "right" or "tr" or "br";
        bool left = _resizeEdge is "left" or "tl" or "bl";
        bool bottom = _resizeEdge is "bottom" or "bl" or "br";
        bool top = _resizeEdge is "top" or "tl" or "tr";
        var w = _rsWidth; var h = _rsHeight;
        var x = _rsLeft; var y = _rsTop;
        if (right) w = Math.Max(MinWidth, _rsWidth + dx);
        if (left) { w = Math.Max(MinWidth, _rsWidth - dx); x = _rsLeft + (_rsWidth - w); }
        if (bottom) h = Math.Max(MinHeight, _rsHeight + dy);
        if (top) { h = Math.Max(MinHeight, _rsHeight - dy); y = _rsTop + (_rsHeight - h); }
        Left = x; Top = y; Width = w; Height = h;
    }

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr hwnd, int cmd);
    [DllImport("user32.dll")]
    private static extern bool IsZoomed(IntPtr hwnd);

    private void ToggleMax()
    {
        var hwnd = new WindowInteropHelper(this).Handle;
        var zoomed = IsZoomed(hwnd) || WindowState == WindowState.Maximized;
        if (!IsVisible) Show();
        WindowState = zoomed ? WindowState.Normal : WindowState.Maximized;
        // 显式调用 Win32：无边框 + WindowChrome 时，避免只改 WPF 状态而实际尺寸不变
        ShowWindow(hwnd, zoomed ? 9 : 3); // SW_RESTORE / SW_MAXIMIZE
        Log($"ToggleMax: zoomed={zoomed} → {WindowState}");
    }
}
