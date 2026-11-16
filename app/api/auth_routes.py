"""认证路由: 登录 / 登出 / 当前用户。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import COOKIE_NAME, _token_from, client_ip, public_user, require_user
from app.config import cfg
from app.store import db

router = APIRouter(prefix="/api")


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, request: Request):
    from app.api import auth_lock
    from app.api.limits import check_login

    ip = client_ip(request)  # B2: 可信代理才采信 XFF, 否则直连 IP
    uname = body.username.strip()
    check_login(f"{uname}@{ip}")
    if not auth_lock.check_admin_rate(uname):  # B1: admin 全局限速 (豁免锁定但不豁免限速)
        db.log_audit(uname, "/api/auth/login", "", "", 0, status="admin_rate")
        raise HTTPException(429, "管理员登录尝试过于频繁, 请 1 分钟后再试")
    locked = auth_lock.check_locked(uname, ip)
    if locked:
        db.log_audit(uname, "/api/auth/login", "", "", 0, status="locked")
        raise HTTPException(423, f"失败次数过多, 账号已临时锁定, 请 {max(1, locked // 60)} 分钟后再试")
    user = db.authenticate(uname, body.password)
    if not user:
        auth_lock.record_failure(body.username.strip(), ip)
        db.log_audit(body.username.strip(), "/api/auth/login", "", "", 0, status="fail")
        raise HTTPException(401, "用户名或密码错误")
    auth_lock.record_success(user["username"], ip)
    ttl = float(cfg("auth.token_ttl_hours", 24))
    from app.api.deps import ua_hash as _ua_hash
    token, _ = db.issue_token(user["id"], ttl, ua_hash=_ua_hash(request))
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


@router.post("/auth/logout_all")
def logout_all(request: Request):
    """C3: 全端登出 —— 吊销当前用户全部令牌 (换密码泄露/丢设备场景)。"""
    user = require_user(request)
    db.revoke_user_tokens(user["id"])
    db.log_audit(user["username"], "/api/auth/logout_all", "", "", 0)
    resp = JSONResponse({"ok": True, "revoked": "all"})
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


@router.get("/auth/me")
def me(request: Request):
    user = require_user(request)
    return {"user": public_user(user)}


class UpdateMe(BaseModel):
    display_name: str


class ChangePw(BaseModel):
    old_password: str
    new_password: str


@router.patch("/auth/me")
def update_me(body: UpdateMe, request: Request):
    user = require_user(request)
    db.update_user(user["id"], display_name=body.display_name.strip()[:30])
    return {"ok": True}


@router.patch("/auth/me/password")
def change_password(body: ChangePw, request: Request):
    user = require_user(request)
    if len(body.new_password) < 6:
        raise HTTPException(400, "新密码长度至少 6 位")
    if not db.authenticate(user["username"], body.old_password):
        raise HTTPException(400, "当前密码不正确")
    db.set_password(user["id"], body.new_password)  # 吊销全部令牌 -> 需重新登录
    return {"ok": True, "relogin": True}
