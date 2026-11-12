# FabAI Hub · 项目推进总结与开发路线（执行版 v1.0）

> 生成: 2026-11-13 00:05 · 分支: `fabai-hub`（自 desktop 拉出）
> 本文 = 项目推进总结 + 已锁定决策 + 本阶段（v4.3）施工清单。
> 配套阅读: PLAN_V43_DETAIL.md（任务级施工图）、DESKTOP_PLAN.md（桌面壳规划）、FabAI-Hub-开发实施文档（需求方 Briefing）。

## 一、项目推进总结（到今天为止）

### 已交付资产

| 资产 | 位置 | 状态 |
|---|---|---|
| **BOT 后端引擎**（RAG 混合检索 / Text2SQL 只读 / 告警值守 / 认证审计限流） | `app/`（本仓库 main 分支 v4.2） | 交付级: 65 测试全绿、三项评测 100%、覆盖率 88%、lint 清零 |
| **桌面壳**（C# WPF + WebView2: 无边框/Mica/托盘/快捷键/sidecar 管理） | `desktop/shell/` | 构建成功 + 真机运行验证（登录页截图 docs/img/desktop-login.png） |
| **桌面 UI**（React18+TS+Tailwind 六模块: 工作台/对话/知识库/数据台/任务/设置） | `desktop/ui/` | 构建成功 + SPA 同源托管验证 |
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
7. **过渡期身份桥**: BOT 校验 AIWEB JWT（Phase 1 落地）, 迁移期双服务并存不割裂。

### 本阶段（v4.3）施工清单 —— 今晚执行

见 PLAN_V43_DETAIL.md 与本仓库 todos: T1 文档 → T2/T3 Skill 规范与注册表 → T4 MCP Server →
T5 通知闭环 → T6 图表 → T7 任务深化 → T8 设置整合 → T9 打包固化 → T10 终验。

## 二、后续开发路线（v4.3 之后）

| 阶段 | 内容 | 前置 |
|---|---|---|
| Hub Phase 1（对应 §十二 1~5） | AIWEB 侧 skill 运行时骨架 + Agent 接入 BOT MCP 工具 + 前端 Vitest + 文档漂移修复 | 今晚 BOT 侧 MCP Server 就绪 |
| Hub Phase 2（§九 Phase 2） | MCP 连接器（Oracle/MES/EAP）+ 桌面轻壳套 AIWEB 前端 | Phase 1 验收 |
| v4.4（BOT 侧） | Rerank 实装、Postgres 迁移、Word 报告导出、通知渠道扩展 | 用户反馈 |
| 长期 | fab-twin-pro 孪生模块、窄任务 LoRA、learn 内容内化 | 按需 |
EOF
echo written