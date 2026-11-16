"""HTTP 接口层 (v4.0: 认证 + 服务端会话持久化 + 反馈)。

/api/chat 与 /api/chat/stream 是统一入口 (按关键词粗分意图); 所有问答持久化到
SQLite 会话, 支持追问与历史回看。生产建议把关键词意图换成模型分类。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.adapters.hcl_notes import (ingest_notes_domino, ingest_notes_domino_multi,
                                    ingest_notes_export)
from app.api import audit as audit_mod
from app.api.deps import require_role, require_user
from app.api.intent import classify_smart
from app.api.limits import check_rate
from app.bots.registry import get_bot as get_bot_def
from app.config import ROOT, abs_path, cfg
from app.guard import prompt_guard
from app.llm.client import LLMError, degraded_status
from app.rag import pipeline
from app.rag.ingest import get_store, ingest_dir
from app.store import db
from app.sqlbot import text2sql
from app.sqlbot.validator import SQLRejected

router = APIRouter(prefix="/api")


def _guard_scan(user: dict, q: str, api: str) -> str:
    """C1 注入扫描 (纵深第 1 层): 剥伪造分隔符 + 命中特征审计留痕, 不阻断正常问答。"""
    cleaned = prompt_guard.sanitize(q)
    verdict = prompt_guard.scan(q)
    if verdict["injection"]:
        audit_mod.record(user["username"], api, "injection",
                         f"tags={','.join(verdict['tags'])}; q={cleaned[:160]}", 0)
    return cleaned


class AskIn(BaseModel):
    question: str = Field(max_length=4000)  # 问题长度上限: 防超长 prompt 成本攻击
    session_id: Optional[str] = None
    history: Optional[List[dict]] = None
    bot_id: Optional[str] = None  # 联系人式智能体 (app/bots/registry.py)


class IngestIn(BaseModel):
    path: Optional[str] = None


class NotesIngestIn(BaseModel):
    mode: Optional[str] = None      # export (默认) | domino
    path: Optional[str] = None
    view: Optional[str] = None
    full: Optional[bool] = None     # true=全量重拉 (默认增量)


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
    if body.bot_id and not get_bot_def(body.bot_id):
        raise HTTPException(400, f"未知 bot: {body.bot_id}")
    check_rate(user["id"])
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "问题不能为空")
    q = _guard_scan(user, q, "/api/chat")
    t0 = time.time()
    session = _resolve_session(user, body.session_id, q)
    try:
        if classify_smart(q)["intent"] == "sql":
            result = {"type": "sql", **text2sql.query(q, history=body.history)}
        else:
            result = {"type": "kb", **pipeline.ask(q, history=body.history, bot_id=body.bot_id)}
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
    check_rate(user["id"])
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "问题不能为空")
    q = _guard_scan(user, q, "/api/chat/stream")
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
            if classify_smart(q)["intent"] == "sql":
                intent = "sql"
                yield sse("meta", {"type": "sql", "session_id": session["id"]})
                yield sse("step", {"label": "生成 SQL (语义层 + 会话历史)"})
                result_holder = {"type": "sql", **text2sql.query(q, history=history)}
                yield sse("step", {"label": "安全校验 (白名单 + 只读连接)"})
                mid = _persist_answer(session["id"], result_holder)
                persisted = True
                yield sse("step", {"label": f"只读执行完成 · {result_holder.get('row_count', 0)} 行"})
                yield sse("result", {**result_holder, "message_id": mid})
            else:
                yield sse("meta", {"type": "kb", "session_id": session["id"]})
                yield sse("step", {"label": "检索知识库 (向量+BM25 混合)"})
                deltas, sources = [], []
                for ev in pipeline.ask_stream(q, history=history):
                    if ev["type"] == "delta":
                        deltas.append(ev["text"])
                        yield sse("delta", {"text": ev["text"]})
                    else:
                        sources = ev.get("sources", [])
                        yield sse("step", {"label": "整理引用来源"})
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
    check_rate(user["id"])
    if body.bot_id and not get_bot_def(body.bot_id):
        raise HTTPException(400, f"未知 bot: {body.bot_id}")
    q = body.question.strip()
    q = _guard_scan(user, q, "/api/kb/ask")
    t0 = time.time()
    result = {"type": "kb", **pipeline.ask(q, history=body.history, bot_id=body.bot_id)}
    if body.session_id:
        session = db.get_chat_session(body.session_id, user_id=user["id"])
        if not session:
            raise HTTPException(404, "会话不存在或无权访问")
        db.add_message(session["id"], "user", "", q)
        mid = _persist_answer(session["id"], result)
        audit_mod.record(user["username"], "/api/kb/ask", "kb", q,
                         int((time.time() - t0) * 1000))
        return {"session_id": session["id"], "assistant_message_id": mid, **result}
    audit_mod.record(user["username"], "/api/kb/ask", "kb", q,
                     int((time.time() - t0) * 1000))
    return result


@router.post("/data/query")
def data_query(body: AskIn, request: Request):
    user = require_user(request)
    check_rate(user["id"])
    q = body.question.strip()
    q = _guard_scan(user, q, "/api/data/query")
    t0 = time.time()
    try:
        result = {"type": "sql", **text2sql.query(q, history=body.history)}
    except SQLRejected as exc:
        audit_mod.record(user["username"], "/api/data/query", "sql", q,
                         int((time.time() - t0) * 1000), status="rejected")
        raise HTTPException(400, f"SQL 安全校验未通过: {exc}") from exc
    if body.session_id:
        session = db.get_chat_session(body.session_id, user_id=user["id"])
        if not session:
            raise HTTPException(404, "会话不存在或无权访问")
        db.add_message(session["id"], "user", "", q)
        mid = _persist_answer(session["id"], result)
        audit_mod.record(user["username"], "/api/data/query", "sql", q,
                         int((time.time() - t0) * 1000))
        return {"session_id": session["id"], "assistant_message_id": mid, **result}
    audit_mod.record(user["username"], "/api/data/query", "sql", q,
                     int((time.time() - t0) * 1000))
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
def session_messages(session_id: str, request: Request, limit: int = 50,
                     before_id: Optional[int] = None):
    """分页取消息: 默认最近 50 条; 更早消息用 before_id (最早一条的 id) 翻页。"""
    user = require_user(request)
    if not db.get_chat_session(session_id, user_id=user["id"]):
        raise HTTPException(404, "会话不存在或无权访问")
    limit = min(max(limit, 1), 200)
    return db.list_messages(session_id, limit=limit, before_id=before_id)


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

def _safe_kb_dir(path: Optional[str], default: str) -> str:
    """知识导入路径白名单: 必须位于项目根目录内 (防路径穿越)。

    用 relative_to 而非 startswith —— 后者对同级前缀目录 (如 bot-other) 误放行。
    """
    target = abs_path(path or default).resolve()
    root = ROOT.resolve()
    if target != root and root not in target.parents:
        raise HTTPException(400, "路径越界: 只允许导入项目目录内的文档")
    return str(target)


# 拖拽上传上限: 原始文件 10MB (base64 约膨胀 4/3)
MAX_UPLOAD_B64_CHARS = 14_000_000


class UploadIn(BaseModel):
    name: str
    b64: str  # base64 文件内容 (拖拽上传)


@router.post("/kb/upload")
def kb_upload(request: Request, body: UploadIn):
    """拖拽上传文档: base64 -> 保存到 data/knowledge -> 立即解析入库。"""
    import base64
    import uuid

    user = require_role(request, "user")
    name = Path(body.name).name  # 防路径穿越
    if not name.lower().endswith((".md", ".txt", ".docx", ".pdf")):
        raise HTTPException(400, "仅支持 .md/.txt/.docx/.pdf")
    if len(body.b64) > MAX_UPLOAD_B64_CHARS:
        raise HTTPException(413, "文件过大 (原始文件上限 10MB)")
    target_dir = abs_path(cfg("rag.knowledge_path", "data/knowledge"))
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex[:6]}_{name}"
    # B7: 同名文档版本替换 —— 清掉旧版本 (uuid6_原名 或 legacy 原名) 的片段与文件,
    # 否则更新版 SOP 上传后旧版残留, 检索可能引用过期规程 (工厂场景高风险)。
    old_pat = re.compile(rf"(?:[0-9a-f]{{6}}_)?{re.escape(name)}")
    store = get_store()
    for old in target_dir.iterdir():
        if old.is_file() and old != target and old_pat.fullmatch(old.name):
            store.delete_by_source(old.name)
            old.unlink()
    try:
        target.write_bytes(base64.b64decode(body.b64))
    except Exception as exc:
        raise HTTPException(400, f"文件内容解码失败: {exc}") from exc
    summary = ingest_dir(str(target_dir))
    audit_mod.record(user["username"], "/api/kb/upload", "", name, 0)
    return {"ok": True, "saved": target.name, **summary}


@router.get("/bots")
def list_bots(request: Request):
    """联系人式智能体清单 (bots-as-contacts, 借鉴 OpenMausBot)。"""
    require_user(request)
    from app.bots.registry import list_bots as _list

    return {"bots": _list()}


@router.post("/kb/ingest")
def kb_ingest(request: Request, body: Optional[IngestIn] = None):
    user = require_role(request, "user")
    target = _safe_kb_dir(body.path if body and body.path else None, "data/knowledge")
    summary = ingest_dir(target)
    audit_mod.record(user["username"], "/api/kb/ingest", "", target, 0)
    return {"ok": True, "dir": target, **summary}


@router.post("/kb/ingest_notes")
def kb_ingest_notes(request: Request, body: Optional[NotesIngestIn] = None):
    """导入 HCL Notes 内容: mode=export 读导出目录 / mode=domino 经 Domino HTTP 拉取。"""
    user = require_role(request, "user")
    mode = (body.mode if body and body.mode else None) or cfg("notes.mode", "export")
    if mode == "domino":
        incremental = not (body and body.full is True)
        multi = cfg("notes.databases") or []
        if multi and not (body and body.view):
            # B5 多库: notes.databases 数组逐库拉取 (显式 view 时退回单库)
            summary = ingest_notes_domino_multi(multi, incremental=incremental)
        else:
            client = _notes_domino_client()
            view = (body.view if body and body.view else None) or cfg("notes.domino.view", "($All)")
            summary = ingest_notes_domino(client, view=view, incremental=incremental)
    else:
        target = _safe_kb_dir(
            body.path if body and body.path else None, cfg("notes.export_dir", "data/notes_export")
        )
        summary = ingest_notes_export(target)
    audit_mod.record(user["username"], "/api/kb/ingest_notes", mode, "", 0)
    return {"ok": True, "mode": mode, **summary}


def _notes_domino_client():
    from app.adapters.hcl_notes import domino_client_from_config

    return domino_client_from_config()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "kb_chunks": len(get_store()),
        "llm": {"mock": bool(cfg("llm.mock", True)), "model": cfg("llm.model", ""),
                "degraded": degraded_status()},  # B8: 云端故障降级态 (前端标黄)
        "notes_mode": cfg("notes.mode", "export"),
        "version": "4.4.1",
    }
