"""轻量本地向量库: JSON(元数据) + npy(矩阵)。

单进程、十万级片段以内够用的试点实现; 接口只有 add/search 两个方法,
生产替换为 Milvus / pgvector 时上层代码不动。
"""
from __future__ import annotations

import json
import os
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
            # 崩溃残留自洽: 两文件条数取交集, 避免 metas 与 vectors 错位导致越界
            n = min(len(self.metas), int(self.vectors.shape[0]))
            if n != len(self.metas) or n != self.vectors.shape[0]:
                self.metas = self.metas[:n]
                self.vectors = self.vectors[:n]
        self._keys = {self._key(m) for m in self.metas}

    @staticmethod
    def _key(meta: Dict[str, Any]) -> str:
        """片段唯一键: 来源 + 正文 (重复导入去重用)。"""
        return f"{meta.get('source', '')}|{meta.get('text', '')}"

    def filter_new(self, metas: List[Dict[str, Any]]) -> List[int]:
        """返回未入库片段的下标 (先过滤再嵌入, 省去对已有片段重复调 embedding)。"""
        with self._lock:
            return [i for i, m in enumerate(metas) if self._key(m) not in self._keys]

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
        """原子写: 先落 .tmp 再 os.replace, 避免进程崩溃把向量库写坏一半。"""
        tmp_vec = self.dir / "vectors.npy.tmp"
        tmp_meta = self.dir / "meta.json.tmp"
        with open(tmp_vec, "wb") as f:  # np.save 对文件对象不追加扩展名
            np.save(f, self.vectors)
        tmp_meta.write_text(json.dumps(self.metas, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_vec, self.vec_file)  # 崩溃窗口: vectors 新 / metas 旧 -> 加载端钳制自洽
        os.replace(tmp_meta, self.meta_file)

    def _normalized(self) -> np.ndarray:
        if self._matrix is None:
            norm = np.linalg.norm(self.vectors, axis=1, keepdims=True)
            norm[norm == 0] = 1.0
            self._matrix = self.vectors / norm
        return self._matrix

    def list_sources(self) -> List[Dict[str, Any]]:
        """知识库来源清单 (来源名 -> 片段数), 管理运维用。"""
        counter: Dict[str, int] = {}
        for m in self.metas:
            counter[m["source"]] = counter.get(m["source"], 0) + 1
        return [{"source": s, "chunks": c} for s, c in sorted(counter.items())]

    def chunks_by_source(self, source: str) -> List[Dict[str, Any]]:
        """某来源的全部片段 (管理端预览)。"""
        return [{"text": m["text"]} for m in self.metas if m["source"] == source]

    def delete_by_source(self, source: str) -> int:
        """按来源删除全部片段 (文档下线/换版时用), 返回删除条数。"""
        with self._lock:
            keep_idx = [i for i, m in enumerate(self.metas) if m["source"] != source]
            removed = len(self.metas) - len(keep_idx)
            if removed == 0:
                return 0
            if self.vectors.shape[0] > 0:
                self.vectors = self.vectors[np.array(keep_idx, dtype=int)]
            self.metas = [self.metas[i] for i in keep_idx]
            self._keys = {self._key(m) for m in self.metas}
            self._matrix = None
            self.save()
            return removed

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
