# Fab Bot Desktop 构建与打包指南

> 产物: Windows 安装目录 (绿色版), 双击 FabBot.exe 即用。
> 分支: `desktop`。

## 0. 环境要求

| 工具 | 版本 | 用途 |
|---|---|---|
| .NET SDK | 8.0+ | C# 壳 (`winget install Microsoft.DotNet.SDK.8`) |
| Node.js | 18+ | 前端构建 |
| Python | 3.10+ | 后端 sidecar 与 PyInstaller (`pip install pyinstaller`) |
| WebView2 Runtime | 系统自带 (Win10 1803+/Win11) | 老机器跑 Evergreen 引导安装 |

## 1. 前端 (React + TS + Tailwind)

```bash
cd desktop/ui
npm install
npm run build        # 产出 desktop/ui/dist
```

## 2. 后端 sidecar (PyInstaller)

```bash
cd E:\AI\BOT          # 仓库根
python -m PyInstaller --noconfirm --clean --onedir --name FabBotBackend ^
  --paths . --collect-all uvicorn --collect-all app ^
  --add-data "data/knowledge;bundle/knowledge" ^
  --add-data "config.yaml;bundle" ^
  backend_runner.py
# 产出 dist/FabBotBackend/ (含 FabBotBackend.exe)
```

## 3. C# 壳

```bash
cd desktop\shell
dotnet build -c Release
# 产出 desktop/shell/bin/Release/net8.0-windows/
```

## 4. 组装部署目录

```bash
mkdir dist\FabBot\backend
cp desktop/shell/bin/Release/net8.0-windows/* dist/FabBot/
cp -r dist/FabBotBackend dist/FabBot/backend/
```

目录形态:
```
FabBot/
├── FabBot.exe            # 双击启动: 自动拉起 sidecar + 打开界面
├── *.dll / runtimes/     # C# 运行时
└── backend/
    └── FabBotBackend/    # Python sidecar (onedir)
        ├── FabBotBackend.exe
        ├── FabBotData/   # 运行时数据 (config/知识库/会话/审计) 自动生成
        └── _internal/
```

## 5. 运行行为

- 启动: 选空闲端口 (8100~8109) → 拉起 sidecar → 健康检查 → WebView2 加载界面
- 关闭窗口 = 最小化到托盘; 托盘右键「退出」才真正退出 (同时回收 sidecar)
- `Ctrl+Alt+F` 全局唤起主窗口
- 数据全部落在 `backend/FabBotBackend/FabBotData/`, 备份该目录即可

## 6. 已知说明

- 演示数据 (告警/WIP) 相对启动日生成, 过期 48 小时后启动自动重种
- 首次运行自动创建内置账号 (admin/admin123), 上线请立即改密
- 自动更新与安装包签名: 见 docs/DESKTOP_PLAN.md §8
