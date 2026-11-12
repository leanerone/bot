# FabAI Hub · SKILL 插件规范 v0.1（草案）

> 设计原则（来自 FabAI-Hub 开发实施文档 D3）: **skill 只声明"做什么"，运行环境由宿主注入**。
> 结果: skill 写一次，在宿主里对所有人可跑 —— 治"本地能跑同事跑不了"。

## 1. 目录结构

```
skills/
  text2sql/
    SKILL.md          # 元信息 (frontmatter) + 使用说明
  rag/
    SKILL.md
  alarm-watch/
    SKILL.md
```

## 2. SKILL.md frontmatter 规范

```yaml
name: text2sql                 # 全局唯一, [a-z0-9-]
version: 1.0.0                 # semver
runtime: mcp                   # v0.1 仅支持 mcp (宿主经 MCP 协议调用 BOT 工具)
server: fabbot                 # 提供该 skill 的 MCP Server 注册名
tools:                         # 暴露给 Agent 循环的工具名 (须在 server 中注册)
  - text2sql_query
permissions:                   # 声明所需权限 (宿主展示给用户, 写操作需确认卡)
  - db.readonly
  - audit.write
config_schema:                 # 宿主注入的配置 (键→说明), 值由宿主从保险库/连接器取
  - db: 只读中间库连接 (MCP 连接器)
description: 用自然语言对授权生产数据库做只读查询
```

## 3. 宿主职责（强制）

1. **校验**: name 唯一、version 合法、runtime 受支持、tools 已在对应 server 注册。
2. **注入**: config_schema 声明的配置由宿主提供（密钥走 Fernet 保险库、数据库走 MCP 连接器）——skill 内不出现明文密钥。
3. **受控执行**: skill 调用在子进程/受控上下文中执行, 全量审计（谁/何时/参数摘要/结果状态）。
4. **展示**: 资源库（AIWEB 市场）展示 skill 卡片, "安装=启用该 skill 对当前用户/Agent 可见"。

## 4. 传输

- v0.1: MCP stdio（同机 Agent 子进程）与 MCP streamable-http（跨机/平台 Agent）均由 BOT 的
  MCP Server 提供（`mcp_server.py`），传输对 skill 声明透明。
- 后续: node runtime、外部 HTTP skill（声明 `runtime: http` + `endpoint`）。

## 5. 安全边界（现实版）

- 无语言级沙箱 → 防线 = 声明式权限 + 写操作确认卡 + 子进程受限环境 + 全量审计 + 上架人工审核。
- skill 不得内嵌密钥; 违者下架。
