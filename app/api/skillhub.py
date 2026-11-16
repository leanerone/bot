"""Skill 发现接口: Agent/平台经此发现可用 skill（注册表只读; 启停管理后续版本）。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import require_role, require_user
from app.skillhub import registry
from app.store import db

router = APIRouter(prefix="/api")


@router.get("/skills")
def list_skills(request: Request, force: Optional[bool] = None):
    require_user(request)
    data = registry.list_skills(force=bool(force))
    ok = not data["errors"] and bool(data["skills"])
    return {"ok": ok, "count": len(data["skills"]),
            "skills": data["skills"], "errors": data["errors"]}


# 注意: 必须用 /skills/{name} 而非 /{name} —— 后者是单段通配, 会遮蔽 /api 下后续注册的同级 GET
@router.get("/skills/{name}")
def get_skill(name: str, request: Request):
    require_user(request)
    s = registry.get_skill(name)
    if not s:
        raise HTTPException(404, f"skill 不存在: {name}")
    if s["errors"]:
        raise HTTPException(422, {"message": "skill 定义未通过校验", "errors": s["errors"]})
    return {"skill": s}


@router.get("/skills/{name}/runs")
def skill_runs(name: str, request: Request, limit: int = 20):
    """D5: 当前用户对该技能的最近执行审计 (治理回看)。"""
    user = require_user(request)
    limit = min(max(limit, 1), 100)
    rows = db.list_audit(limit=500, user=user["username"])
    runs = [{"ts": r["ts"], "status": r["status"], "ms": r["ms"], "args": r["question"]}
            for r in rows if r["api"] == f"/skillhub/run/{name}"][:limit]
    return {"runs": runs}


class SkillRunIn(BaseModel):
    args: Optional[Dict[str, Any]] = None


@router.post("/skills/{name}/run")
def run_skill_endpoint(name: str, request: Request, body: Optional[SkillRunIn] = None):
    """D4/D5: 执行技能 (受控执行 + 全量审计); 权限 user+ (viewer 只读不可执行)。"""
    from app.skillhub import runner

    user = require_role(request, "user")
    return runner.run_skill(name, user=user["username"], args=(body.args if body else None))
