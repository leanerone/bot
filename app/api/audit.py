"""审计: 双写 JSONL 文件 + SQLite (便于留存与后台查询)。"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any, Dict

from app.config import abs_path, cfg
from app.store import db

_lock = threading.Lock()


def _file_log(event: Dict[str, Any]) -> None:
    path = abs_path(cfg("audit.path", "data/audit.log"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def record(user: str, api: str, intent: str, question: str, ms: int,
           status: str = "ok") -> None:
    event = {"ts": datetime.now().isoformat(timespec="seconds"), "user": user,
             "api": api, "intent": intent, "question": question[:200],
             "ms": ms, "status": status}
    try:
        _file_log(event)
    except Exception:
        pass
    try:
        db.log_audit(user, api, intent or "", question or "", ms, status)
    except Exception:
        pass  # 审计入库失败不阻断主流程 (文件侧仍留痕)
