"""认证路由: 登录 / 登出 / 当前用户。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import COOKIE_NAME, _token_from, public_user, require_user
from app.config import cfg
from app.store import db

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, request: Request):
    from app.api.limits import check_login

    check_login(f"{body.username.strip()}@{request.client.host if request.client else '?'}")
    user = db.authenticate(body.username.strip(), body.password)
    if not user:
        db.log_audit(body.username.strip(), "/api/auth/login", "", "", 0, status="fail")
        raise HTTPException(401, "用户名或密码错误")
    ttl = float(cfg("auth.token_ttl_hours", 24))
    token, _ = db.issue_token(user["id"], ttl)
    resp = JSONResponse({"ok": True, "user": public_user(user)})
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax",
                    path="/", max_age=int(ttl * 3600),
                    secure=bool(cfg("auth.cookie_secure", False)))  # HTTPS 部署时置 true
    db.log_audit(user["username"], "/api/auth/login", "", "", 0)
    return resp


@router.post("/auth/logout")
def logout(request: Request):
    tok = _token_from(request)
    if tok:
        db.revoke_token(tok)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


@router.get("/auth/me")
def me(request: Request):
    user = require_user(request)
    return {"user": public_user(user)}
