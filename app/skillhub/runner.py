"""D4: Skill 执行器 v0.1 —— SKILL.md 声明能力, 宿主注入环境, 受控执行。

约定 (FabAI-Hub 决策 D3/D4):
- skill 只声明"做什么" (frontmatter.tools 指向宿主工具); runtime=mcp 时映射到
  MCP 工具同源的内部实现 (app.agent.loop.TOOLS / mcp_server 同一套底层);
- 权限 permissions 里出现 db.write / file.write 等写权限时 → requires_confirm,
  v0.1 内置技能全部只读, 确认卡接口预留 (写确认卡 API 见计划);
- 受控执行: 子进程隔离留给 v0.2 (当前工具实现均为进程内只读函数),
  超时受控 + 输出截断 + 全量审计;
- 密钥注入: skillhub.secrets 配置 (Fernet 加密值) 运行时解密, 不落日志。
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

from app.api.audit import record as audit_record
from app.config import cfg
from app.skillhub import registry

RUN_TIMEOUT_S = 30
OUTPUT_MAX_CHARS = 20000

# skill.tools 里的工具名 (MCP 名) → Agent 循环工具名 (与 MCP 工具同源实现)
_MCP_ALIASES = {
    "rag_search": "kb_search",
    "kb_search": "kb_search",
    "text2sql_query": "sql_query",
    "sql_query": "sql_query",
    "alarms_open": "alarms_open",
    "watcher_summary": "alarms_open",
    "shift_report": "shift_report",
}
_DEFAULT_ARGS = {
    "kb_search": {"query": ""},
    "sql_query": {"question": ""},
    "alarms_open": {"hours": 168},
    "shift_report": {"hours": 8},
}
_TOOLMAP = None


def _toolmap() -> Any:
    global _TOOLMAP
    if _TOOLMAP is None:
        from app.agent.loop import call_tool

        _TOOLMAP = call_tool
    return _TOOLMAP


def _decrypt_secrets() -> Dict[str, str]:
    """从 config skillhub.secrets 取密钥 (Fernet 加密值 → 解密; 明文直接用, 仅内网自用)。"""
    raw = cfg("skillhub.secrets", {}) or {}
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(v, str) and v.startswith("fernet:"):
            try:
                from cryptography.fernet import Fernet

                key = cfg("skillhub.fernet_key", "")
                out[k] = Fernet(key.encode()).decrypt(v[7:].encode()).decode()
            except Exception:
                out[k] = ""  # 解密失败宁可为空, 不抛栈
        else:
            out[k] = v
    return out


def _validate(s: Dict[str, Any]) -> Optional[str]:
    for field in ("name", "version", "runtime", "tools"):
        if not s.get(field):
            return f"frontmatter 缺少 {field}"
    if s.get("runtime") != "mcp":
        return f"runtime 仅支持 mcp (当前: {s.get('runtime')})"
    return None


def run_skill(name: str, user: str = "system",
              args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """执行一个 skill: 校验 → 调用其声明的工具 → 审计。"""
    skill = registry.get_skill(name)
    if not skill:
        return {"ok": False, "error": f"skill 不存在: {name}"}
    if skill.get("errors"):
        return {"ok": False, "error": "skill 定义未通过校验", "errors": skill["errors"]}
    invalid = _validate(skill)
    if invalid:
        return {"ok": False, "error": invalid}

    mcp_tool = (skill.get("tools") or [None])[0]
    tool = _MCP_ALIASES.get(mcp_tool)
    if not tool:
        return {"ok": False, "error": f"skill 声明的工具 {mcp_tool} 不在宿主白名单"}
    call = _toolmap()
    merged = {**_DEFAULT_ARGS.get(tool, {}), **(args or {})}
    holder: Dict[str, Any] = {}

    def _run() -> None:
        holder["r"] = call(tool, merged, user=user)

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(RUN_TIMEOUT_S)
    if th.is_alive():
        result = {"ok": False, "error": f"skill 执行超时 ({RUN_TIMEOUT_S}s)"}
    else:
        result = holder.get("r", {"ok": False, "error": "无结果"})

    # 输出截断 (受控执行)
    data = result.get("data")
    if isinstance(data, (dict, list)):
        data = json.loads(json.dumps(data, ensure_ascii=False)[:OUTPUT_MAX_CHARS] or "{}")
        result["data"] = data
    audit_record(user, f"/skillhub/run/{name}", "skill",
                 f"tool={mcp_tool}; args={json.dumps(merged, ensure_ascii=False)[:120]}",
                 0, status="ok" if result.get("ok") else "fail")
    return result
