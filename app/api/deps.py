"""认证依赖: 从 Cookie 或 Bearer 头解析用户, 按角色门槛放行。

角色: viewer(只读问答) < user(问答+知识库导入) < admin(全部管理)。
"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request

from app.store import db

COOKIE_NAME = "fabbot_token"
ROLE_RANK = {"viewer": 0, "user": 1, "admin": 2}


def _token_from(request: Request) -> Optional[str]:
    tok = request.cookies.get(COOKIE_NAME)
    if not tok:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            tok = auth[7:].strip()
    return tok or None


def current_user(request: Request) -> Optional[dict]:
    tok = _token_from(request)
    if not tok:
        return None
    return db.resolve_token(tok)


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "未登录或登录已过期")
    return user


def require_role(request: Request, role: str = "user") -> dict:
    user = require_user(request)
    if ROLE_RANK.get(user["role"], -1) < ROLE_RANK.get(role, 99):
        raise HTTPException(403, "权限不足")
    return user


def public_user(user: dict) -> dict:
    return {k: user[k] for k in ("id", "username", "role", "display_name")}
