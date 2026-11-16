# FabAI Hub · 项目推进总结与开发路线（执行版 v1.1）

> 生成: 2026-11-13 00:05 · 分支: `fabai-hub`（自 desktop 拉出）· 状态更新: 2026-11-16 (v4.4.1)
> 本文 = 项目推进总结 + 已锁定决策 + 阶段完成度如实标注。
> 配套阅读: PLAN_V43_DETAIL.md（任务级施工图）、DESKTOP_PLAN.md（桌面壳规划）、FabAI-Hub-开发实施文档（需求方 Briefing）。

## 一、项目推进总结（到今天为止）

### 已交付资产

| 资产 | 位置 | 状态 |
|---|---|---|
| **BOT 后端引擎**（RAG 混合检索+rerank / Text2SQL 只读 / Agent 循环 / 技能执行器 / 告警值守 / 认证审计限流） | `app/`（fabai-hub 分支 v4.4.1） | 交付级: 125 测试、三项评测 100% (kb42/sql17/意图59)、MCP 冒烟 7/7、lint 清零 |
| **桌面壳**（C# WPF + WebView2: 无边框/Mica/托盘/快捷键/sidecar 管理） | `desktop/shell/` | 构建成功 + 真机运行验证（登录页截图 docs/img/desktop-login.png） |
| **桌面 UI**（React18+TS+Tailwind 八视图: 工作台/对话/知识库/数据台/任务/技能/管理/设置） | `desktop/ui/` | 构建成功 + SPA 同源托管验证 |
| **团队液态玻璃基线**（WebMessage 窗口交互闭环 / 三档性能开关 / 品牌图标全套） | `desktop/`（719c9f2） | 已合入, 构建全绿 |
| **sidecar 打包**（PyInstaller onedir 85MB: config 内嵌兜底/知识自动落位） | `backend_runner.py` + `dist/FabBotBackend/` | 独立运行验证: health ok + kb=14 |
| **评测体系**（59 条: 知识/SQL/意图 三项 100%） | `eval/` | 门禁常驻 |
| **文档全套**（方案 docx V1.1 含附录B / DEPLOY / USER_GUIDE / ACCEPTANCE / ARCHITECTURE） | `docs/` | 齐备 |

### 关键决策（已锁定, 详见 FabAI-Hub-开发实施文档 D1~D6 + 本轮评审修正）

1. **收敛为 FabAI Hub 单一产品**：AIWEB 出门户/市场/SSO，BOT 出运行时引擎，fab-twin-pro 出 MCP 连接器。
2. **集成模式修正（本轮评审）**：Phase 1 用**连接器模式**——BOT 保持独立服务, 把 RAG/Text2SQL/告警值守暴露为 **MCP 工具**（BOT = 第一个 MCP Server）, AIWEB Agent 循环远程消费; **不做进程内 import 大手术**（推至 Phase 2 评估）。
3. **Skill 即插件**：SKILL.md 声明能力, 宿主注入环境（密钥 Fernet/连接器/模型）, "写一次全员能跑"。
4. **沙箱预期降级**：Python 无真沙箱 → 子进程 + 受限环境 + 写确认卡 + 全量审计 = "受控执行"。
5. **形态**: Web 主入口 + 桌面轻壳（复用 C# WebView2 壳）; 本机独立版（PyInstaller+sidecar）仅离线/自用。
6. **模型策略**: 本地基座 vLLM+Qwen + RAG 先行; 窄任务 LoRA 后置; 不做通用自训。
7. **过渡期身份桥**: BOT 校验 AIWEB JWT（决策已锁定, 列入 Phase 1 施工）。
   ⚠️ 截至 v4.4.1 **尚未实现** —— BOT 代码中无任何 JWT 校验逻辑, 现仍为内置账号 + Cookie/Bearer 令牌;
   "Phase 1 落地"仅指 BOT 侧 MCP Server 就绪, 不代表身份桥/全链路已完成。

### 本阶段（v4.3）施工清单 —— ✅ 已完成 (2026-11-13, H-GATE1~11 全绿, tag v4.3.0)

见 PLAN_V43_DETAIL.md 与本仓库 todos: T1 文档 → T2/T3 Skill 规范与注册表 → T4 MCP Server →
T5 通知闭环 → T6 图表 → T7 任务深化 → T8 设置整合 → T9 打包固化 → T10 终验。

### v4.4 / v4.4.1（BOT 侧）—— ✅ 已交付 (2026-11-15 ~ 11-16)

E0 云 Provider / D3 Agent 循环 / MCP 扩至 7 工具 (统一 envelope) / D4-D5 技能执行器+技能中心 /
B1 管理五页签 / B3 Teams 双格式 / B4 Word 导出+推送 / B5 Notes 增量多库 / E1 rerank /
E2 意图模型化 / E3 上下文压缩 / C1-C5 安全纵深; v4.4.1 两轮修复加固 + Docker 多阶段/CI/安装器。
详见 CHANGELOG.md。

## 二、后续开发路线（v4.4.1 之后, 完成度如实标注）

| 阶段 | 内容 | 前置 | 状态 (2026-11-16) |
|---|---|---|---|
| Hub Phase 1（对应 §十二 1~5） | AIWEB 侧 skill 运行时骨架 + Agent 接入 BOT MCP 工具 + **AIWEB JWT 身份桥** + 前端 Vitest + 文档漂移修复 | BOT 侧 MCP Server 就绪 | **BOT 侧前置已完成** (MCP 7 工具 + envelope + 密钥头, 冒烟 7/7); AIWEB 侧与 JWT 身份桥**未实现** (BOT 无 jwt 代码), 全链路未打通 |
| Hub Phase 2（§九 Phase 2） | MCP 连接器（Oracle/MES/EAP）+ 桌面轻壳套 AIWEB 前端 | Phase 1 验收 | **未实现** (现数据源仍为演示库/只读中间库接口预留) |
| BOT 生产化 | 真实 MES 中间库 / SSO / Postgres 迁移 / 评测集真实问题扩充 | 用户反馈 + IT 配合 | 未开始 (接口已隔离, 见 README 生产化清单) |
| 长期 | fab-twin-pro 孪生模块、窄任务 LoRA、learn 内容内化 | 按需 | **未启动** |