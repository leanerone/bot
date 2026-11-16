"""RAG 问答: 混合检索 (向量+BM25, RRF 融合) -> Prompt -> LLM 生成 (同步/流式)。

工厂场景的关键设计:
- 强制引用来源 ([序号]), 答案必须可溯源;
- 知识库为空或检索不到时明确告知, 而不是让模型自由发挥;
- 混合检索: 向量负责语义, BM25 负责机台号/告警码等精确关键词;
- 支持携带最近对话历史, 便于追问 (如「那 P2233 呢」)。
"""
from __future__ import annotations

import threading
from typing import Generator, List, Optional, Tuple

from app.config import cfg
from app.bots.registry import persona_system_prompt
from app.guard.prompt_guard import wrap_context
from app.llm.client import get_llm
from app.llm.prompts import RAG_SYSTEM, compress_history
from app.rag.bm25 import BM25Index
from app.rag.embedder import get_embedder
from app.rag.ingest import get_store

_EMPTY_HINT = "知识库为空。请先调用 POST /api/kb/ingest 导入文档 (默认读取 data/knowledge)。"

_bm25: Optional[BM25Index] = None
_bm25_len = -1
_bm25_lock = threading.Lock()

_RRF_K = 60


def _bm25_index() -> BM25Index:
    """BM25 索引随向量库规模自动重建 (增量导入后 len 变化触发)。

    双检锁: 并发请求同时发现 len 变化时只重建一次, 避免全量重复劳动。"""
    global _bm25, _bm25_len
    store = get_store()
    if _bm25 is None or _bm25_len != len(store):
        with _bm25_lock:
            if _bm25 is None or _bm25_len != len(store):
                index = BM25Index()
                index.build([m["text"] for m in store.metas])
                _bm25 = index
                _bm25_len = len(store)
    return _bm25


def _doc_key(meta: dict) -> str:
    return f"{meta.get('source', '')}|{meta.get('text', '')[:64]}"


def _retrieve(question: str, top_k: Optional[int] = None) -> Tuple[Optional[str], List[dict]]:
    """混合检索, 返回 (context, sources); 知识库为空时 context 为 None。

    向量负责语义相似, BM25 负责机台号/告警码/产品号等精确关键词,
    两路结果用 RRF (1/(60+rank)) 融合。
    """
    store = get_store()
    if len(store) == 0:
        return None, []
    k = int(top_k or cfg("rag.top_k", 6))

    vec_hits = store.search(get_embedder().embed_one(question), k * 2)
    merged: dict = {}
    for rank, h in enumerate(vec_hits):
        key = _doc_key(h)
        entry = merged.setdefault(key, {"meta": h, "rrf": 0.0, "vec": None})
        entry["rrf"] += 1.0 / (_RRF_K + rank + 1)
        entry["vec"] = h["score"]

    if cfg("rag.hybrid", True) and len(store) >= 3:
        for rank, (idx, _bm_score) in enumerate(_bm25_index().search(question, k * 2)):
            meta = store.metas[idx]
            key = _doc_key(meta)
            entry = merged.setdefault(key, {"meta": {**meta, "score": 0.0}, "rrf": 0.0, "vec": None})
            entry["rrf"] += 1.0 / (_RRF_K + rank + 1)

    top = sorted(merged.values(), key=lambda e: -e["rrf"])[:k]
    # E1: RRF 粗排后 rerank 精排 (provider=off 时规则降级, 不阻塞)
    from app.rag.rerank import rerank_hits

    top = rerank_hits(question, [
        {"source": e["meta"]["source"], "text": e["meta"]["text"],
         "score": round(e["rrf"], 4), "meta": e["meta"]} for e in top
    ], top_n=k)
    hits = [
        {
            "source": h["source"],
            "text": h["text"],
            "score": h["score"],
            "link": h["meta"].get("link", ""),   # B5: Notes doclink 回链
        }
        for h in top
    ]
    context = "\n\n".join(f"[{i + 1}] 来源: {h['source']}\n{h['text']}" for i, h in enumerate(hits))
    sources = [
        {"idx": i + 1, "source": h["source"], "score": h["score"],
         "excerpt": h["text"][:120], "text": h["text"],
         **({"link": h["link"]} if h["link"] else {})}
        for i, h in enumerate(hits)
    ]
    return context, sources


def _build_messages(question: str, history, context: str, bot_id: Optional[str] = None) -> List[dict]:
    # C1 间接注入防护: 检索资料包进"资料非指令"信任边界 (OWASP LLM01 纵深第 2 层)
    base = RAG_SYSTEM.format(context=wrap_context(context))
    system = persona_system_prompt(bot_id, base) if bot_id else base
    messages = [{"role": "system", "content": system}]
    messages.extend(compress_history(history))  # E3: 长会话自动压缩
    messages.append({"role": "user", "content": question})
    return messages


def ask(question: str, history=None, top_k: Optional[int] = None, bot_id: Optional[str] = None) -> dict:
    context, sources = _retrieve(question, top_k)
    if context is None:
        return {"answer": _EMPTY_HINT, "sources": []}
    answer = get_llm().chat(_build_messages(question, history, context, bot_id))
    return {"answer": answer, "sources": sources}


def ask_stream(question: str, history=None, top_k: Optional[int] = None,
               bot_id: Optional[str] = None) -> Generator[dict, None, None]:
    """流式问答: 依次产出 {"type":"delta","text":...} 与 {"type":"done","sources":[...]}。"""
    context, sources = _retrieve(question, top_k)
    if context is None:
        yield {"type": "delta", "text": _EMPTY_HINT}
        yield {"type": "done", "sources": []}
        return
    for chunk in get_llm().chat_stream(_build_messages(question, history, context, bot_id)):
        yield {"type": "delta", "text": chunk}
    yield {"type": "done", "sources": sources}
