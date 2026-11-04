"""限流测试: 超限 429, 放行计数, 关闭开关。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.config import CFG
from app.main import app
from app.store import db


def test_rate_limit():
    db.use(Path(tempfile.mkdtemp()) / "rl.db")
    from app.api.limits import _hits

    _hits.clear()  # 清掉其他用例留下的计数
    CFG.setdefault("ratelimit", {})["chat_per_minute"] = 3
    try:
        with TestClient(app) as c:
            assert c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
            codes = [c.post("/api/data/query", json={"question": "机台状态怎么查"}).status_code
                     for _ in range(4)]  # data/query 走同一限流, 每次很快
            assert codes[:3] == [200, 200, 200] and codes[3] == 429
    finally:
        _hits.clear()
        CFG["ratelimit"]["chat_per_minute"] = 30  # 还原默认, 不影响其他用例


def test_rate_limit_disabled():
    db.use(Path(tempfile.mkdtemp()) / "rl2.db")
    CFG.setdefault("ratelimit", {})["chat_per_minute"] = 0
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
        codes = [c.post("/api/data/query", json={"question": "机台状态怎么查"}).status_code for _ in range(5)]
        assert all(code == 200 for code in codes)


def test_login_brute_force_limited():
    db.use(Path(tempfile.mkdtemp()) / "bf.db")
    from app.api.limits import _hits

    _hits.clear()
    CFG.setdefault("ratelimit", {})["login_per_5min"] = 3
    try:
        with TestClient(app) as c:
            codes = [c.post("/api/auth/login",
                            json={"username": "admin", "password": "wrong"}).status_code
                     for _ in range(4)]
            assert codes[:3] == [401, 401, 401] and codes[3] == 429
            # 即便此时密码正确也被限流拦下
            r = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
            assert r.status_code == 429
    finally:
        _hits.clear()
        CFG["ratelimit"]["login_per_5min"] = 10


def test_kb_ingest_path_traversal_blocked():
    db.use(Path(tempfile.mkdtemp()) / "trav.db")
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": "zhangsan", "password": "user123"}).status_code == 200
        r = c.post("/api/kb/ingest", json={"path": "C:/Windows"})
        assert r.status_code == 400 and "路径越界" in r.json()["detail"]
        r2 = c.post("/api/kb/ingest", json={"path": "../../../etc"})
        assert r2.status_code == 400


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
