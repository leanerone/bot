# OpenMausBot 借鉴分析 —— 我们拿什么、不拿什么、为什么

> 参考: E:/AI/OpenMausBot-main (开源 Grok Bot 替代品, Electron + TS monorepo)。
> 结论: **借四个模式, 不借它的运行时** —— 我们的引擎 (RAG/Text2SQL/值守) 与安全模型 (工厂写确认) 与它不同。

## 1. 借鉴的四个模式

### ① Bots as Contacts（核心借鉴）
- **它**: 侧边栏是"联系人列表"，每个 bot 有名字/人设/模型/身份色 (`--identity-green|blue|red|orange|purple|cyan`)，像联系人一样对话。
- **我们怎么做**: 新增 Bot 注册表（4 个专精 bots：工艺助手/数据分析师/告警值守官/知识管理员），每个有 `id/名字/emoji/身份色/系统人设/默认落点`。对话 API 接受 `bot_id`，后端按 persona 注入系统提示。桌面侧栏加"联系人"区。
- **为什么值得**: 单一对话框对用户是"万能但不知道能问什么"；bots-as-contacts 把能力可视化成"找对人"。

### ② Decision Log 决策分类法（审计升级）
- **它**: 按月 NDJSON 追加式决策日志，kind 枚举 `auto-approved / auto-denied / card-shown / user-approved / user-denied / user-undone`，0600 权限 + 脱敏 + fire-and-forget（审计永不拖垮业务）。
- **我们怎么做**: audit 表加 `decision` 列（同枚举），写操作确认卡与 SQL 拒绝全部落分类；管理后台出决策统计。不搬 NDJSON 文件形态（SQLite 已够，但保留 append-only 思想）。

### ③ Watch Them Work（活动流）
- **它**: 聊天里实时展示工具运行行（"Ran a command / Read a file"），人工标签而非代码名。
- **我们怎么做**: RAG/Text2SQL/告警查询的执行步骤事件（"检索了知识库"/"查询了告警表"/"校验 SQL 安全"）以 SSE 步骤推送 + 消息内活动行渲染。

### ④ DESIGN.md 规则文档格式
- **它**: 编号设计规则（"规则不是建议"），token 强制（禁 raw 色）、每个状态都被设计、Calm by default。
- **我们怎么做**: 产出 `docs/DESIGN_RULES.md`（本项目语境: 液态玻璃三档、iOS token、工厂安全文案规则），作为团队 UI 约定。

## 2. 明确不借的

| 它的做法 | 为什么不借 |
|---|---|
| 每台 bot 一个"cloud computer"（云 VM 跑 Claude/Codex） | 工厂红线: 不把生产数据交给外部 agent 执行；我们的引擎在自有服务内 |
| "No new asks"（用 Undo 替代确认弹窗） | 工厂写操作风险不可逆（Hold lot/开单），确认卡必须保留——但我们吸收"能撤销的尽量撤销"思想用于低风险操作 |
| Electron 运行时 | 已定 C# WebView2 壳（公司栈），不换 |
| NDJSON 月度文件审计形态 | SQLite 表 + 管理查询更贴合我们栈 |

## 3. 顺带确认的差距（我们的短板）

1. 设计规则无文档 → 本轮补 DESIGN_RULES.md；
2. 活动步骤已部分有（v4.4 Agent SSE 步骤条）→ 本轮补齐 RAG/SQL 路径的统一活动行；
3. 决策分类缺失 → 本轮补 decision 列；
4. 无 bots 概念 → 本轮新增（这是与 OpenMausBot 对齐的最大 UX 升级）。
