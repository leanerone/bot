"""轻量限流: 每用户/每键滑动窗口计数 (单进程内存版)。

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


def _hit(key: str, limit: int, window_s: int) -> bool:
    """True=放行, False=超限。"""
    now = time.time()
    with _lock:
        dq = _hits[key]
        while dq and dq[0] < now - window_s:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


def check_rate(user_id: str) -> None:
    """问答接口限流: 超限抛 429。"""
    limit = int(cfg("ratelimit.chat_per_minute", 30))
    if limit <= 0:
        return
    if not _hit(f"chat:{user_id}", limit, 60):
        raise HTTPException(429, "请求过于频繁, 请稍后再试")


def check_login(identifier: str) -> None:
    """登录接口防爆破: 按 用户名+来源 组合限流 (默认 10 次/5 分钟)。"""
    limit = int(cfg("ratelimit.login_per_5min", 10))
    if limit <= 0:
        return
    if not _hit(f"login:{identifier}", limit, 300):
        raise HTTPException(429, "登录尝试过于频繁, 请 5 分钟后再试")
