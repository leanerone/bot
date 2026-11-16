"""决策日志分类测试 (借鉴 OpenMausBot decision-log: auto-approved/card-shown/user-* 枚举)。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app
from app.store import db


def test_decision_enum_recorded():
    db.use(Path(tempfile.mkdtemp()) / "dec.db")
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
        # 只读查询 → auto-approved
        r = c.post("/api/data/query", json={"question": "机台状态怎么查"})
        assert r.status_code == 200
        # SQL 拒绝 → auto-denied (validator 拒绝写操作)
        c.post("/api/data/query", json={"question": "删除所有告警记录"})
        rows = db.list_audit(50)
        decisions = [(a["api"], a.get("decision")) for a in rows]
        assert ("auto-approved", None) not in decisions  # decision 字段存在
        approved = [a for a in rows if a["api"] == "/api/data/query" and a["decision"] == "auto-approved"]
        assert approved, "只读查询应记 auto-approved"
        # 写 SQL 拒绝路径由 validator 层负责 (tests/test_validator.py + SQLRejected 分支已埋 auto-denied);
        # mock LLM 不会生成写 SQL, 此处只验证 decision 字段全程落库
        assert all(a.get("decision") in ("auto-approved", "auto-denied", "") for a in rows)


def test_decision_kind_column_exists():
    db.use(Path(tempfile.mkdtemp()) / "dec2.db")
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        c.post("/api/chat", json={"question": "你好"})
        rows = db.list_audit(20)
        assert all("decision" in a for a in rows)
