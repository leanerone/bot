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
    CFG.setdefault("ratelimit", {})["chat_per_minute"] = 3
    try:
        with TestClient(app) as c:
            assert c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
            codes = [c.post("/api/data/query", json={"question": "机台状态怎么查"}).status_code
                     for _ in range(4)]  # data/query 走同一限流, 每次很快
            assert codes[:3] == [200, 200, 200] and codes[3] == 429
    finally:
        CFG["ratelimit"]["chat_per_minute"] = 0  # 还原为不限, 不影响其他用例


def test_rate_limit_disabled():
    db.use(Path(tempfile.mkdtemp()) / "rl2.db")
    CFG.setdefault("ratelimit", {})["chat_per_minute"] = 0
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
        codes = [c.post("/api/data/query", json={"question": "机台状态怎么查"}).status_code for _ in range(5)]
        assert all(code == 200 for code in codes)


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
