"""轻量限流: 每用户滑动窗口计数 (单进程内存版)。

多实例部署时替换为 Redis 实现, check_rate 签名不变。
config.yaml -> ratelimit.chat_per_minute: 0 表示不限流。
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import cfg

_hits: dict = defaultdict(deque)
_lock = threading.Lock()


def check_rate(user_id: str) -> None:
    """超限则抛 429。按调用方要求用于问答类接口。"""
    limit = int(cfg("ratelimit.chat_per_minute", 30))
    if limit <= 0:
        return
    now = time.time()
    with _lock:
        dq = _hits[user_id]
        while dq and dq[0] < now - 60:
            dq.popleft()
        if len(dq) >= limit:
            raise HTTPException(429, "请求过于频繁, 请稍后再试")
        dq.append(now)
