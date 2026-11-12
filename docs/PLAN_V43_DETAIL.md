# Fab Bot Desktop —— v4.3 详细开发计划（可执行粒度）

> 基线: 团队液态玻璃 UI + WebMessage 窗口交互 + 图标全套已合入 (719c9f2)。
> 本文档是施工图: 每个任务列出 改动文件 / API 契约 / 数据模型 / UI 规格 / 验收标准 / 估时。
> 排期按 1 人全栈 8h/天; 并行开发时 P-A 与 P-B 可两人同时开工。

## 任务索引与依赖

```
P-A 通知闭环 (Day1, 8h) ──────────────┐
P-B 数据台图表 (Day2 上午, 4h) ────────┤
P-D 设置整合 (Day2 下午, 4h) ──────────┼──> P-E 打包发布 (Day4, 4h) ──> v4.3 安装包
P-C 任务深化 (Day3, 8h) ──────────────┘
P-F 工程健康 (贯穿, 2h)
```

---

## P-A 原生通知闭环（Day1, 8h）★ 最高价值

### A1 后端增量告警接口（2h）

**文件**: `app/adapters/base.py` `mock_mes.py`（+30 行）、`app/api/tasks.py`（+25 行）、`tests/test_tasks_api.py`（新）

**API 契约**:
```
GET /api/tasks/alarms/since?after_id=0&levels=CRITICAL,ALARM
→ 200 {"alarms": [{id, dt, eqp_id, level, code, message}...],
        "last_id": 123,                      # 当前最大 id (前端游标)
        "server_time": "2026-11-12T14:30:00"}
说明: after_id=0 表示全部; levels 逗号分隔, 缺省 CRITICAL,ALARM; 按 id 升序; 上限 100 条
```

**实现要点**:
- adapter 加 `get_alarms_since(after_id: int, levels: list[str], limit: int = 100)`（SQL: `WHERE id > ? AND level IN (...) AND handled=0 ORDER BY id`）
- `alarms.id` 是自增主键 → 前端游标用 id, 无需时间戳比较（时区免疫）

**验收**: 游标语义单测（插入 3 条 → since(第一条id) 恰返回后 2 条）; 未登录 401。

### A2 前端通知轮询 hook（2h）

**文件**: `desktop/ui/src/hooks/useAlarms.ts`（新, ~90 行）

**行为规格**:
- 登录后启动, 每 60s 调 `alarms/since?after_id={localStorage.fabbot.alarmCursor}`
- 新告警 → ①未读列表追加（localStorage `fabbot.notifs` 存最近 50 条: {id, level, eqp, text, dt, read}）
  ②CRITICAL/ALARM → `chrome.webview.postMessage("toast:" + level + "|" + eqp_id + "|" + message)`
  （WebView 外/浏览器环境静默降级为应用内顶部横幅 5s）
  ③铃铛未读数 = 未读条数, badge 更新
- 页面可见性: document.hidden 时跳过 toast 只记未读; 回到前台铃铛抖动
- 手动测试钩子: `window.__fab.testNotify()` 注入假告警走完整链路

### A3 通知中心 UI（2h）

**文件**: `desktop/ui/src/components/NotificationCenter.tsx`（新, ~120 行）、`TitleBar.tsx` 挂铃铛

**UI 规格**:
- 铃铛 🔔 位于 TitleBar 右侧（搜索左侧）, 未读>0 显示红点数字
- 点击下拉 380px 面板: 头部（未读 N 条 · 全部已读）+ 列表项 [级别徽标][机台][消息][时间], 点击跳任务中心, 底部"查看全部"切到 Tasks
- 空态: "暂无新告警 🎉"

### A4 壳侧 Toast（1h）

**文件**: `desktop/shell/MainWindow.xaml.cs` OnWebMessage 加 case

```
case string a when a.StartsWith("toast:"):
    var parts = a[6:].Split('|');          // level|eqp|message
    _tray?.ShowBalloonTip(3000, $"Fab Bot · {parts[0]} {parts[1]}", parts[2],
        parts[0] == "CRITICAL" ? WF.ToolTipIcon.Error : WF.ToolTipIcon.Warning);
    break;
```

### A5 验收与测试

- pytest: since 游标/levels 过滤/未登录 401（3 项）
- 手动: sqlite 插入一条 CRITICAL 告警 → ≤60s 气泡弹出 + 铃铛红点 + 面板可见
- 回归: 65 项测试 + 59 条评测不受影响

---

## P-B 数据台图表（Day2 上午, 4h）

### B1 依赖与组件（1h）

**文件**: `desktop/ui/package.json` 加 recharts；`src/components/DataChart.tsx`（新, ~140 行）

**组件规格** `DataChart({ mode, xKey, series: [{name, color, points: [{x, y}]}] })`:
- LineChart（趋势）/ BarChart（分布）双形态; recharts 主题色取 iOS 色板
- 响应式 ResponsiveContainer; 空数据显示空态卡

### B2 预置图表端点（2h）

**文件**: `app/api/charts.py`（新, ~70 行）、main.py 挂路由、`tests/test_charts.py`

**API 契约**:
```
GET /api/data/charts/yield-trend?days=30
→ 200 {"days": 30,
       "series": [{"name": "P1234", "points": [{"x": "2026-11-01", "y": 0.931}, ...]}, ...],
       "meta": {"metric": "die_yield"}}
实现: 直连演示库 SQL（按日聚合 die_yield 均值, product 分系列）—— 不走 LLM, 稳定可测

GET /api/data/charts/alarm-by-day?days=14
→ 200 {"series": [{"name": "CRITICAL", "points": [{"x": "2026-11-01", "y": 2}, ...]}, ...]}
实现: alarms 按日+级别计数
```
权限: require_user; 演示库无数据时返回空 series（前端显示空态）。

### B3 自由查询智能切图（1h）

**文件**: `src/pages/Data.tsx` 改造（+60 行）

**识别规则**（纯函数 `detectChart(columns, rows)` → "line"|"bar"|null, 单测覆盖）:
- 存在日期列（列名含 dt/date/时间 或值可 parse）且 ≥1 数值列 → line
- 仅分类列 + 1 数值列（行数 ≤20）→ bar
- Data 页结果区加 Segmented「表格 | 折线 | 柱状」（不可图表化时只有表格）

### B4 验收

- 「良率趋势」预置卡出折线（多产品系列）; 「告警分布」出柱状
- 自由查询「最近两周良率趋势」→ 自动识别可切折线
- pytest: 聚合端点 2 项; detectChart 纯函数 4 项

---

## P-C 任务中心深化（Day3, 8h）

### C1 tasks 表与 CRUD（3h）

**DDL**（`app/store/db.py` _SCHEMA 追加, 迁移: CREATE TABLE IF NOT EXISTS 天然兼容）:
```sql
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT DEFAULT '',
  kind TEXT DEFAULT 'followup',      -- report | alarm-review | followup
  status TEXT DEFAULT 'open',        -- open | done
  due_at TEXT,
  created_at TEXT NOT NULL,
  done_at TEXT
);
```

**API 契约**（`app/api/tasks.py` 追加）:
```
GET    /api/tasks/list?status=open       → {"tasks": [{id, title, detail, kind, status, due_at, created_at}]}
POST   /api/tasks/list                   body {title, detail?, kind?, due_at?} → {"task": {...}}
PATCH  /api/tasks/list/{id}              body {status?|title?|due_at?} → {"ok": true}   (归属校验)
DELETE /api/tasks/list/{id}              → {"ok": true}
```
全部 require_user + 归属校验（user_id 比对, 模式同 messages）。

**前端**: `src/pages/Tasks.tsx` 增「我的任务」区: 新建输入行 + 列表（checkbox 完成/删除/逾期红色 due）+ Segmented(全部/未完成/已完成)。

### C2 交班报告生成（3h）

**后端** `app/api/reports.py`（新）:
```
GET /api/tasks/shift-report?hours=12
→ 200 {"generated_at": "...", "hours": 12,
       "alarms": {"summary": {...}, "items": [...]},
       "yield": {"series": [{name, avg, latest}]},
       "wip": {"total": 40, "by_product": [{"product": "P1234", "lots": 9}]},
       "markdown": "# 交班报告 ..."}      # 后端直接产出 MD 文本, 前端渲染+导出
实现: 聚合函数 build_shift_report(hours) 纯函数（单测）; Word 导出 v1 用 MD（python-docx 留 v4.4）
```

**前端**: 任务中心加「生成交班报告」按钮 → 拉取 → 弹层渲染报告（标题/分级小节/表格）→ 「导出 MD」「复制」。

### C3 watcher 配置 UI（2h, 依赖 P-D1 config API）

任务中心加「值守配置」卡: 级别(checkbox CRITICAL/ALARM)、间隔(Segmented 10/30/60 分钟)、渠道(Segmented wechat/dingtalk/both/none) → PATCH /api/admin/config（admin）→ 提示重启生效。

### C4 验收

- 新建任务 → 列表可见 → 勾选完成 → 逾期任务红字
- 「生成交班报告」含真实告警统计与良率均值, 导出 MD 打开正常
- pytest: tasks CRUD 4 项 + 报告聚合 3 项

---

## P-D 设置整合（Day2 下午, 4h）

### D1 admin 配置读写 API（2h）

**文件**: `app/api/admin_config.py`（新, ~90 行）、tests

**API 契约**:
```
GET  /api/admin/config
→ 200 {"config": {"llm.mock": true, "llm.model": "...", "rag.top_k": 6,
        "rag.hybrid": true, "ratelimit.chat_per_minute": 30,
        "watcher.interval_minutes": 10, "watcher.levels": "ALARM,CRITICAL",
        "watcher.platform": "wechat", "notes.mode": "export"},
       "editable": [上述键列表]}
   密码/webhook/api_key 类键不返回 (打码策略: 白名单外一律不出)

PUT  /api/admin/config   body {"llm.mock": false, "watcher.interval_minutes": 30}
→ 200 {"ok": true, "applied": [...], "restart_required": ["llm.mock"]}
   实现: 白名单键校验 → yaml 读改写 (PyYAML round-trip) → 写前备份 config.yaml.bak
```

### D2 设置页「服务配置」区（1.5h, admin）

分组卡: 模型（Mock/真实 Segmented + 模型名只读）、告警值守（间隔 Segmented + 级别 checkbox + 渠道）、检索（top_k 数字输入 3~10）。变更 PUT → 黄色提示条「已保存, 标 * 的项重启后生效」。

### D3 液态玻璃三档进设置（0.5h）

外观卡加 Segmented(精致/均衡/性能) → `document.documentElement.dataset.glass` + localStorage, 与 TitleBar 菜单同源（抽 `setGlassTier(tier)` 到 `src/glass.ts` 双处调用）。

### D4 主题双向联动补全（0.5h）

setDark 时 `postMessage("theme:" + (dark ? "dark" : "light"))`（壳可同步 Mica 深浅）; 壳已支持该 case。

### 验收

- admin 改 watcher.interval=30 → config.yaml 落盘 → 重启后 GET 回读 30
- 非 admin 访问 config API → 403; PUT 未知键 → 400
- 三档切换即时生效且刷新后保持

---

## P-E 打包发布固化（Day4 上午, 4h）

### E1 一键打包脚本（2h）

**文件**: `deploy/desktop-package.ps1`（新, ~80 行）
```
参数: -Version 4.3.0
步骤: 1) npm ci && npm run build   (desktop/ui)
      2) pyinstaller (复用 BUILD.md §2 参数)
      3) dotnet publish -c Release (framework-dependent)
      4) 组装 dist/FabBot/ (壳输出 + backend/FabBotBackend + ui_dist 进 sidecar bundle)
      5) 校验: exe 存在 + health 端口探测 (起一次壳进程轮询后杀)
输出: dist/FabBot-4.3.0/
```

### E2 UI 打包修复（1h, 关键）

当前 PyInstaller spec 未含 `desktop/ui/dist` → 冻结后 SPA 404。命令追加:
`--add-data "desktop/ui/dist;ui_dist"`, main.py SPA 路径解析顺序改为:
`ROOT/desktop/ui/dist`（源码模式）→ `ROOT/ui_dist`（冻结模式）→ `app/web`（legacy）。

### E3 应用图标与版本（0.5h）

csproj 确认 `<ApplicationIcon>Assets/fabbot.ico</ApplicationIcon>` + `<Version>` 读自 `VERSION` 文件（单源）; health.version 对齐。

### E4 安装包（0.5h）

`deploy/installer.iss`（Inno Setup）: 文件树 + 开始菜单/桌面快捷方式 + WebView2 注册表检测（缺失时引导 Evergreen 下载页/离线包）+ 卸载保留 FabBotData。产出 `Setup_FabBot_4.3.0.exe`。

### 验收

- 干净用户目录双击 Setup → 安装 → 启动 → 登录 → 六模块全可用
- 卸载后 FabBotData 保留（数据不丢）

---

## P-F 工程健康（贯穿, 2h）

- F1 `scripts/desktop-smoke.ps1`: 拉壳 → 等健康 → 截屏 → 归档 → 杀进程（挂夜间门禁, 有桌面会话时执行）
- F2 vitest 接入: mdToHtml / detectChart / 报告聚合纯函数（约 12 项）, `npm test` 进 check_all.sh 第 5 步
- F3 版本单源: 仓库根 `VERSION` 文件 → csproj/health/package.json 构建期读取
- F4 回归纪律: 每任务合入前跑 `bash scripts/check_all.sh`（5 步门禁）+ 评测 59 条

---

## 里程碑验收（v4.3 出口标准）

| # | 标准 | 证据 |
|---|---|---|
| 1 | CRITICAL 告警 60s 内桌面气泡 + 应用内通知 | P-A 演示录像/截图 |
| 2 | 数据台预置图表 + 自由查询智能切图 | 截图 |
| 3 | 交班报告一键生成导出 | 报告样例 |
| 4 | 设置页三档玻璃/服务配置生效 | config.yaml diff |
| 5 | Inno Setup 安装包在干净环境装完全功能 | 安装录屏 |
| 6 | check_all 5 步 + 评测 59 条 + 65 测试全绿 | 门禁日志 |
