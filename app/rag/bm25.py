"""BM25 检索 (纯 Python) —— 与向量检索做 RRF 混合。

中文 tokenization: 字符级 + 中文二元组 + ASCII 词元, 不依赖分词器 (内网可用)。
复杂度 O(词数 x 文档数), 试点量级 (<=10 万片段) 可接受; 大规模时换 Elasticsearch。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import List, Tuple

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> List[str]:
    tokens = _TOKEN_RE.findall((text or "").lower())
    hans = [t for t in tokens if "\u4e00" <= t <= "\u9fff"]
    return tokens + [f"{a}{b}" for a, b in zip(hans, hans[1:])]


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tfs: List[Counter] = []
        self.dls: List[int] = []
        self.df: dict = {}
        self.avgdl = 1.0

    def build(self, docs: List[str]) -> None:
        self.tfs, self.dls, self.df = [], [], {}
        for d in docs:
            tf = Counter(tokenize(d))
            self.tfs.append(tf)
            self.dls.append(sum(tf.values()))
            for term in tf:
                self.df[term] = self.df.get(term, 0) + 1
        self.avgdl = (sum(self.dls) / len(self.dls)) if self.dls else 1.0

    def __len__(self) -> int:
        return len(self.tfs)

    def search(self, query: str, k: int = 5) -> List[Tuple[int, float]]:
        """返回 [(文档下标, bm25分), ...] 按分降序。"""
        if not self.tfs:
            return []
        n = len(self.tfs)
        scores = [0.0] * n
        for term in set(tokenize(query)):
            df = self.df.get(term)
            if not df:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for i, tf in enumerate(self.tfs):
                f = tf.get(term, 0)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.dls[i] / self.avgdl)
                scores[i] += idf * f * (self.k1 + 1) / denom
        ranked = sorted(((i, s) for i, s in enumerate(scores) if s > 0), key=lambda x: -x[1])
        return ranked[:k]
