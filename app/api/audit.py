"""审计: 双写 JSONL 文件 + SQLite (便于留存与后台查询)。

v4.4 (C4): 落盘前 PII 脱敏 (手机号/邮箱/IPv4) + 正文截断, 机台号/告警码不受影响。
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from typing import Any, Dict

from app.config import abs_path, cfg
from app.store import db

_lock = threading.Lock()

_RE_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RE_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


def mask_pii(text: str) -> str:
    """手机号/邮箱/IPv4 → ***; 不含字母数字边界的机台号 (ETCH-01) 与告警码 (E0010) 原样保留。"""
    if not text:
        return text
    text = _RE_PHONE.sub("***", text)
    text = _RE_EMAIL.sub("***", text)
    text = _RE_IPV4.sub("***", text)
    return text


def _file_log(event: Dict[str, Any]) -> None:
    path = abs_path(cfg("audit.path", "data/audit.log"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def record(user: str, api: str, intent: str, question: str, ms: int,
           status: str = "ok") -> None:
    if cfg("audit.mask_pii", True):
        question = mask_pii(question or "")
    max_len = int(cfg("audit.max_text_len", 200))
    if max_len > 0:
        question = (question or "")[:max_len]
    event = {"ts": datetime.now().isoformat(timespec="seconds"), "user": user,
             "api": api, "intent": intent, "question": question,
             "ms": ms, "status": status}
    try:
        _file_log(event)
    except Exception:
        pass
    try:
        db.log_audit(user, api, intent or "", question or "", ms, status)
    except Exception:
        pass  # 审计入库失败不阻断主流程 (文件侧仍留痕)
