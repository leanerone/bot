"""审计日志: 所有问答与查询落 JSONL 文件, 便于追溯。

生产环境建议改为写数据库或接入公司日志平台, 并保留期按资安要求配置。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any, Dict

from app.config import abs_path, cfg

_lock = threading.Lock()


def log(event: Dict[str, Any]) -> None:
    event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
    path = abs_path(cfg("audit.path", "data/audit.log"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
