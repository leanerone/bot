---
name: text2sql
version: 1.0.0
runtime: mcp
server: fabbot
tools:
  - text2sql_query
permissions:
  - db.readonly
  - audit.write
config_schema:
  - db: 只读中间库连接 (MCP 连接器)
  - read_only: true
description: 用自然语言对授权生产数据库做只读查询（WIP/良率/机台/告警），SQL 白名单校验 + 只读连接 + 行数上限。
---

# Text2SQL Skill

将自然语言问题转换为只读 SQL 并执行，返回列与行数据。

## 工具

### text2sql_query(question: string) → {sql, columns, rows, row_count}

- 语义层: 机台/批次/良率/告警等业务词 → 表与列（见 `app/sqlbot/schema.py`）。
- 安全: 仅单条 SELECT；禁注释与多语句；LIMIT ≤ 200；只读连接执行；全量审计。

## 示例

- 「最近未处理的告警有哪些」→ alarms 表最近记录
- 「最近一周 P1234 的平均良率」→ yield_daily 聚合
