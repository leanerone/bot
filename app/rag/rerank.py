"""E1: Rerank 精排 —— RRF 融合后对候选做交叉编码重排 (Top-5 召回业界实测 +20%)。

三级 provider (按环境可用性选择, 默认 off 规则降级零回归):
- off    : 规则降级 —— 机台号/告警码/产品号精确命中加权 (mock 与无模型环境的兜底)
- vllm   : OpenAI 兼容 /v1/rerank 端点 (vLLM rerank / TEI / SiliconFlow 等)
- local  : sentence-transformers CrossEncoder, CPU 可跑 (bge-reranker-v2-m3)
"""
from __future__ import annotations

import re
from typing import List, Optional

from app.config import cfg

# 精确业务标识: 工厂问题常带机台号/告警码/产品号, 精确命中应排前
_CODE_RE = re.compile(r"\b([A-Z]{2,6}-?\d{2,4}|E\d{4}|V\d{4})\b", re.I)


def _exact_boost(query: str, text: str) -> float:
    q_codes = set(_CODE_RE.findall(query or ""))
    if not q_codes:
        return 0.0
    t = (text or "").upper()
    return sum(1.0 for c in q_codes if c.upper() in t)


class _OffReranker:
    name = "off"

    def rerank(self, query: str, hits: List[dict], top_n: int) -> List[dict]:
        if not hits:
            return hits
        scored = []
        for i, h in enumerate(hits):
            boost = _exact_boost(query, f"{h.get('source', '')} {h.get('text', '')}")
            base = h.get("score", 0.0)
            scored.append((base + boost, -i, h))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [h for _, _, h in scored[:top_n]]


class _VllmReranker:
    """OpenAI 兼容 /rerank (Jina/Cohere 风格): {model, query, documents} → results[{index, score}]。"""

    name = "vllm"

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 20.0):
        import httpx

        self._client = httpx.Client(base_url=base_url.rstrip("/"),
                                    headers={"Authorization": f"Bearer {api_key or 'EMPTY'}"},
                                    timeout=timeout)
        self.model = model

    def rerank(self, query: str, hits: List[dict], top_n: int) -> List[dict]:

        docs = [f"{h.get('source', '')}\n{h.get('text', '')}" for h in hits]
        resp = self._client.post("/rerank", json={
            "model": self.model, "query": query, "documents": docs, "top_n": len(docs)})
        resp.raise_for_status()
        results = resp.json().get("results", [])
        out = []
        for r in results:
            h = dict(hits[r["index"]])
            h["score"] = round(float(r.get("relevance_score", 0.0)), 6)
            out.append(h)
        return out[:top_n]


class _LocalReranker:
    name = "local"

    def __init__(self, model: str):
        try:
            from sentence_transformers import CrossEncoder

            self._ce = CrossEncoder(model, max_length=512)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"local rerank 不可用 (需要 sentence-transformers): {exc}") from exc

    def rerank(self, query: str, hits: List[dict], top_n: int) -> List[dict]:
        pairs = [(query, f"{h.get('source', '')}\n{h.get('text', '')}") for h in hits]
        scores = self._ce.predict(pairs)
        ranked = sorted(zip(hits, scores), key=lambda t: -float(t[1]))
        out = []
        for h, s in ranked[:top_n]:
            h = dict(h)
            h["score"] = round(float(s), 6)
            out.append(h)
        return out


_reranker = None
_reranker_key: tuple = ()
_failed_keys: set = set()


def get_reranker():
    """按 (provider, model, base_url) 指纹缓存实例 —— local 模型加载与 vllm
    连接都是秒级开销, 每次检索重建会拖垮问答延迟。构建失败 (如 local 模型
    缺失) 的配置键记录后直接降级 off, 避免每个请求重复付出加载代价;
    远端调用失败不在缓存层处理 (由 rerank_hits 逐次降级, 服务恢复即自动回归)。"""
    global _reranker, _reranker_key
    provider = cfg("rag.rerank.provider", "off")
    model = cfg("rag.rerank.model", "BAAI/bge-reranker-v2-m3")
    base_url = cfg("rag.rerank.base_url", cfg("llm.base_url", "http://127.0.0.1:8000/v1"))
    key = (provider, model, base_url)
    if key in _failed_keys:
        return _OffReranker()
    if _reranker is not None and _reranker_key == key:
        return _reranker
    try:
        if provider == "vllm":
            instance = _VllmReranker(base_url, cfg("llm.api_key", "EMPTY"), model)
        elif provider == "local":
            instance = _LocalReranker(model)
        else:
            instance = _OffReranker()
    except Exception:
        _failed_keys.add(key)
        return _OffReranker()
    try:  # 换配置时释放旧 vllm 连接池
        old = _reranker
        if old is not None and getattr(old, "name", "") == "vllm":
            old._client.close()
    except Exception:
        pass
    _reranker, _reranker_key = instance, key
    return instance


def rerank_hits(query: str, hits: List[dict], top_n: Optional[int] = None) -> List[dict]:
    """管线入口: 异常时静默降级回原序 (rerank 永不阻塞主流程)。"""
    if not hits:
        return hits
    n = int(top_n or cfg("rag.rerank.top_n", cfg("rag.top_k", 6)))
    try:
        return get_reranker().rerank(query, hits, n)
    except Exception:
        return hits[:n]
