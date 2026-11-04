"""分页取消息 + 审计 CSV 导出测试。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app
from app.store import db


def test_message_pagination_keyset():
    db.use(Path(tempfile.mkdtemp()) / "pg.db")
    u = db.create_user("pger", "pass123")
    s = db.create_chat_session(u["id"], "长会话")
    for i in range(60):
        db.add_message(s["id"], "user", "", f"消息{i}")
    page1 = db.list_messages(s["id"], limit=50)
    assert len(page1["messages"]) == 50 and page1["has_more"] is True
    assert page1["messages"][0]["content"] == "消息10"   # 最近 50 条的最早一条
    assert page1["messages"][-1]["content"] == "消息59"
    page2 = db.list_messages(s["id"], limit=50,
                             before_id=page1["messages"][0]["id"])
    assert page2["has_more"] is False and len(page2["messages"]) == 10
    assert page2["messages"][0]["content"] == "消息0"


def test_audit_csv_export():
    db.use(Path(tempfile.mkdtemp()) / "csv.db")
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
        c.post("/api/data/query", json={"question": "机台状态怎么查"})
        r = c.get("/api/admin/audit/export?limit=100")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        body = r.content.decode("utf-8-sig")
        assert body.splitlines()[0] == "ts,user,api,intent,question,ms,status"
        assert "机台状态怎么查" in body
        # viewer 不可导出
        c2 = TestClient(app)
        c2.post("/api/auth/login", json={"username": "guest", "password": "guest123"})
        assert c2.get("/api/admin/audit/export").status_code == 403


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
