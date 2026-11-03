"""RAG 问答: 检索 -> 拼 Prompt -> LLM 生成。

工厂场景的关键设计:
- 强制引用来源 ([序号]), 答案必须可溯源;
- 知识库为空或检索不到时明确告知, 而不是让模型自由发挥。
"""
from __future__ import annotations

from typing import List, Optional

from app.config import cfg
from app.llm.client import get_llm
from app.llm.prompts import RAG_SYSTEM
from app.rag.embedder import get_embedder
from app.rag.ingest import get_store


def ask(question: str, top_k: Optional[int] = None) -> dict:
    store = get_store()
    if len(store) == 0:
        return {
            "answer": "知识库为空。请先调用 POST /api/kb/ingest 导入文档 (默认读取 data/knowledge)。",
            "sources": [],
        }
    hits: List[dict] = store.search(
        get_embedder().embed_one(question), int(top_k or cfg("rag.top_k", 5))
    )
    context = "\n\n".join(
        f"[{i + 1}] 来源: {h['source']}\n{h['text']}" for i, h in enumerate(hits)
    )
    messages = [
        {"role": "system", "content": RAG_SYSTEM.format(context=context)},
        {"role": "user", "content": question},
    ]
    answer = get_llm().chat(messages)
    sources = [
        {
            "idx": i + 1,
            "source": h["source"],
            "score": round(h["score"], 4),
            "excerpt": h["text"][:120],
        }
        for i, h in enumerate(hits)
    ]
    return {"answer": answer, "sources": sources}
