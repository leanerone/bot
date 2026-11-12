"""SQLite 持久化层 (WAL 模式)。

表: users / auth_tokens / chat_sessions / messages / audit。
单连接 + 线程锁, 试点量级 (几十用户/万级消息) 足够; 生产换 Postgres 时
仅替换本文件, DAO 接口不变。

测试隔离: 调 use(path) 切换库文件, close() 释放连接。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import abs_path, cfg

_conn: Optional[sqlite3.Connection] = None
_lock = threading.RLock()
_override: Optional[Path] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  pw_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  display_name TEXT DEFAULT '',
  disabled INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_tokens(
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_sessions(
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  type TEXT DEFAULT '',
  content TEXT NOT NULL,
  sources TEXT,
  sql_text TEXT,
  columns TEXT,
  rows TEXT,
  row_count INTEGER,
  rating TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  user TEXT DEFAULT '',
  api TEXT DEFAULT '',
  intent TEXT DEFAULT '',
  question TEXT DEFAULT '',
  ms INTEGER DEFAULT 0,
  status TEXT DEFAULT 'ok'
);
CREATE TABLE IF NOT EXISTS tasks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT DEFAULT '',
  kind TEXT DEFAULT 'followup',
  status TEXT DEFAULT 'open',
  due_at TEXT,
  created_at TEXT NOT NULL,
  done_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
"""


def _db_path() -> Path:
    if _override:
        return Path(_override)
    return abs_path(cfg("store.db_path", "data/app.db"))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def use(path) -> None:
    """切换库文件 (测试隔离用)。"""
    global _conn, _override
    close()
    _override = Path(path)


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            path = _db_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(path), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
            _conn.executescript(_SCHEMA)
            _seed_default_users()
        return _conn


def _seed_default_users() -> None:
    """首次启动时创建内置账号 (密码来自 config, 上线后请立即修改)。"""
    row = _conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
    if row["c"] > 0:
        return
    from app.store.security import hash_password
    from app.config import cfg as _cfg

    accounts = _cfg("auth.bootstrap_users") or [
        {"username": "admin", "password": "admin123", "role": "admin", "display_name": "管理员"},
        {"username": "zhangsan", "password": "user123", "role": "user", "display_name": "张工"},
        {"username": "guest", "password": "guest123", "role": "viewer", "display_name": "访客"},
    ]
    for a in accounts:
        _conn.execute(
            "INSERT INTO users(id, username, pw_hash, role, display_name, created_at) VALUES (?,?,?,?,?,?)",
            (f"u_{a['username']}", a["username"], hash_password(a["password"]),
             a.get("role", "user"), a.get("display_name", ""), _now()),
        )
    _conn.commit()
    print("[db] 已创建内置账号: " + ", ".join(f"{a['username']}({a.get('role')})" for a in accounts)
          + " —— 上线后请立即修改默认密码")


# ── 用户 ──

def create_user(username: str, password: str, role: str = "user",
                display_name: str = "") -> Dict[str, Any]:
    from app.store.security import hash_password
    with _lock:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO users(id, username, pw_hash, role, display_name, created_at) VALUES (?,?,?,?,?,?)",
                (f"u_{username}_{int(datetime.now().timestamp())}", username,
                 hash_password(password), role, display_name, _now()),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"用户名已存在: {username}") from exc
        return get_user_by_username(username)


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def list_users() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, role, display_name, disabled, created_at FROM users ORDER BY created_at"
    ).fetchall()
    return [dict(r) for r in rows]


def update_user(user_id: str, role: Optional[str] = None, disabled: Optional[bool] = None,
                display_name: Optional[str] = None) -> bool:
    with _lock:
        conn = get_conn()
        sets, args = [], []
        if role is not None:
            if role not in ("viewer", "user", "admin"):
                raise ValueError(f"非法角色: {role}")
            sets.append("role = ?")
            args.append(role)
        if disabled is not None:
            sets.append("disabled = ?")
            args.append(1 if disabled else 0)
        if display_name is not None:
            sets.append("display_name = ?")
            args.append(display_name)
        if not sets:
            return False
        args.append(user_id)
        cur = conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", args)
        conn.commit()
        return cur.rowcount > 0


def set_password(user_id: str, password: str) -> None:
    from app.store.security import hash_password
    if len(password) < 6:
        raise ValueError("密码长度至少 6 位")
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (hash_password(password), user_id))
        conn.commit()
        revoke_user_tokens(user_id)


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user_by_username(username)
    if not user or user["disabled"]:
        return None
    from app.store.security import verify_password
    if not verify_password(password, user["pw_hash"]):
        return None
    return user


# ── 登录令牌 ──

def issue_token(user_id: str, ttl_hours: Optional[float] = None) -> tuple:
    from app.store.security import new_token
    ttl = float(ttl_hours if ttl_hours is not None else cfg("auth.token_ttl_hours", 24))
    token = new_token()
    expires = (datetime.now() + timedelta(hours=ttl)).isoformat(timespec="seconds")
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO auth_tokens(token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (token, user_id, _now(), expires),
        )
        conn.execute("DELETE FROM auth_tokens WHERE expires_at < ?", (_now(),))
        conn.commit()
    return token, expires


def resolve_token(token: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM auth_tokens WHERE token = ?", (token,)).fetchone()
    if not row or row["expires_at"] < _now():
        return None
    user = get_user_by_id(row["user_id"])
    if not user or user["disabled"]:
        return None
    return user


def revoke_token(token: str) -> None:
    with _lock:
        conn = get_conn()
        conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
        conn.commit()


def revoke_user_tokens(user_id: str) -> None:
    with _lock:
        conn = get_conn()
        conn.execute("DELETE FROM auth_tokens WHERE user_id = ?", (user_id,))
        conn.commit()


# ── 会话与消息 ──

def create_chat_session(user_id: str, title: str) -> Dict[str, Any]:
    session_id = f"c_{int(datetime.now().timestamp() * 1000)}_{abs(hash(title)) % 10000}"
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO chat_sessions(id, user_id, title, created_at, updated_at) VALUES (?,?,?,?,?)",
            (session_id, user_id, title[:40] or "新会话", _now(), _now()),
        )
        conn.commit()
    return get_chat_session(session_id)


def list_chat_sessions(user_id: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT s.*, COUNT(m.id) AS message_count
           FROM chat_sessions s LEFT JOIN messages m ON m.session_id = s.id
           WHERE s.user_id = ? GROUP BY s.id ORDER BY s.updated_at DESC""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_all_sessions(limit: int = 200) -> List[Dict[str, Any]]:
    """管理员视角: 全用户会话 (含用户名与消息数)。"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT s.*, u.username, COUNT(m.id) AS message_count
           FROM chat_sessions s
           LEFT JOIN users u ON u.id = s.user_id
           LEFT JOIN messages m ON m.session_id = s.id
           GROUP BY s.id ORDER BY s.updated_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def admin_delete_session(session_id: str) -> bool:
    """管理员删除任意会话 (不校验属主)。"""
    if not get_chat_session(session_id):
        return False
    return delete_chat_session(session_id)


def get_chat_session(session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row or (user_id and row["user_id"] != user_id):
        return None
    return dict(row)


def rename_chat_session(session_id: str, title: str, user_id: Optional[str] = None) -> bool:
    if not get_chat_session(session_id, user_id):
        return False
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
                     (title[:40], _now(), session_id))
        conn.commit()
    return True


def delete_chat_session(session_id: str, user_id: Optional[str] = None) -> bool:
    if not get_chat_session(session_id, user_id):
        return False
    with _lock:
        conn = get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        conn.commit()
    return True


def touch_chat_session(session_id: str) -> None:
    with _lock:
        conn = get_conn()
        conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (_now(), session_id))
        conn.commit()


def add_message(session_id: str, role: str, type_: str, content: str, *,
                sources: Optional[List[dict]] = None, sql: Optional[str] = None,
                columns: Optional[List[str]] = None, rows: Optional[List[Any]] = None,
                row_count: Optional[int] = None) -> int:
    with _lock:
        conn = get_conn()
        cur = conn.execute(
            """INSERT INTO messages(session_id, role, type, content, sources, sql_text,
               columns, rows, row_count, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (session_id, role, type_, content,
             json.dumps(sources, ensure_ascii=False) if sources is not None else None,
             sql,
             json.dumps(columns, ensure_ascii=False) if columns is not None else None,
             json.dumps(rows, ensure_ascii=False) if rows is not None else None,
             row_count, _now()),
        )
        conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE id = ?", (_now(), session_id))
        conn.commit()
        return cur.lastrowid


def list_messages(session_id: str, limit: int = 50,
                  before_id: Optional[int] = None) -> Dict[str, Any]:
    """分页取消息 (按 id 升序返回); before_id 为"加载更早"游标。

    返回 {"messages": [...], "has_more": bool} —— has_more 表示更早还有消息。
    """
    conn = get_conn()
    args: List[Any] = [session_id]
    where = "WHERE session_id = ?"
    if before_id:
        where += " AND id < ?"
        args.append(before_id)
    rows = conn.execute(
        f"SELECT * FROM messages {where} ORDER BY id DESC LIMIT ?", (*args, limit + 1)
    ).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    out = []
    for r in reversed(rows):  # 升序输出
        d = dict(r)
        for key in ("sources", "columns", "rows"):
            if d.get(key):
                try:
                    d[key] = json.loads(d[key])
                except json.JSONDecodeError:
                    pass
        out.append(d)
    return {"messages": out, "has_more": has_more}


def rate_message(message_id: int, rating: str) -> bool:
    if rating not in ("up", "down", "none"):
        raise ValueError(f"非法评分: {rating}")
    with _lock:
        conn = get_conn()
        cur = conn.execute(
            "UPDATE messages SET rating = ? WHERE id = ? AND role = 'assistant'",
            (None if rating == "none" else rating, message_id),
        )
        conn.commit()
        return cur.rowcount > 0


def message_owner(message_id: int) -> Optional[str]:
    """返回消息所属会话的 user_id (反馈归属校验用)。"""
    conn = get_conn()
    row = conn.execute(
        """SELECT s.user_id FROM messages m
           JOIN chat_sessions s ON s.id = m.session_id WHERE m.id = ?""",
        (message_id,),
    ).fetchone()
    return row["user_id"] if row else None


# ── 审计 ──

def log_audit(user: str, api: str, intent: str, question: str, ms: int,
              status: str = "ok") -> None:
    with _lock:
        conn = get_conn()
        conn.execute(
            "INSERT INTO audit(ts, user, api, intent, question, ms, status) VALUES (?,?,?,?,?,?,?)",
            (_now(), user, api, intent, question[:200], ms, status),
        )
        conn.commit()


def list_audit(limit: int = 200, user: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_conn()
    if user:
        rows = conn.execute(
            "SELECT * FROM audit WHERE user = ? ORDER BY id DESC LIMIT ?", (user, limit)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── 统计 ──

# ── 任务 (v4.3) ──

def add_task(user_id: str, title: str, detail: str = "", kind: str = "followup",
             due_at: Optional[str] = None) -> Dict[str, Any]:
    if kind not in ("report", "alarm-review", "followup"):
        raise ValueError(f"非法任务类型: {kind}")
    with _lock:
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO tasks(user_id, title, detail, kind, status, due_at, created_at) "
            "VALUES (?,?,?,?,'open',?,?)",
            (user_id, title[:80], detail, kind, due_at, _now()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def list_tasks(user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND status = ? ORDER BY due_at IS NULL, due_at, id DESC",
            (user_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY status = 'done', due_at IS NULL, due_at, id DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_task(task_id: int, user_id: str, status: Optional[str] = None,
                title: Optional[str] = None, due_at: Optional[str] = None) -> bool:
    owner = task_owner(task_id)
    if owner != user_id:
        return False
    with _lock:
        conn = get_conn()
        sets, args = [], []
        if status is not None:
            if status not in ("open", "done"):
                raise ValueError(f"非法状态: {status}")
            sets.append("status = ?")
            args.append(status)
            sets.append("done_at = ?")
            args.append(_now() if status == "done" else None)
        if title is not None:
            sets.append("title = ?")
            args.append(title[:80])
        if due_at is not None:
            sets.append("due_at = ?")
            args.append(due_at)
        if not sets:
            return False
        args.append(task_id)
        cur = conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", args)
        conn.commit()
        return cur.rowcount > 0


def delete_task(task_id: int, user_id: str) -> bool:
    if task_owner(task_id) != user_id:
        return False
    with _lock:
        conn = get_conn()
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0


def task_owner(task_id: int) -> Optional[str]:
    conn = get_conn()
    row = conn.execute(
        "SELECT user_id FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    return row["user_id"] if row else None


def stats() -> Dict[str, Any]:
    conn = get_conn()
    today = datetime.now().isoformat(timespec="seconds")[:10]

    def q(sql: str, args: tuple = ()) -> int:
        return conn.execute(sql, args).fetchone()[0]

    return {
        "users": q("SELECT COUNT(*) FROM users"),
        "chat_sessions": q("SELECT COUNT(*) FROM chat_sessions"),
        "messages": q("SELECT COUNT(*) FROM messages"),
        "messages_today": q("SELECT COUNT(*) FROM messages WHERE created_at >= ?", (today,)),
        "feedback_up": q("SELECT COUNT(*) FROM messages WHERE rating = 'up'"),
        "feedback_down": q("SELECT COUNT(*) FROM messages WHERE rating = 'down'"),
        "audit_today": q("SELECT COUNT(*) FROM audit WHERE ts >= ?", (today,)),
    }
