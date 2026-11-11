# Fab Bot Desktop —— Windows 桌面应用规划（v1.0）

> 目标形态: 对标 WorkBuddy 的"AI 数字同事"桌面工作台, Windows 端, iOS 设计风格。
> 核心原则: **复用既有 Fab Bot 后端全部资产**（RAG/Text2SQL/认证审计/Notes 接入, 65 项测试）,
> 桌面壳与 UI 重建 —— 后端是资产不是包袱, 换的只是"壳和脸"。

## 1. 技术选型（按公司栈: Java / Python / C# · VS Code + VS2026）

### 推荐方案 A：C# 主壳 + WebView2 承载 React/TS 界面 + Python 后端 sidecar

```
┌─────────────────────────────────────────────────────┐
│  FabBot.exe (C# / .NET 8, WPF 主窗口, VS2026 开发)   │
│   · 无边框圆角窗口 / Mica 亚克力材质 / 系统托盘        │
│   · 全局快捷键 (类 Spotlight 唤起) / 原生 Toast 通知   │
│   · sidecar 进程管理 (拉起/健康检查/退出回收)          │
│   ┌───────────────────────────────────────────────┐ │
│   │  WebView2 (Win10/11 自带, 无需分发)             │ │
│   │   · React 18 + TypeScript + TailwindCSS        │ │
│   │   · iOS 设计系统 (见 §3), 全部 UI 在这里实现     │ │
│   └────────────────────┬──────────────────────────┘ │
└────────────────────────┼────────────────────────────┘
             PostWebMessage (窗口/托盘/通知指令)
                         │
   HTTP 127.0.0.1:8100  ▼
┌─────────────────────────────────────────────────────┐
│  FabBot.Backend.exe (现有 FastAPI, PyInstaller 打包)  │
│   · RAG / Text2SQL / 认证审计 / Notes 接入 / 评测     │
│   · 65 项测试资产原样保留 —— 零重写                    │
└─────────────────────────────────────────────────────┘
```

**为什么这个组合**:
| 维度 | 评估 |
|---|---|
| 语言栈 | C#（壳, VS2026 一等公民）+ TS（界面, VS Code）+ Python（后端, 已有）—— 全部落在公司能力矩阵内, **零新语言** |
| iOS 风格还原度 | UI 全部由 Web CSS 实现（毛玻璃/spring 动效/圆角/任意定制), 是所有方案里天花板最高的 |
| Windows 原生体验 | C# 壳提供托盘、Toast、全局快捷键、Mica 材质 —— WPF/WinUI 成熟方案 |
| 安装体积 | C# self-contained ~80MB + 前端静态资源 ~5MB + 后端 sidecar ~60MB |
| WebView2 | Win10 1803+ / Win11 系统自带; 工控老机器打包 Evergreen 引导安装即可 |
| 风险 | 三层结构（C#/TS/Python）需要清晰的进程与 IPC 约定 —— 见 §5 |

### 备选方案 B：Electron 单壳（全 TS）
前端 + 壳层都是 TypeScript（VS Code 开发无摩擦), Python 后端同样 sidecar。优点: 团队只维护一种语言;
缺点: 安装包 ~180MB、内存高, 且壳层 JS 不在公司语言栈内。**若团队强烈倾向全 TS 选 B**, 规划其余部分完全通用。

### 否决项
- Tauri v2（Rust 不在公司栈）、Flutter（Dart 不在栈内, 后端整合成本高）、纯 WPF 重写全部 UI（放弃 Web 前端优势, iOS 质感成本翻倍）。

## 2. 与 WorkBuddy 能力对标（范围划定）

| WorkBuddy 能力 | Fab Bot Desktop | 说明 |
|---|---|---|
| AI 对话工作台 | ✅ 已有后端, M1 做 UI | 多会话/流式/引用溯源 |
| 私有知识库 | ✅ 已有后端, M2 做 UI | 导入/来源治理/重建 |
| 数据分析/查数 | ✅ 已有后端, M2 做 UI | Text2SQL + 图表 |
| 自动化任务（日报/纪要） | 🔶 M3 任务中心 | 告警值守/定时报告先行 |
| 操作电脑/跨软件执行 | ⛔ 红线外 | 工厂安全约束: 用受控工具调用替代（MES 只读/推送/审计） |
| IM 接入 | 🔶 后续 | 后端 webhook 已支持企微/钉钉 |

## 3. iOS 风格设计系统（Design Token 落到 TailwindCSS）

| 层 | 规格 |
|---|---|
| 窗口 | 无边框 + 10px 圆角 + Mica 亚克力材质（Win11）/ 半透明白（Win10 降级）; 1px 描边 rgba(0,0,0,0.08) |
| 字体 | MiSans / HarmonyOS Sans SC（免费商用, SF 气质）; 标题 34/28/22/17pt 梯度, 正文 15px |
| 色板 | iOS 语义色: 背景 grouped #F2F2F7(亮)/#1C1C1E(暗), 主色 systemBlue #0A84FF, 强调橙 #FF9500, 分隔线 rgba(60,60,67,0.29) |
| 组件 | inset grouped 分组列表 / 16px 圆角卡片 / UISwitch 开关 / Segmented 分段控件 / Sheet 底部弹层 / Context Menu |
| 动效 | spring 曲线 cubic-bezier(0.32,0.72,0,1) 300ms; 页面横向 push; Sheet 上滑; 骨架屏过渡 |
| 布局 | 左侧毛玻璃侧边栏（导航 + 用户态）+ 内容区大标题导航; 支持亮/暗双主题跟随系统 |

## 4. 功能规划（完整工作台, 六模块）

| 模块 | 内容 | 后端依赖 | 新增工作 |
|---|---|---|---|
| M-Home 工作台 | 今日概览卡片（会话/告警/知识库/任务）、常用操作 | stats 接口（已有） | 首页 UI |
| M-Chat 对话 | 多会话/流式/引用弹层/表格/导出/反馈 | 全部已有（web 版已验证） | 桌面版 UI 重构 |
| M-KB 知识库 | 文档列表/拖拽导入(进度)/来源治理/重建 | ingest/sources/rebuild（已有） | 拖拽与进度 UI |
| M-Data 数据台 | 自然语言查数 → 表格 + 趋势图表（recharts） | /api/data/query（已有） | 图表组件 |
| M-Task 任务 | 告警值守面板（级别/机台/趋势）、定时报告配置 | watcher（已有原型, 需加任务 API） | 任务 API + UI |
| M-Settings 设置 | 账号/服务器地址/模型状态/主题/关于 | auth/health（已有） | 设置 UI |

## 5. 进程与 IPC 约定（三层结构的稳定接口）

1. **C# → Python**: 启动时拉起 sidecar（stdout 健康行 "Uvicorn running" 判定就绪）, 退出时回收;
   端口冲突时从 8100 起顺延探测。
2. **WebView ↔ C#**: 仅两类消息——`ui→native`: openTray/setBadge/showToast/registerHotkey;
   `native→ui`: themeChanged/pushNotification/backendReady。业务数据一律不走此桥, 直连 HTTP。
3. **认证延续**: Cookie 登录沿用, WebView 内 httpOnly 自动携带; 托盘/通知场景用 Bearer token。

## 6. 路线图（4 周 → 可交付安装包）

| 里程碑 | 周期 | 交付 | 验收 |
|---|---|---|---|
| **M0 骨架** | 2 天 | C# 壳可跑（圆角/Mica/托盘）+ sidecar 拉起 + React 骨架 + 设计 token v1 | 窗口出现毛玻璃登录页 |
| **M1 对话** | 第 1 周 | 登录 + 工作台首页 + 对话（流式/引用/表格/导出） | 对标现有 web 版全部能力 |
| **M2 知识与数据** | 第 2 周 | 知识库管理（拖拽导入/来源治理）+ 数据台（查询+图表）+ 设置 | 拖拽 docx 入库立即可问 |
| **M3 任务与原生** | 第 3 周 | 任务中心（告警值守面板/报告配置）+ 全局快捷键 + Toast 通知 | Ctrl+Alt+F 唤起、告警弹 Toast |
| **M4 打包交付** | 第 4 周 | NSIS 安装包 + 自动更新（内网文件源）+ 图标品牌 + 卸载清理 | 双击安装→登录→全功能 |

## 7. 仓库结构（monorepo）

```
E:\AI\BOT\
├── backend\            # 现有 FastAPI（原 app/ 平移, 不动逻辑）
├── desktop\
│   ├── shell\          # C# WPF 主壳（.NET 8, VS2026 解决方案）
│   └── ui\             # React 18 + TS + Tailwind（VS Code）
├── docs\               # 本规划与既有文档
└── scripts\
```

## 8. 风险与对策

| 风险 | 对策 |
|---|---|
| 工控机无 WebView2 | M4 打包内置 Evergreen 引导安装器; DEPLOY 加检测说明 |
| 内网安装包审批 | 提前提交资安扫描; 安装包签名 |
| 三层联调复杂度 | §5 接口契约冻结; C#/Python 各有健康检查; 日志分进程落盘 |
| sidecar 被杀毒误杀 | 提交白名单申请; PyInstaller 单文件+签名 |
| 自动更新内网分发 | 文件共享 + 版本清单校验, 不依赖公网 |

## 9. 今天就能开工的第一步（M0）

1. `desktop/shell` 建 .NET 8 WPF 工程（无边框圆角 + WebView2 控件 + 托盘）
2. `desktop/ui` 建 React+TS+Tailwind 工程, 落设计 token（色板/字体/圆角/动效曲线）
3. backend PyInstaller 打包脚本验证 sidecar 拉起
4. 产出: 毛玻璃登录页跑在真窗口里 —— 立即可见"iOS 风格"效果
