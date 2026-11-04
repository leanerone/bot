"""轻量本地向量库: JSON(元数据) + npy(矩阵)。

单进程、十万级片段以内够用的试点实现; 接口只有 add/search 两个方法,
生产替换为 Milvus / pgvector 时上层代码不动。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


class LocalVectorStore:
    def __init__(self, dir_path) -> None:
        self.dir = Path(dir_path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.dir / "meta.json"
        self.vec_file = self.dir / "vectors.npy"
        self._lock = threading.Lock()
        self._matrix = None  # 归一化缓存
        self.metas: List[Dict[str, Any]] = []
        self.vectors = np.zeros((0, 0), dtype=np.float32)
        if self.meta_file.exists() and self.vec_file.exists():
            self.metas = json.loads(self.meta_file.read_text(encoding="utf-8"))
            self.vectors = np.load(self.vec_file)
        self._keys = {self._key(m) for m in self.metas}

    @staticmethod
    def _key(meta: Dict[str, Any]) -> str:
        """片段唯一键: 来源 + 正文 (重复导入去重用)。"""
        return f"{meta.get('source', '')}|{meta.get('text', '')}"

    def __len__(self) -> int:
        return len(self.metas)

    def add(self, vectors: List[List[float]], metas: List[Dict[str, Any]]) -> int:
        """批量入库; 重复片段 (来源+正文相同) 自动跳过, 返回实际新增条数。"""
        if len(vectors) != len(metas):
            raise ValueError("vectors 与 metas 数量不一致")
        with self._lock:
            new_vecs, new_metas = [], []
            for vec, meta in zip(vectors, metas):
                key = self._key(meta)
                if key in self._keys:
                    continue
                self._keys.add(key)
                new_vecs.append(vec)
                new_metas.append(meta)
            if not new_vecs:
                return 0
            new = np.asarray(new_vecs, dtype=np.float32)
            self.vectors = new if self.vectors.shape[0] == 0 else np.vstack([self.vectors, new])
            self.metas.extend(new_metas)
            self._matrix = None
            self.save()
            return len(new_vecs)

    def save(self) -> None:
        np.save(self.vec_file, self.vectors)
        self.meta_file.write_text(json.dumps(self.metas, ensure_ascii=False), encoding="utf-8")

    def _normalized(self) -> np.ndarray:
        if self._matrix is None:
            norm = np.linalg.norm(self.vectors, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            self._matrix = self.vectors / norm
        return self._matrix

    def search(self, query_vec: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """余弦相似度 Top-K, 返回 [{score, source, text}, ...]"""
        if len(self.metas) == 0:
            return []
        with self._lock:
            q = np.asarray(query_vec, dtype=np.float32)
            qn = np.linalg.norm(q) or 1.0
            scores = self._normalized() @ (q / qn)
            k = min(k, len(self.metas))
            idx = np.argsort(-scores)[:k]
            return [{"score": float(scores[i]), **self.metas[int(i)]} for i in idx]
