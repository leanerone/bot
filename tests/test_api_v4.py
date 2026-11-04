"""v4 API 测试: 认证/权限/会话 CRUD/反馈/管理端。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app
from app.store import db


def _setup(tmp_name):
    db.use(Path(tempfile.mkdtemp()) / tmp_name)


def _client():
    return TestClient(app)


def _login(client, u="admin", p="admin123"):
    r = client.post("/api/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    return r.json()["user"]


# ── 认证 ──

def test_auth_required_on_chat():
    _setup("auth.db")
    with _client() as c:
        r = c.post("/api/chat", json={"question": "你好"})
        assert r.status_code == 401
        r2 = c.get("/api/sessions")
        assert r2.status_code == 401


def test_login_fail_and_me():
    _setup("login.db")
    with _client() as c:
        r = c.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401
        _login(c)
        me = c.get("/api/auth/me")
        assert me.status_code == 200 and me.json()["user"]["role"] == "admin"
        c.post("/api/auth/logout")
        assert c.get("/api/auth/me").status_code == 401


# ── 角色权限 ──

def test_roles():
    _setup("roles.db")
    with _client() as c:
        _login(c, "guest", "guest123")  # viewer
        r = c.post("/api/chat", json={"question": "最近未处理的告警有哪些"})
        assert r.status_code == 200  # viewer 可以问答
        r2 = c.post("/api/kb/ingest")  # 但不能导知识库
        assert r2.status_code == 403
        r3 = c.get("/api/admin/users")
        assert r3.status_code == 403
        _login(c)  # admin
        assert c.get("/api/admin/users").status_code == 200


def test_ingest_requires_user_role():
    _setup("ingest_role.db")
    with _client() as c:
        _login(c, "zhangsan", "user123")
        r = c.post("/api/kb/ingest")
        assert r.status_code == 200 and r.json()["ok"] is True


# ── 会话 CRUD 与追问持久化 ──

def test_session_crud_and_persistence():
    _setup("sess.db")
    with _client() as c:
        _login(c)
        # 无 session_id -> 自动建会话
        r = c.post("/api/chat", json={"question": "最近未处理的告警有哪些"})
        sid = r.json()["session_id"]
        # 列表
        lst = c.get("/api/sessions").json()["sessions"]
        assert len(lst) == 1 and lst[0]["message_count"] == 2
        # 指定会话继续追问
        r2 = c.post("/api/chat", json={"question": "那良率呢", "session_id": sid})
        assert r2.json()["session_id"] == sid
        assert len(c.get(f"/api/sessions/{sid}/messages").json()["messages"]) == 4
        # 改名
        assert c.patch(f"/api/sessions/{sid}", json={"title": "值班排查"}).status_code == 200
        # 删除
        assert c.delete(f"/api/sessions/{sid}").status_code == 200
        assert c.get(f"/api/sessions/{sid}/messages").status_code == 404


def test_feedback_ownership():
    _setup("fb.db")
    with _client() as c:
        _login(c)
        mid = c.post("/api/chat", json={"question": "射频功率漂移怎么处理"}).json()["assistant_message_id"]
        assert c.post("/api/feedback", json={"message_id": mid, "rating": "up"}).status_code == 200
    with _client() as c:
        _login(c, "zhangsan", "user123")
        r = c.post("/api/feedback", json={"message_id": mid, "rating": "down"})
        assert r.status_code == 403  # 别人的消息不能评


# ── 管理端 ──

def test_admin_user_management():
    _setup("admin.db")
    with _client() as c:
        _login(c)
        # 创建
        r = c.post("/api/admin/users", json={"username": "neweng", "password": "pass123",
                                             "role": "user", "display_name": "新工程师"})
        assert r.status_code == 200
        uid = r.json()["user"]["id"]
        # 角色修改 + 禁用
        assert c.patch(f"/api/admin/users/{uid}", json={"role": "viewer"}).status_code == 200
        assert c.patch(f"/api/admin/users/{uid}", json={"disabled": True}).status_code == 200
        # 被禁用用户无法登录
        r2 = c.post("/api/auth/login", json={"username": "neweng", "password": "pass123"})
        assert r2.status_code == 401
        # 防自我锁定
        me = c.get("/api/auth/me").json()["user"]["id"]
        assert c.patch(f"/api/admin/users/{me}", json={"disabled": True}).status_code == 400
        # 密码重置
        assert c.patch(f"/api/admin/users/{uid}/password", json={"password": "short"}).status_code == 400
        assert c.patch(f"/api/admin/users/{uid}/password", json={"password": "newpass9"}).status_code == 200


def test_admin_stats_and_audit():
    _setup("stats.db")
    with _client() as c:
        _login(c)
        c.post("/api/chat", json={"question": "最近未处理的告警有哪些"})
        st = c.get("/api/admin/stats").json()
        assert st["users"] >= 3 and st["messages"] >= 2 and "kb_chunks" in st
        au = c.get("/api/admin/audit?limit=50").json()["audit"]
        assert len(au) >= 1 and au[0]["api"].startswith("/api/")


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
