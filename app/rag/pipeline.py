"""RAG 问答: 检索 -> 拼 Prompt -> LLM 生成 (同步与流式两种链路)。

工厂场景的关键设计:
- 强制引用来源 ([序号]), 答案必须可溯源;
- 知识库为空或检索不到时明确告知, 而不是让模型自由发挥;
- 支持携带最近对话历史, 便于追问 (如「那 P2233 呢」)。
"""
from __future__ import annotations

from typing import Generator, List, Optional, Tuple

from app.config import cfg
from app.llm.client import get_llm
from app.llm.prompts import RAG_SYSTEM, clean_history
from app.rag.embedder import get_embedder
from app.rag.ingest import get_store

_EMPTY_HINT = "知识库为空。请先调用 POST /api/kb/ingest 导入文档 (默认读取 data/knowledge)。"


def _retrieve(question: str, top_k: Optional[int] = None) -> Tuple[Optional[str], List[dict]]:
    """检索, 返回 (context, sources); 知识库为空时 context 为 None。"""
    store = get_store()
    if len(store) == 0:
        return None, []
    hits: List[dict] = store.search(
        get_embedder().embed_one(question), int(top_k or cfg("rag.top_k", 5))
    )
    context = "\n\n".join(
        f"[{i + 1}] 来源: {h['source']}\n{h['text']}" for i, h in enumerate(hits)
    )
    sources = [
        {
            "idx": i + 1,
            "source": h["source"],
            "score": round(h["score"], 4),
            "excerpt": h["text"][:120],
        }
        for i, h in enumerate(hits)
    ]
    return context, sources


def _build_messages(question: str, history, context: str) -> List[dict]:
    messages = [{"role": "system", "content": RAG_SYSTEM.format(context=context)}]
    messages.extend(clean_history(history))
    messages.append({"role": "user", "content": question})
    return messages


def ask(question: str, history=None, top_k: Optional[int] = None) -> dict:
    context, sources = _retrieve(question, top_k)
    if context is None:
        return {"answer": _EMPTY_HINT, "sources": []}
    answer = get_llm().chat(_build_messages(question, history, context))
    return {"answer": answer, "sources": sources}


def ask_stream(question: str, history=None, top_k: Optional[int] = None) -> Generator[dict, None, None]:
    """流式问答: 依次产出 {"type":"delta","text":...} 与 {"type":"done","sources":[...]}。"""
    context, sources = _retrieve(question, top_k)
    if context is None:
        yield {"type": "delta", "text": _EMPTY_HINT}
        yield {"type": "done", "sources": []}
        return
    for chunk in get_llm().chat_stream(_build_messages(question, history, context)):
        yield {"type": "delta", "text": chunk}
    yield {"type": "done", "sources": sources}
