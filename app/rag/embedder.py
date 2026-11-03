"""Embedding 客户端。

provider=openai : 调用 OpenAI 兼容 /embeddings 接口 (vLLM --task embed、TEI、
                  Ollama 均可)。生产建议 BGE-M3 或 Qwen3-Embedding, 本地部署。
provider=mock   : 确定性字符 n-gram 向量 (dim=256), 无推理环境时演示流程用,
                  检索质量有限, 接入真实 embedding 后自动提升。
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import List

import httpx

from app.config import cfg

_DIM = 256


class MockEmbedder:
    name = "mock-ngram-256"

    @staticmethod
    def _feats(text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]", text.lower())
        feats = list(tokens)
        hans = [t for t in tokens if "\u4e00" <= t <= "\u9fff"]
        feats += [f"{a}{b}" for a, b in zip(hans, hans[1:])]  # 中文二元组
        return feats

    def embed(self, texts: List[str]) -> List[List[float]]:
        out = []
        for text in texts:
            vec = [0.0] * _DIM
            for feat in self._feats(text):
                idx = int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16) % _DIM
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


class OpenAICompatEmbedder:
    def __init__(self, base_url: str, model: str, api_key: str = "EMPTY", timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def embed(self, texts: List[str]) -> List[List[float]]:
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": texts},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


def get_embedder():
    provider = cfg("rag.embedding.provider", "mock")
    if provider == "openai":
        return OpenAICompatEmbedder(
            base_url=cfg("rag.embedding.base_url", "http://127.0.0.1:8001/v1"),
            model=cfg("rag.embedding.model", "bge-m3"),
            api_key=cfg("rag.embedding.api_key", "EMPTY"),
        )
    return MockEmbedder()
