"""Text2SQL 安全层: 只放行单条只读 SELECT, 强制 LIMIT。

原则: 模型生成的 SQL 永远不直接信任 —— 先过校验, 再用只读连接执行
(sqlite mode=ro / 数据库只读账号), 写操作一律走人工确认流程。
"""
from __future__ import annotations

import re
from typing import Set

_FORBIDDEN: Set[str] = {
    "insert", "update", "delete", "drop", "alter", "create", "replace",
    "attach", "detach", "pragma", "vacuum", "reindex", "grant", "revoke",
    "begin", "commit", "rollback",
}


class SQLRejected(ValueError):
    """SQL 未通过安全校验。"""


def _mask_strings(sql: str) -> str:
    """把字符串字面量替换为空串, 避免字段值里的关键字被误判。"""
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def validate_sql(raw: str, max_rows: int = 200) -> str:
    sql = (raw or "").strip()
    sql = re.sub(r"^```[a-zA-Z]*\s*", "", sql)   # 去掉可能的 markdown 围栏
    sql = re.sub(r"```\s*$", "", sql)
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise SQLRejected("SQL 为空")
    if ";" in sql:
        raise SQLRejected("仅允许单条语句")
    if "--" in sql or "/*" in sql:
        raise SQLRejected("不允许携带注释")

    masked = _mask_strings(sql)
    first = re.match(r"\s*([A-Za-z]+)", masked)
    if not first or first.group(1).lower() not in ("select", "with"):
        raise SQLRejected("仅允许 SELECT 查询")

    words = set(re.findall(r"[a-z_]+", masked.lower()))
    hit = words & _FORBIDDEN
    if hit:
        raise SQLRejected(f"包含被禁止的关键字: {sorted(hit)}")

    m = re.search(r"\blimit\s+(\d+)\b", masked.lower())
    if m:
        if int(m.group(1)) > max_rows:  # 上限钳制, 防止全表拉取
            sql = re.sub(r"(?i)\blimit\s+\d+\b", f"LIMIT {max_rows}", sql, count=1)
    else:
        sql = f"{sql} LIMIT {max_rows}"
    return sql
