"""admin 配置读写: 白名单键 + PyYAML 往返 + 写前备份。

安全: 密码/webhook/api_key 类键永不出现在 GET 返回中; PUT 只接受白名单键。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import require_role
from app.config import ROOT, abs_path

router = APIRouter(prefix="/api/admin")

# 可读写白名单: 点路径 -> 类型
EDITABLE: Dict[str, type] = {
    "llm.mock": bool,
    "llm.model": str,
    "rag.top_k": int,
    "rag.hybrid": bool,
    "ratelimit.chat_per_minute": int,
    "ratelimit.login_per_5min": int,
    "watcher.enabled": bool,
    "watcher.interval_minutes": int,
    "watcher.platform": str,
    "notes.mode": str,
}


def _config_path() -> Path:
    return abs_path("config.yaml")


def _get_nested(cfg: Dict[str, Any], dotted: str) -> Any:
    node: Any = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _set_nested(cfg: Dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = cfg
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


@router.get("/config")
def get_config(request: Request):
    require_role(request, "admin")
    path = _config_path()
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {k: _get_nested(cfg, k) for k in EDITABLE}
    return {"config": out, "editable": list(EDITABLE.keys()),
            "path": str(path), "restart_hint": "llm.* / watcher.* / rag.* 变更需重启服务生效"}


@router.put("/config")
def put_config(body: dict, request: Request):
    admin = require_role(request, "admin")
    path = _config_path()
    if path.exists():
        shutil.copy2(path, path.with_suffix(".yaml.bak"))  # 写前备份
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    applied, rejected = [], []
    for key, value in (body or {}).items():
        if key not in EDITABLE:
            rejected.append(key)
            continue
        expected = EDITABLE[key]
        if expected is bool and not isinstance(value, bool):
            rejected.append(key)
            continue
        if expected is int:
            try:
                value = int(value)
            except (TypeError, ValueError):
                rejected.append(key)
                continue
        if expected is str:
            value = str(value)
        _set_nested(cfg, key, value)
        applied.append(key)

    if rejected:
        raise HTTPException(400, f"以下键被拒绝 (未在白名单或类型错误): {rejected}")

    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    from app.api.audit import record as audit_record
    audit_record(admin["username"], "/api/admin/config", "", f"applied={applied}", 0)
    return {"ok": True, "applied": applied,
            "restart_hint": "llm.* / watcher.* 变更需重启服务生效"}
