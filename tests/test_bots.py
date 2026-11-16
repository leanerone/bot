"""Bots 注册表测试: 清单/persona 注入/API 发现。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.bots.registry import list_bots, persona_system_prompt
from app.main import app
from app.store import db


def test_registry_has_four_bots():
    bots = list_bots()
    ids = [b["id"] for b in bots]
    assert {"craft", "analyst", "watcher", "librarian"} <= set(ids)
    for b in bots:
        assert b["emoji"] and b["color"] in ("blue", "green", "red", "orange", "purple", "cyan")
        assert "persona" not in b  # 公开清单不暴露系统提示


def test_persona_injection():
    base = "基础指令: 引用来源。"
    wrapped = persona_system_prompt("craft", base)
    assert wrapped.startswith("你是半导体工厂的工艺与制程助手「小艺」")
    assert "基础指令: 引用来源。" in wrapped
    # 未知 bot_id -> 原样返回
    assert persona_system_prompt("nope", base) == base


def test_chat_with_bot_id():
    db.use(Path(tempfile.mkdtemp()) / "bots.db")
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
        r = c.post("/api/chat", json={"question": "射频功率漂移怎么处理", "bot_id": "craft"})
        assert r.status_code == 200 and r.json()["type"] == "kb"
        # 未知 bot -> 400
        r2 = c.post("/api/chat", json={"question": "x", "bot_id": "nope"})
        assert r2.status_code == 400
        # 清单接口
        lb = c.get("/api/bots").json()["bots"]
        assert len(lb) == 4 and "persona" not in lb[0]


import tempfile  # noqa: E402


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
