"""C2 登录防爆破: 按 用户名+IP 统计失败, 超阈值锁定窗口期。

进程内计数 (单进程部署足够; 多实例部署时应迁 Redis —— DAO 思路与限流一致)。
管理员账号 (role=admin) 不锁定, 防止管理员自我锁定失去唯一入口 (沿用 v4.0 决策)。
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Tuple

from app.config import cfg
from app.store import db

_lock = threading.Lock()
_failures: Dict[Tuple[str, str], list] = {}  # (username, ip) -> [fail_ts, ...]
_locked_until: Dict[Tuple[str, str], float] = {}
_admin_hits: Dict[str, list] = {}  # username -> [attempt_ts, ...] (管理员全局限速)


def _key(username: str, ip: str) -> Tuple[str, str]:
    return (username.lower(), ip or "?")


def _is_admin(username: str) -> bool:
    try:
        u = db.get_user_by_username(username)
        return bool(u) and u.get("role") == "admin"
    except Exception:
        return False


def check_locked(username: str, ip: str) -> int:
    """返回剩余锁定秒数; 0 = 未锁定。管理员不锁。"""
    if _is_admin(username):
        return 0
    key = _key(username, ip)
    max_f = int(cfg("auth_lock.max_failures", 5))
    win = float(cfg("auth_lock.window_minutes", 10)) * 60
    lock_s = float(cfg("auth_lock.lock_minutes", 15)) * 60
    now = time.time()
    with _lock:
        until = _locked_until.get(key, 0)
        if until > now:
            return int(until - now)
        if until:  # 锁定已到期, 清态放行
            _locked_until.pop(key, None)
            _failures.pop(key, None)
        wins = [t for t in _failures.get(key, []) if now - t < win]
        _failures[key] = wins
        if len(wins) >= max_f:
            _locked_until[key] = now + lock_s
            _failures.pop(key, None)
            return int(lock_s)
    return 0


def check_admin_rate(username: str) -> bool:
    """B1: 管理员豁免锁定, 但加更严的全局限速 (按用户名而非 IP, 换 IP 无效)。

    防攻击者对唯一 admin 入口持续爆破。True=放行, False=超限。
    """
    if not _is_admin(username):
        return True
    limit = int(cfg("auth_lock.admin_per_minute", 3))
    if limit <= 0:
        return True
    now = time.time()
    key = username.lower()
    with _lock:
        hits = [t for t in _admin_hits.get(key, []) if now - t < 60]
        if len(hits) >= limit:
            _admin_hits[key] = hits
            return False
        hits.append(now)
        _admin_hits[key] = hits
        return True


def record_failure(username: str, ip: str) -> None:
    if _is_admin(username):
        return
    key = _key(username, ip)
    with _lock:
        _failures.setdefault(key, []).append(time.time())


def record_success(username: str, ip: str) -> None:
    key = _key(username, ip)
    with _lock:
        _failures.pop(key, None)
        _locked_until.pop(key, None)


def status() -> dict:
    """管理端排查用: 当前锁定数 (不含值, 防泄露)。"""
    now = time.time()
    with _lock:
        active = sum(1 for v in _locked_until.values() if v > now)
    return {"locked": active}
