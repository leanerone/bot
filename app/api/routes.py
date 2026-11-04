"""HTTP 接口层 (v4.0: 认证 + 服务端会话持久化 + 反馈)。

/api/chat 与 /api/chat/stream 是统一入口 (按关键词粗分意图); 所有问答持久化到
SQLite 会话, 支持追问与历史回看。生产建议把关键词意图换成模型分类。
"""
from __future__ import annotations

import json
import re
import time
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.adapters.hcl_notes import ingest_notes_domino, ingest_notes_export
from app.api import audit as audit_mod
from app.api.deps import public_user, require_role, require_user
from app.config import abs_path, cfg
from app.llm.client import LLMError
from app.rag import pipeline
from app.rag.ingest import get_store, ingest_dir
from app.store import db
from app.sqlbot import text2sql
from app.sqlbot.validator import SQLRejected

router = APIRouter(prefix="/api")

# 意图粗分: 命中 -> 数据查询, 否则知识问答
_DATA_HINT = re.compile(
    r"多少|几个|统计|查询|查一下|排名|top|趋势|良率|wip|在制|机台|告警|报警|数量|平均|最近",
    re.I,
)


class AskIn(BaseModel):
    question: str
    session_id: Optional[str] = None
    history: Optional[List[dict]] = None


class IngestIn(BaseModel):
    path: Optional[str] = None


class NotesIngestIn(BaseModel):
    mode: Optional[str] = None      # export (默认) | domino
    path: Optional[str] = None
    view: Optional[str] = None


class SessionIn(BaseModel):
    title: Optional[str] = "新会话"


class FeedbackIn(BaseModel):
    message_id: int
    rating: str                     # up | down | none


# ── 会话辅助 ──

def _resolve_session(user: dict, session_id: Optional[str], question: str) -> dict:
    """取/建当前用户的会话, 并写入用户消息。"""
    if session_id:
        session = db.get_chat_session(session_id, user_id=user["id"])
        if not session:
            raise HTTPException(404, "会话不存在或无权访问")
    else:
        session = db.create_chat_session(user["id"], question[:20] or "新会话")
    db.add_message(session["id"], "user", "", question)
    return session


def _persist_answer(session_id: str, result: dict) -> int:
    if result.get("type") == "sql":
        return db.add_message(
            session_id, "assistant", "sql", result.get("sql", ""),
            sql=result.get("sql"), columns=result.get("columns"),
            rows=result.get("rows"), row_count=result.get("row_count"),
        )
    return db.add_message(session_id, "assistant", "kb", result.get("answer", ""),
                          sources=result.get("sources"))


# ── 统一问答入口 ──

@router.post("/chat")
def chat(body: AskIn, request: Request):
    user = require_user(request)
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "问题不能为空")
    t0 = time.time()
    session = _resolve_session(user, body.session_id, q)
    try:
        if _DATA_HINT.search(q):
            result = {"type": "sql", **text2sql.query(q, history=body.history)}
        else:
            result = {"type": "kb", **pipeline.ask(q, history=body.history)}
    except SQLRejected as exc:
        raise HTTPException(400, f"SQL 安全校验未通过: {exc}") from exc
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from exc
    mid = _persist_answer(session["id"], result)
    audit_mod.record(user["username"], "/api/chat", result.get("type"), q,
                     int((time.time() - t0) * 1000))
    return {"session_id": session["id"], "assistant_message_id": mid, **result}


@router.post("/chat/stream")
def chat_stream(body: AskIn, request: Request):
    """流式统一入口 (SSE)。事件: meta(含 session_id) -> (delta*+done | result) -> error(可选)。"""
    user = require_user(request)
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "问题不能为空")
    session = _resolve_session(user, body.session_id, q)
    history = body.history

    def sse(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def gen():
        t0 = time.time()
        intent = "kb"
        result_holder: dict = {}
        persisted = False
        try:
            if _DATA_HINT.search(q):
                intent = "sql"
                yield sse("meta", {"type": "sql", "session_id": session["id"]})
                result_holder = {"type": "sql", **text2sql.query(q, history=history)}
                mid = _persist_answer(session["id"], result_holder)
                persisted = True
                yield sse("result", {**result_holder, "message_id": mid})
            else:
                yield sse("meta", {"type": "kb", "session_id": session["id"]})
                deltas, sources = [], []
                for ev in pipeline.ask_stream(q, history=history):
                    if ev["type"] == "delta":
                        deltas.append(ev["text"])
                        yield sse("delta", {"text": ev["text"]})
                    else:
                        sources = ev.get("sources", [])
                result_holder = {"type": "kb", "answer": "".join(deltas), "sources": sources}
                mid = _persist_answer(session["id"], result_holder)
                persisted = True
                yield sse("done", {"sources": sources, "message_id": mid})
        except SQLRejected as exc:
            yield sse("error", {"message": f"SQL 安全校验未通过: {exc}"})
        except LLMError as exc:
            yield sse("error", {"message": str(exc)})
        except Exception as exc:  # 兜底: 流式链路不让服务挂掉
            yield sse("error", {"message": f"服务异常: {exc}"})
        finally:
            if result_holder and not persisted:
                try:
                    _persist_answer(session["id"], result_holder)
                except Exception:
                    pass
            audit_mod.record(user["username"], "/api/chat/stream", intent, q,
                             int((time.time() - t0) * 1000))

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/kb/ask")
def kb_ask(body: AskIn, request: Request):
    user = require_user(request)
    if body.session_id:
        session = _resolve_session(user, body.session_id, body.question.strip())
        result = {"type": "kb", **pipeline.ask(body.question.strip(), history=body.history)}
        mid = _persist_answer(session["id"], result)
        return {"session_id": session["id"], "assistant_message_id": mid, **result}
    return {"type": "kb", **pipeline.ask(body.question.strip(), history=body.history)}


@router.post("/data/query")
def data_query(body: AskIn, request: Request):
    user = require_user(request)
    try:
        result = {"type": "sql", **text2sql.query(body.question.strip(), history=body.history)}
    except SQLRejected as exc:
        raise HTTPException(400, f"SQL 安全校验未通过: {exc}") from exc
    if body.session_id:
        session = db.get_chat_session(body.session_id, user_id=user["id"])
        if not session:
            raise HTTPException(404, "会话不存在或无权访问")
        db.add_message(session["id"], "user", "", body.question.strip())
        mid = _persist_answer(session["id"], result)
        return {"session_id": session["id"], "assistant_message_id": mid, **result}
    return result


# ── 会话管理 (服务端持久化) ──

@router.get("/sessions")
def sessions(request: Request):
    user = require_user(request)
    return {"sessions": db.list_chat_sessions(user["id"])}


@router.post("/sessions")
def create_session(body: SessionIn, request: Request):
    user = require_user(request)
    return {"session": db.create_chat_session(user["id"], body.title or "新会话")}


@router.get("/sessions/{session_id}/messages")
def session_messages(session_id: str, request: Request):
    user = require_user(request)
    if not db.get_chat_session(session_id, user_id=user["id"]):
        raise HTTPException(404, "会话不存在或无权访问")
    return {"messages": db.list_messages(session_id)}


@router.patch("/sessions/{session_id}")
def rename_session(session_id: str, body: SessionIn, request: Request):
    user = require_user(request)
    if not db.rename_chat_session(session_id, body.title or "新会话", user_id=user["id"]):
        raise HTTPException(404, "会话不存在或无权访问")
    return {"ok": True}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, request: Request):
    user = require_user(request)
    if not db.delete_chat_session(session_id, user_id=user["id"]):
        raise HTTPException(404, "会话不存在或无权访问")
    return {"ok": True}


@router.post("/feedback")
def feedback(body: FeedbackIn, request: Request):
    """对 assistant 消息点赞/点踩 (质量追踪: stats 里汇总)。"""
    user = require_user(request)
    if db.message_owner(body.message_id) != user["id"]:
        raise HTTPException(403, "只能评价自己的会话消息")
    try:
        ok = db.rate_message(body.message_id, body.rating)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "消息不存在")
    return {"ok": True}


# ── 知识库 ──

@router.post("/kb/ingest")
def kb_ingest(request: Request, body: Optional[IngestIn] = None):
    user = require_role(request, "user")
    target = (body.path if body and body.path else None) or "data/knowledge"
    summary = ingest_dir(target)
    audit_mod.record(user["username"], "/api/kb/ingest", "", target, 0)
    return {"ok": True, "dir": target, **summary}


@router.post("/kb/ingest_notes")
def kb_ingest_notes(request: Request, body: Optional[NotesIngestIn] = None):
    """导入 HCL Notes 内容: mode=export 读导出目录 / mode=domino 经 Domino HTTP 拉取。"""
    user = require_role(request, "user")
    mode = (body.mode if body and body.mode else None) or cfg("notes.mode", "export")
    if mode == "domino":
        client = _notes_domino_client()
        view = (body.view if body and body.view else None) or cfg("notes.domino.view", "($All)")
        summary = ingest_notes_domino(client, view=view)
    else:
        target = (body.path if body and body.path else None) or cfg(
            "notes.export_dir", "data/notes_export"
        )
        summary = ingest_notes_export(str(abs_path(target)))
    audit_mod.record(user["username"], "/api/kb/ingest_notes", mode, "", 0)
    return {"ok": True, "mode": mode, **summary}


def _notes_domino_client():
    from app.adapters.hcl_notes import DominoNotesClient

    return DominoNotesClient(
        base_url=cfg("notes.domino.base_url", ""),
        db_path=cfg("notes.domino.db_path", ""),
        username=cfg("notes.domino.username", ""),
        password=cfg("notes.domino.password", ""),
    )


@router.get("/health")
def health():
    return {
        "status": "ok",
        "kb_chunks": len(get_store()),
        "llm": {"mock": bool(cfg("llm.mock", True)), "model": cfg("llm.model", "")},
        "notes_mode": cfg("notes.mode", "export"),
        "version": "4.0.0",
    }
