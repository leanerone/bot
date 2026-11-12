"""任务中心 API: 告警值守面板数据 (桌面端 Tasks 模块)。

告警来源走 MES 适配器 (演示库/真实中间库), 只读。
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import require_user
from app.store import db

router = APIRouter(prefix="/api/tasks")


def _adapter():
    from app.adapters.mock_mes import MockMESAdapter

    return MockMESAdapter()


def _summarize(alarms: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "total": len(alarms),
        "critical": sum(1 for a in alarms if a.get("level") == "CRITICAL"),
        "alarm": sum(1 for a in alarms if a.get("level") == "ALARM"),
        "warn": sum(1 for a in alarms if a.get("level") == "WARN"),
    }


@router.get("/alarms")
def open_alarms(request: Request, hours: int = 24 * 7):
    """当前未处理告警 + 分级汇总 (值守面板主数据)。"""
    require_user(request)
    alarms = _adapter().get_alarms(hours=hours, only_open=True)
    by_eqp: Dict[str, int] = {}
    for a in alarms:
        by_eqp[a.get("eqp_id", "?")] = by_eqp.get(a.get("eqp_id", "?"), 0) + 1
    top_eqp = sorted(by_eqp.items(), key=lambda kv: -kv[1])[:6]
    return {"alarms": alarms, "summary": _summarize(alarms), "by_eqp": top_eqp}


@router.get("/summary")
def tasks_summary(request: Request):
    """任务中心概览卡数据。"""
    require_user(request)
    alarms = _adapter().get_alarms(hours=24 * 7, only_open=True)
    return {"alarms": _summarize(alarms), "wip": _adapter().get_wip_count()}


@router.get("/alarms/since")
def alarms_since(request: Request, after_id: int = 0, levels: str = "CRITICAL,ALARM",
                 limit: int = 100):
    """通知轮询: 按告警 id 游标取新增未处理告警 (时区免疫, 前端本地保存游标)。"""
    require_user(request)
    level_list = [x.strip().upper() for x in levels.split(",") if x.strip()]
    alarms = _adapter().get_alarms_since(after_id=after_id, levels=level_list,
                                         limit=min(max(limit, 1), 200))
    last_id = alarms[-1]["id"] if alarms else after_id
    return {"alarms": alarms, "last_id": last_id}


@router.get("/shift-report")
def shift_report(request: Request, hours: int = 12):
    """交班报告: 告警/良率/WIP 聚合, 返回结构化数据 + Markdown 文本。"""
    require_user(request)
    from app.services.shift_report import build_shift_report

    return build_shift_report(hours=min(max(hours, 1), 72))


# ── 我的任务 (CRUD) ──

class TaskIn(BaseModel):
    title: str
    detail: str = ""
    kind: str = "followup"      # report | alarm-review | followup
    due_at: str | None = None


class TaskPatch(BaseModel):
    status: str | None = None
    title: str | None = None
    due_at: str | None = None


@router.get("/list")
def list_my_tasks(request: Request, status: str | None = None):
    user = require_user(request)
    return {"tasks": db.list_tasks(user["id"], status=status)}


@router.post("/list")
def create_task(body: TaskIn, request: Request):
    user = require_user(request)
    try:
        task = db.add_task(user["id"], body.title.strip(), body.detail,
                           kind=body.kind, due_at=body.due_at)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"task": task}


@router.patch("/list/{task_id}")
def patch_task(task_id: int, body: TaskPatch, request: Request):
    user = require_user(request)
    try:
        ok = db.update_task(task_id, user["id"], status=body.status,
                            title=body.title, due_at=body.due_at)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "任务不存在或无权修改")
    return {"ok": True}


@router.delete("/list/{task_id}")
def delete_task(task_id: int, request: Request):
    user = require_user(request)
    if not db.delete_task(task_id, user["id"]):
        raise HTTPException(404, "任务不存在或无权删除")
    return {"ok": True}

