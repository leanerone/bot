"""SKILL 注册表: 扫描 skills/*/SKILL.md, 校验 frontmatter, 提供发现接口。

校验规则 (docs/SKILL_SPEC.md):
- name 唯一且合法; version 存在; runtime 受支持; tools 非空; description 非空。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.config import ROOT

SUPPORTED_RUNTIME = {"mcp"}
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
_VER_RE = re.compile(r"^\d+\.\d+\.\d+")

_cache: Optional[List[Dict[str, Any]]] = None
_cache_mtime: Optional[float] = None


def skills_dir() -> Path:
    return ROOT / "skills"


def _parse_skill_md(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError("缺少 frontmatter")
    parts = raw.split("---", 2)
    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip() if len(parts) > 2 else ""
    errors: List[str] = []
    name = str(meta.get("name", ""))
    if not _NAME_RE.match(name):
        errors.append(f"name 非法: {name!r}")
    version = str(meta.get("version", ""))
    if not _VER_RE.match(version):
        errors.append(f"version 非法: {version!r}")
    runtime = str(meta.get("runtime", ""))
    if runtime not in SUPPORTED_RUNTIME:
        errors.append(f"runtime 不支持: {runtime}")
    tools = [str(t) for t in meta.get("tools", [])]
    if not tools:
        errors.append("tools 不能为空")
    if not str(meta.get("description", "")).strip():
        errors.append("description 不能为空")
    return {
        "name": name, "version": version, "runtime": runtime,
        "server": str(meta.get("server", "fabbot")),
        "tools": tools, "permissions": [str(p) for p in meta.get("permissions", [])],
        "config_schema": [str(c) for c in meta.get("config_schema", [])],
        "description": str(meta.get("description", "")),
        "body": body, "errors": errors, "path": str(path),
    }


def list_skills(force: bool = False) -> Dict[str, Any]:
    """扫描 skills 目录, 返回 {skills: [...], errors: [...]}。带 mtime 缓存。"""
    global _cache, _cache_mtime
    root = skills_dir()
    marker = root.stat().st_mtime if root.exists() else 0
    if not force and _cache is not None and _cache_mtime == marker:
        return {"skills": _cache, "errors": []}
    skills: List[Dict[str, Any]] = []
    errors: List[str] = []
    if root.exists():
        seen = set()
        for md in sorted(root.glob("*/SKILL.md")):
            try:
                s = _parse_skill_md(md)
                if s["name"] in seen:
                    errors.append(f"{md.parent.name}: name 重复 {s['name']}")
                    continue
                seen.add(s["name"])
                skills.append({k: v for k, v in s.items() if k != "path"})
            except Exception as exc:  # 单个 skill 损坏不阻塞
                errors.append(f"{md.parent.name}: {exc}")
    _cache, _cache_mtime = skills, marker
    return {"skills": skills, "errors": errors}


def get_skill(name: str) -> Optional[Dict[str, Any]]:
    for s in list_skills()["skills"]:
        if s["name"] == name:
            return s
    return None
