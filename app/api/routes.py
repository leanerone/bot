"""HTTP 接口层。

/api/chat 是统一入口 (按关键词粗分意图); 生产建议换成模型意图分类,
并按登录用户的角色做数据权限过滤 (现在通过 X-User 头演示审计留痕)。
"""
from __future__ import annotations

import re
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.adapters.hcl_notes import ingest_notes_domino, ingest_notes_export
from app.api.audit import log
from app.config import abs_path, cfg
from app.llm.client import LLMError
from app.rag import pipeline
from app.rag.ingest import get_store, ingest_dir
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


class IngestIn(BaseModel):
    path: Optional[str] = None


class NotesIngestIn(BaseModel):
    mode: Optional[str] = None      # export (默认) | domino
    path: Optional[str] = None      # mode=export 时的导出目录, 默认取 config
    view: Optional[str] = None      # mode=domino 时的视图名


@router.post("/chat")
def chat(body: AskIn, request: Request):
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "问题不能为空")
    t0 = time.time()
    try:
        if _DATA_HINT.search(q):
            result = {"type": "sql", **text2sql.query(q)}
        else:
            result = {"type": "kb", **pipeline.ask(q)}
    except SQLRejected as exc:
        raise HTTPException(400, f"SQL 安全校验未通过: {exc}") from exc
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from exc
    log({
        "user": request.headers.get("X-User", "anonymous"),
        "api": "/api/chat",
        "intent": result.get("type"),
        "question": q,
        "ms": int((time.time() - t0) * 1000),
    })
    return result


@router.post("/kb/ask")
def kb_ask(body: AskIn):
    """知识问答直连入口 (跳过意图路由)。"""
    return {"type": "kb", **pipeline.ask(body.question.strip())}


@router.post("/data/query")
def data_query(body: AskIn):
    """数据查询直连入口 (跳过意图路由)。"""
    return {"type": "sql", **text2sql.query(body.question.strip())}


@router.post("/kb/ingest")
def kb_ingest(body: Optional[IngestIn] = None):
    """导入知识文档: 默认 data/knowledge, 导入后立即可问。"""
    target = (body.path if body and body.path else None) or "data/knowledge"
    summary = ingest_dir(target)
    return {"ok": True, "dir": target, **summary}


@router.post("/kb/ingest_notes")
def kb_ingest_notes(body: Optional[NotesIngestIn] = None):
    """导入 HCL Notes 内容。

    mode=export (推荐): 读取导出目录 JSON (由 tools/export_notes_com.py 或
                        Domino 导出代理生成), 支持附件与 notes:// 链接解析;
    mode=domino:        经 Domino HTTP 只读拉取 (需管理员开通服务账号)。
    """
    mode = (body.mode if body and body.mode else None) or cfg("notes.mode", "export")
    if mode == "domino":
        from app.adapters.hcl_notes import DominoNotesClient

        client = DominoNotesClient(
            base_url=cfg("notes.domino.base_url", ""),
            db_path=cfg("notes.domino.db_path", ""),
            username=cfg("notes.domino.username", ""),
            password=cfg("notes.domino.password", ""),
        )
        view = (body.view if body and body.view else None) or cfg("notes.domino.view", "($All)")
        summary = ingest_notes_domino(client, view=view)
    else:
        target = (body.path if body and body.path else None) or cfg(
            "notes.export_dir", "data/notes_export"
        )
        summary = ingest_notes_export(str(abs_path(target)))
    return {"ok": True, "mode": mode, **summary}


@router.get("/health")
def health():
    return {"status": "ok", "kb_chunks": len(get_store())}
