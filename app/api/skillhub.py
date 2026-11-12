"""Skill 发现接口: Agent/平台经此发现可用 skill（注册表只读; 启停管理后续版本）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from app.api.deps import require_user
from app.skillhub import registry

router = APIRouter(prefix="/api")


@router.get("/skills")
def list_skills(request: Request, force: Optional[bool] = None):
    require_user(request)
    data = registry.list_skills(force=bool(force))
    ok = not data["errors"] and bool(data["skills"])
    return {"ok": ok, "count": len(data["skills"]),
            "skills": data["skills"], "errors": data["errors"]}


@router.get("/{name}")
def get_skill(name: str, request: Request):
    require_user(request)
    s = registry.get_skill(name)
    if not s:
        raise HTTPException(404, f"skill 不存在: {name}")
    if s["errors"]:
        raise HTTPException(422, {"message": "skill 定义未通过校验", "errors": s["errors"]})
    return {"skill": s}
