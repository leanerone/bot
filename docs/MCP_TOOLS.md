# FabBot MCP 工具参考 (v4.4.1)

> 面向: AIWEB Agent / 任何 MCP 客户端消费方。源码: `mcp_server.py` (Server 注册名 `fabbot`)。
> 本文与代码同步维护; 冒烟验证: `python scripts/mcp_smoke.py` (7/7 工具)。

## 1. 连接方式

| 传输 | 启动 | 适用 |
|---|---|---|
| stdio (默认) | `python mcp_server.py` | 同机 Agent 子进程, 无需密钥 |
| streamable-http | `python mcp_server.py --transport streamable-http --port 8111` | 跨机消费 (监听 127.0.0.1, 跨机需反代/隧道) |

**密钥 (C5)**: `config.yaml` → `mcp.require_key: true` 时, streamable-http 的每个请求必须带
`X-FabBot-Key: <mcp.key>` 头; 缺失/错误返回 `401 {"error": "unauthorized: missing/invalid X-FabBot-Key"}`。
服务端用常量时间比较 (防时序侧信道)。stdio 模式不校验。

**预热**: 启动时主线程预导入 rag/向量库/numpy, 避免工具首调在 worker 线程冷导入挂起。

## 2. 统一返回 envelope

所有工具返回 **JSON 字符串**, 结构统一:

```json
// 成功
{"ok": true, "data": { ... }}
// 失败 (异常不裸抛, Agent 可据此重试/降级)
{"ok": false, "data": null, "error": "ExcType: message"}
```

## 3. 工具清单 (7)

### 3.1 rag_search — 知识问答 (检索 + 生成)

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `query` | str | 必填 | 自然语言问题或关键词 (机台号/告警码精确匹配) |
| `top_k` | int | 6 | 返回片段数, 服务端钳制 1~10 |

`data`: `{"answer": str, "sources": [source…]}` — 带引用约束的完整回答;
检索不到时 answer 明确告知未找到 (不编造)。

### 3.2 kb_search — 纯检索 (不生成)

参数同 rag_search (`query`, `top_k=6`, 钳制 1~10)。
`data`: `{"sources": [source…]}` — 只返回相关片段, 供调用方自行组织答案 (Agent 循环常用)。

**source 结构** (3.1/3.2 通用):

```json
{"idx": 1, "source": "文件名或 notes://…", "score": 0.87,
 "excerpt": "前120字预览", "text": "片段全文", "link": "notes://… (可选, Notes 回链)"}
```

### 3.3 text2sql_query — 只读数据查询

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `question` | str | 必填 | 自然语言查询, 如 "最近未处理的告警有哪些" |

`data`: `{"sql": str, "columns": [str…], "rows": [[…]], "row_count": int}`。
安全: 仅单条 SELECT / 禁注释 / 禁多语句 / LIMIT≤200 (`sqlbot.max_rows`) / 只读连接;
违规 SQL 走 envelope `ok=false`。当前数据源为演示库/只读中间库 (`sqlbot.db_path`)。

### 3.4 alarms_open — 未处理告警

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `hours` | int | 168 (7天) | 回看窗口, 钳制 1~720 |

`data`: `{"summary": {"total", "critical", "alarm", "warn"}, "alarms": [前50条明细…]}`。

### 3.5 watcher_summary — 值守概览

无参数。`data`: `{"alarms": {"total", "critical"}, "wip": int}` —
近 7 天未处理告警汇总 + 当前在制品批次总数。

### 3.6 shift_report — 交班报告摘要

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `hours` | int | 8 | 报告覆盖小时数, 钳制 1~72 |

`data`: `{"generated_at": str, "hours": int, "alarms": {"total_open", "critical", "items"(前20条)},
"yield": [{"name", "avg"}…], "wip": [{"product", "lots"}…], "markdown": str}`。
与 Web 端交班报告/Word 导出同一服务 (`app/services/shift_report.py`)。

### 3.7 kb_sources_check — 知识库来源核对

无参数。`data`: `{"chunks": int, "sources": {"来源名": 片段数, …}}` — 导入前核对用, 只读。

## 4. 消费方注意事项

- 全部工具**只读**; 写操作不在 MCP 暴露面内 (Agent 写工具须 requires_confirm + 写确认卡, 见架构红线)。
- 工具调用全量审计 (与 Web 同一套 audit); 问答内容会进入 BOT 的 LLM 链路 ——
  云端 provider 的合规约束 (D1 红线) 同样适用于 MCP 消费场景。
- Agent 循环内部工具名与 MCP 名的映射: `rag_search→kb_search`, `text2sql_query→sql_query`,
  `watcher_summary→alarms_open` (见 `app/skillhub/runner.py`); 技能 (SKILL.md) 声明的是 MCP 名。
- 错误处理建议: `ok=false` 时读 `error` 决定重试/降级, 不要解析裸异常文本。