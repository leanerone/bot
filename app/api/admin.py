"""管理路由 (admin): 用户管理 / 审计查询 / 统计 / 知识库重建。"""
from __future__ import annotations

import shutil
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import public_user, require_role
from app.config import abs_path, cfg
from app.rag.ingest import get_store, ingest_dir, reset_store
from app.store import db

router = APIRouter(prefix="/api/admin")


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "user"
    display_name: str = ""


class UserPatch(BaseModel):
    role: Optional[str] = None
    disabled: Optional[bool] = None
    display_name: Optional[str] = None


class PasswordIn(BaseModel):
    password: str


class NotifyIn(BaseModel):
    platform: str = "wechat"        # wechat | dingtalk | both
    text: str


# ── 告警推送测试 ──

@router.post("/notify/test")
def notify_test(body: NotifyIn, request: Request):
    """向群机器人发送一条测试消息 (admin), 验证 webhook 配置。"""
    admin = require_role(request, "admin")
    from app.notify import webhook
    try:
        result = webhook.send(body.platform, body.text or "Fab Bot 推送测试", user=admin["username"])
    except webhook.NotifyError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "result": result}


# ── 用户管理 ──

@router.get("/users")
def list_users(request: Request):
    require_role(request, "admin")
    return {"users": db.list_users()}


@router.post("/users")
def create_user(body: UserIn, request: Request):
    require_role(request, "admin")
    if body.role not in ("viewer", "user", "admin"):
        raise HTTPException(400, f"非法角色: {body.role}")
    try:
        user = db.create_user(body.username.strip(), body.password,
                              role=body.role, display_name=body.display_name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "user": public_user(user)}


@router.patch("/users/{user_id}")
def patch_user(user_id: str, body: UserPatch, request: Request):
    admin = require_role(request, "admin")
    if user_id == admin["id"] and (body.disabled or (body.role and body.role != "admin")):
        raise HTTPException(400, "不能降级/禁用自己的管理员账号 (防锁定)")
    if not db.update_user(user_id, role=body.role, disabled=body.disabled,
                          display_name=body.display_name):
        raise HTTPException(404, "用户不存在")
    return {"ok": True}


@router.patch("/users/{user_id}/password")
def reset_password(user_id: str, body: PasswordIn, request: Request):
    require_role(request, "admin")
    try:
        db.set_password(user_id, body.password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


# ── 审计与统计 ──

@router.get("/audit")
def audit_list(request: Request, limit: int = 200, user: Optional[str] = None):
    require_role(request, "admin")
    return {"audit": db.list_audit(min(max(limit, 1), 1000), user=user)}


@router.get("/stats")
def stats(request: Request):
    require_role(request, "admin")
    data = db.stats()
    data["kb_chunks"] = len(get_store())
    data["llm"] = {"mock": bool(cfg("llm.mock", True)), "model": cfg("llm.model", "")}
    return data


# ── 知识库重建 ──

@router.post("/kb/rebuild")
def kb_rebuild(request: Request):
    """清空向量库并从知识目录 + Notes 导出目录全量重建 (admin)。"""
    require_role(request, "admin")
    store_dir = abs_path(cfg("rag.store_path", "data/vector_store"))
    if store_dir.exists():
        shutil.rmtree(store_dir)
    reset_store()
    summary = {"knowledge": ingest_dir(cfg("rag.knowledge_path", "data/knowledge"))}
    notes_dir = abs_path(cfg("notes.export_dir", "data/notes_export"))
    if notes_dir.exists() and any(notes_dir.glob("*.json")):
        from app.adapters.hcl_notes import ingest_notes_export
        summary["notes"] = ingest_notes_export(str(notes_dir))
    summary["kb_chunks"] = len(get_store())
    return {"ok": True, **summary}


@router.get("/kb/sources")
def kb_sources(request: Request):
    require_role(request, "admin")
    return {"sources": get_store().list_sources()}


@router.delete("/kb/sources")
def kb_delete_source(request: Request, name: str):
    """按来源删除知识片段 (文档下线/换版)。磁盘文档不受影响, 可重新导入。"""
    require_role(request, "admin")
    removed = get_store().delete_by_source(name)
    return {"ok": True, "removed": removed, "kb_chunks": len(get_store())}
