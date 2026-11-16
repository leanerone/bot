"""AIWEB JWT 身份桥测试: 签发→自动建档→角色映射→过期/签名拒绝。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.config import CFG
from app.main import app
from app.store import db


import time as _time


def _token(username="engineer01", role=None, secret="bridge-secret", expired=False):
    payload = {"sub": username, "iss": "aiweb", "name": "域工程师",
               "iat": int(_time.time()), "exp": int(_time.time()) + 3600}
    if expired:
        payload["exp"] = int(_time.time()) - 3600
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _enable(secret="bridge-secret"):
    CFG.setdefault("auth", {})["jwt"] = {
        "enabled": True, "secret": secret, "issuer": "aiweb", "auto_provision": "viewer",
    }


def test_jwt_auto_provision_and_role():
    db.use(Path(tempfile.mkdtemp()) / "jwt.db")
    _enable()
    with TestClient(app) as c:
        r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {_token('engineer01')}"})
        assert r.status_code == 200
        me = r.json()["user"]
        assert me["username"] == "engineer01" and me["role"] == "viewer"  # 自动建档=viewer
        # 建档后二次请求稳定
        r2 = c.get("/api/auth/me", headers={"Authorization": f"Bearer {_token('engineer01')}"})
        assert r2.status_code == 200


def test_jwt_bad_signature_rejected():
    db.use(Path(tempfile.mkdtemp()) / "jwt2.db")
    _enable()
    with TestClient(app) as c:
        bad = pyjwt.encode({"sub": "engineer01", "iss": "aiweb"}, "wrong-secret", algorithm="HS256")
        r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"})
        assert r.status_code == 401


def test_jwt_expired_rejected():
    db.use(Path(tempfile.mkdtemp()) / "jwt3.db")
    _enable()
    import time
    with TestClient(app) as c:
        tok = pyjwt.encode({"sub": "engineer01", "iss": "aiweb",
                            "exp": int(time.time()) - 3600}, "bridge-secret", algorithm="HS256")
        r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401


def test_jwt_disabled_when_off():
    db.use(Path(tempfile.mkdtemp()) / "jwt4.db")
    CFG.setdefault("auth", {})["jwt"] = {"enabled": False, "secret": "", "issuer": "aiweb"}
    with TestClient(app) as c:
        tok = pyjwt.encode({"sub": "engineer01", "iss": "aiweb"}, "bridge-secret", algorithm="HS256")
        r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401  # 桥关闭时 JWT 不被接受


def test_jwt_user_can_use_chat():
    db.use(Path(tempfile.mkdtemp()) / "jwt5.db")
    _enable()
    with TestClient(app) as c:
        tok = _token("engineer01")
        r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        chat = c.post("/api/data/query", json={"question": "机台状态怎么查"},
                      headers={"Authorization": f"Bearer {tok}"})
        assert chat.status_code == 200 and chat.json()["type"] == "sql"


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
