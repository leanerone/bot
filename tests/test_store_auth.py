"""持久化层与认证测试 (临时库文件隔离)。运行: pytest 或 python tests/test_store_auth.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.store import db, security


def _fresh_db():
    tmp = Path(tempfile.mkdtemp()) / "test_app.db"
    db.use(tmp)
    return db


# ── 口令散列 ──

def test_password_hash_roundtrip():
    stored = security.hash_password("s3cret-密码")
    assert stored.startswith("pbkdf2$")
    assert security.verify_password("s3cret-密码", stored)
    assert not security.verify_password("wrong", stored)
    assert not security.verify_password("x", "garbage")


# ── 用户 ──

def test_user_create_and_authenticate():
    _fresh_db()
    u = db.create_user("tester", "pass123", role="user", display_name="测试工")
    assert u["username"] == "tester" and u["role"] == "user"
    assert db.authenticate("tester", "pass123") is not None
    assert db.authenticate("tester", "bad") is None
    try:
        db.create_user("tester", "x")
        raise AssertionError("重复用户名应当报错")
    except ValueError:
        pass


def test_user_disable_and_role():
    _fresh_db()
    u = db.create_user("eng", "pass123")
    assert db.update_user(u["id"], role="admin", disabled=True)
    assert db.authenticate("eng", "pass123") is None  # 禁用后不可登录
    assert db.get_user_by_id(u["id"])["role"] == "admin"


def test_password_change_revokes_tokens():
    _fresh_db()
    u = db.create_user("pw", "pass123")
    token, _ = db.issue_token(u["id"], ttl_hours=1)
    assert db.resolve_token(token) is not None
    db.set_password(u["id"], "newpass9")
    assert db.resolve_token(token) is None  # 改密后旧令牌失效
    assert db.authenticate("pw", "newpass9") is not None


# ── 令牌 ──

def test_token_expiry_and_revoke():
    _fresh_db()
    u = db.create_user("tok", "pass123")
    token, expires = db.issue_token(u["id"], ttl_hours=1)
    assert expires > db._now()
    assert db.resolve_token(token)["id"] == u["id"]
    # 过期: 直接把 expires_at 改到过去
    with db._lock:
        db.get_conn().execute("UPDATE auth_tokens SET expires_at = '2000-01-01T00:00:00' WHERE token = ?", (token,))
        db.get_conn().commit()
    assert db.resolve_token(token) is None
    t2, _ = db.issue_token(u["id"])
    db.revoke_token(t2)
    assert db.resolve_token(t2) is None


def test_default_seed_users():
    _fresh_db()
    db.get_conn()  # 触发种子
    names = [u["username"] for u in db.list_users()]
    assert {"admin", "zhangsan", "guest"} <= set(names)
    assert db.authenticate("admin", "admin123")["role"] == "admin"


# ── 会话与消息 ──

def test_chat_session_and_messages():
    _fresh_db()
    u = db.create_user("chatu", "pass123")
    s = db.create_chat_session(u["id"], "夜班问题")
    assert s["title"] == "夜班问题"
    mid = db.add_message(s["id"], "user", "", "腔压越限怎么办")
    db.add_message(s["id"], "assistant", "kb", "先 Hold 批次…",
                   sources=[{"idx": 1, "source": "SOP.md"}], sql=None)
    msgs = db.list_messages(s["id"])
    assert len(msgs) == 2 and msgs[0]["role"] == "user"
    assert msgs[1]["sources"][0]["source"] == "SOP.md"
    # 评分
    assert db.rate_message(msgs[1]["id"], "up")
    assert db.list_messages(s["id"])[1]["rating"] == "up"
    try:
        db.rate_message(msgs[1]["id"], "bad")
        raise AssertionError("非法评分应报错")
    except ValueError:
        pass
    # 归属校验
    other = db.create_user("other", "pass123")
    assert db.get_chat_session(s["id"], user_id=other["id"]) is None
    assert db.delete_chat_session(s["id"], user_id=other["id"]) is False
    # 列表与统计
    assert db.list_chat_sessions(u["id"])[0]["message_count"] == 2
    assert db.delete_chat_session(s["id"]) is True
    assert db.list_messages(s["id"]) == []


def test_rename_session():
    _fresh_db()
    u = db.create_user("r", "pass123")
    s = db.create_chat_session(u["id"], "旧标题")
    assert db.rename_chat_session(s["id"], "新标题")
    assert db.get_chat_session(s["id"])["title"] == "新标题"


# ── 审计与统计 ──

def test_audit_and_stats():
    _fresh_db()
    db.log_audit("tester", "/api/chat", "kb", "测试问题", 12)
    db.log_audit("tester", "/api/chat", "sql", "查告警", 8)
    rows = db.list_audit(10)
    assert len(rows) == 2 and rows[0]["intent"] == "sql"  # 倒序
    assert db.list_audit(10, user="tester")  # 按用户过滤
    st = db.stats()
    assert st["audit_today"] >= 2 and "users" in st


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
