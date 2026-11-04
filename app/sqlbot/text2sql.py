"""Text2SQL: 自然语言 -> LLM 生成 SQL -> 安全校验 -> 只读执行。

生产改造点:
- db_path 指向 IT 侧只读中间库时, 将 sqlite3 换成对应驱动 (psycopg2 等),
  连接账号保持只读权限;
- 高危查询 (扫描大表/含敏感列) 可加白名单与人工确认环节。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.config import abs_path, cfg
from app.llm.client import get_llm
from app.llm.prompts import T2SQL_SYSTEM, clean_history
from app.sqlbot.schema import FEWSHOT, SCHEMA_TEXT
from app.sqlbot.validator import validate_sql


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"{db_path.resolve().as_uri()}?mode=ro"  # 只读打开
    return sqlite3.connect(uri, uri=True, timeout=5.0)


def execute_sql(sql: str) -> Tuple[List[str], List[List[Any]]]:
    db_path = abs_path(cfg("sqlbot.db_path", "data/demo/fab_demo.db"))
    if not db_path.exists():
        raise FileNotFoundError(
            "演示库不存在 (正常情况服务启动时自动生成); 也可手动运行 data/demo/seed_demo_db.py"
        )
    conn = _connect_ro(db_path)
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [list(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return columns, rows


def query(question: str, history=None) -> Dict[str, Any]:
    max_rows = int(cfg("sqlbot.max_rows", 200))
    prompt = T2SQL_SYSTEM.format(schema=SCHEMA_TEXT, fewshot=FEWSHOT, max_rows=max_rows)
    messages = [{"role": "system", "content": prompt}]
    messages.extend(clean_history(history, max_turns=4))
    messages.append({"role": "user", "content": question})
    raw = get_llm().chat(messages)
    sql = validate_sql(raw, max_rows=max_rows)
    columns, rows = execute_sql(sql)
    return {"sql": sql, "columns": columns, "rows": rows, "row_count": len(rows)}
