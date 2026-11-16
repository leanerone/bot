"""D3: Agent 端点 —— 多步工具循环, SSE 推送 agent_step 中间步骤。

独立于 /api/chat 契约之外, 前端在"Agent 模式"开关下调用;
工具循环见 app/agent/loop.py (白名单/风险分级/Hook 审计)。
"""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent import loop as agent_loop
from app.api import audit as audit_mod
from app.api.deps import require_user
from app.api.limits import check_rate
from app.api.routes import _guard_scan  # C1 注入扫描: 与 /api/chat 共用同一实现

router = APIRouter(prefix="/api/agent")


class AgentIn(BaseModel):
    question: str = Field(max_length=4000)  # 问题长度上限: 防超长 prompt 成本攻击
    session_id: Optional[str] = None
    history: Optional[List[dict]] = None


def _open_agent_session(session_id: Optional[str], user: dict, question: str) -> dict:
    """取/建会话并落库用户提问 (与 /api/chat 的 _resolve_session 对齐)。"""
    from app.store import db

    if session_id:
        session = db.get_chat_session(session_id, user_id=user["id"])
        if not session:
            raise HTTPException(404, "会话不存在或无权访问")
    else:
        session = db.create_chat_session(user["id"], question[:20] or "Agent 会话")
    db.add_message(session["id"], "user", "", question)
    return session


def _persist_agent(session_id: Optional[str], user: dict, question: str,
                   result: dict) -> tuple:
    from app.store import db

    session = _open_agent_session(session_id, user, question)
    mid = db.add_message(session["id"], "assistant", "kb", result.get("answer", ""),
                         sources=result.get("sources"))
    return session["id"], mid


@router.post("/chat")
def agent_chat(body: AgentIn, request: Request):
    user = require_user(request)
    check_rate(user["id"])
    q = _guard_scan(user, body.question.strip(), "/api/agent/chat")
    if not q:
        raise HTTPException(400, "问题不能为空")
    t0 = time.time()
    result = agent_loop.run_agent(q, history=body.history, user=user["username"])
    sid, mid = _persist_agent(body.session_id, user, q, result)
    audit_mod.record(user["username"], "/api/agent/chat",
                     f"agent({len(result.get('steps', []))}步)", q,
                     int((time.time() - t0) * 1000))
    return {"session_id": sid, "assistant_message_id": mid, "type": "agent", **result}


@router.post("/chat/stream")
def agent_chat_stream(body: AgentIn, request: Request):
    """SSE: meta -> agent_step*(执行中实时推送) -> delta* -> done (sources 含引用)。

    工具循环在工作线程执行, 步骤事件经队列实时转发 —— 不再等 run_agent
    返回后一次性回放, 真实 LLM 多步执行期间前端能看到步骤推进。
    """
    user = require_user(request)
    check_rate(user["id"])
    q = _guard_scan(user, body.question.strip(), "/api/agent/chat/stream")
    if not q:
        raise HTTPException(400, "问题不能为空")
    # A2: 提前建会话并落库提问 —— meta 即可带 session_id (前端认领会话, 不再产生孤儿),
    # 与 /api/chat/stream 契约一致; 无效会话在此即返回 404。
    session = _open_agent_session(body.session_id, user, q)
    sid = session["id"]

    def sse(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def gen():
        from app.store import db

        t0 = time.time()
        events: "queue.Queue[dict]" = queue.Queue()
        result_holder: dict = {}
        error_holder: list = []
        n_steps = 0

        def on_step(ev: dict) -> None:
            events.put({"kind": "step", "ev": ev})

        def work() -> None:
            try:
                result_holder["r"] = agent_loop.run_agent(
                    q, history=body.history, user=user["username"], on_step=on_step)
            except Exception as exc:  # noqa: BLE001
                error_holder.append(exc)
            finally:
                events.put({"kind": "done"})

        threading.Thread(target=work, daemon=True).start()
        try:
            yield sse("meta", {"type": "agent", "session_id": sid})
            while True:
                try:
                    item = events.get(timeout=15)
                except queue.Empty:
                    yield sse("ping", {"t": int(time.time() * 1000)})  # 保活, 防代理空闲断流
                    continue
                if item["kind"] == "done":
                    break
                n_steps += 1
                yield sse("agent_step", item["ev"])
            if error_holder:
                raise error_holder[0]
            result = result_holder["r"]
            mid = db.add_message(sid, "assistant", "kb", result.get("answer", ""),
                                 sources=result.get("sources"))
            for chunk in _chunked(result.get("answer", "")):
                yield sse("delta", {"text": chunk})
            yield sse("done", {"sources": result.get("sources", []),
                               "steps": result.get("steps", []),
                               "session_id": sid, "message_id": mid})  # A2: 补 message_id 供反馈
            audit_mod.record(user["username"], "/api/agent/chat/stream",
                             f"agent({n_steps}步)", q,
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
