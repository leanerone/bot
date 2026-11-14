"""D3: Agent 端点 —— 多步工具循环, SSE 推送 agent_step 中间步骤。

独立于 /api/chat 契约之外, 前端在"Agent 模式"开关下调用;
工具循环见 app/agent/loop.py (白名单/风险分级/Hook 审计)。
"""
from __future__ import annotations

import json
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import loop as agent_loop
from app.api import audit as audit_mod
from app.api.deps import require_user
from app.api.limits import check_rate
from app.guard import prompt_guard

router = APIRouter(prefix="/api/agent")


class AgentIn(BaseModel):
    question: str
    session_id: Optional[str] = None
    history: Optional[List[dict]] = None


def _persist_agent(session_id: Optional[str], user: dict, question: str,
                   result: dict) -> Optional[str]:
    from app.store import db

    if session_id:
        session = db.get_chat_session(session_id, user_id=user["id"])
        if not session:
            raise HTTPException(404, "会话不存在或无权访问")
        db.add_message(session["id"], "user", "", question)
    else:
        session = db.create_chat_session(user["id"], question[:20] or "Agent 会话")
    db.add_message(session["id"], "assistant", "kb", result.get("answer", ""),
                   sources=result.get("sources"))
    return session["id"]


@router.post("/chat")
def agent_chat(body: AgentIn, request: Request):
    user = require_user(request)
    check_rate(user["id"])
    q = prompt_guard.sanitize(body.question.strip())
    if not q:
        raise HTTPException(400, "问题不能为空")
    t0 = time.time()
    result = agent_loop.run_agent(q, history=body.history, user=user["username"])
    sid = _persist_agent(body.session_id, user, q, result)
    audit_mod.record(user["username"], "/api/agent/chat",
                     f"agent({len(result.get('steps', []))}步)", q,
                     int((time.time() - t0) * 1000))
    return {"session_id": sid, "type": "agent", **result}


@router.post("/chat/stream")
def agent_chat_stream(body: AgentIn, request: Request):
    """SSE: meta -> agent_step* -> delta* -> done (sources 含引用)。"""
    user = require_user(request)
    check_rate(user["id"])
    q = prompt_guard.sanitize(body.question.strip())
    if not q:
        raise HTTPException(400, "问题不能为空")

    def sse(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def gen():
        t0 = time.time()
        steps_holder: list = []
        try:
            yield sse("meta", {"type": "agent"})

            def on_step(ev: dict) -> None:
                steps_holder.append(ev)

            result = agent_loop.run_agent(q, history=body.history,
                                          user=user["username"], on_step=on_step)
            for ev in steps_holder:
                yield sse("agent_step", ev)
            sid = _persist_agent(body.session_id, user, q, result)
            for chunk in _chunked(result.get("answer", "")):
                yield sse("delta", {"text": chunk})
            yield sse("done", {"sources": result.get("sources", []),
                               "steps": result.get("steps", []), "session_id": sid})
            audit_mod.record(user["username"], "/api/agent/chat/stream",
                             f"agent({len(steps_holder)}步)", q,
                             int((time.time() - t0) * 1000))
        except Exception as exc:  # noqa: BLE001
            yield sse("error", {"message": f"服务异常: {exc}"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _chunked(text: str, size: int = 24):
    """整段回答切片为打字机增量 (Agent 结果非逐 token 流, 前端体验统一)。"""
    for i in range(0, len(text), size):
        yield text[i:i + size]
