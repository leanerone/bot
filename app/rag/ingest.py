"""知识库文档导入: 解析 -> 分块 -> 向量化 -> 入库。

SOP/手册的清洗质量决定 RAG 上限 —— 老旧扫描件建议先用 OCR 工具
(如 MinerU) 转成文本再导入。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from app.config import abs_path, cfg
from app.rag.embedder import get_embedder
from app.rag.store import LocalVectorStore

_store: Optional[LocalVectorStore] = None


def get_store() -> LocalVectorStore:
    global _store
    if _store is None:
        _store = LocalVectorStore(abs_path(cfg("rag.store_path", "data/vector_store")))
    return _store


def read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".md", ".txt"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        try:
            from docx import Document  # python-docx
        except ImportError as exc:
            raise RuntimeError("解析 .docx 需要: pip install python-docx") from exc
        return "\n".join(p.text for p in Document(str(path)).paragraphs if p.text.strip())
    if suffix == ".pdf":
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError("解析 .pdf 需要: pip install pdfplumber") from exc
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    raise ValueError(f"暂不支持的文件类型: {suffix}")


def chunk_text(text: str, size: int = 500, overlap: int = 80) -> List[str]:
    """按空行分段后贪心组块; 超长段落硬切并保留 overlap 重叠 (中文按字符数)。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    buf = ""
    for para in paras:
        if len(para) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            step = max(1, size - overlap)
            chunks.extend(para[i : i + size] for i in range(0, len(para), step))
            continue
        if buf and len(buf) + len(para) + 1 > size:
            chunks.append(buf)
            buf = para
        else:
            buf = f"{buf}\n{para}" if buf else para
    if buf:
        chunks.append(buf)
    return chunks


def ingest_dir(kb_dir: str, store: Optional[LocalVectorStore] = None) -> Dict:
    """导入目录下所有可解析文档, 返回 {files, chunks, errors}。"""
    root = abs_path(kb_dir)
    if store is None:  # 不能用 `store or ...`: 空库 __len__==0 会被判假
        store = get_store()
    embedder = get_embedder()
    size = int(cfg("rag.chunk_size", 500))
    overlap = int(cfg("rag.chunk_overlap", 80))

    used: List[str] = []
    errors: List[str] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = read_document(path)
        except Exception as exc:  # 单个文件失败不阻塞整批
            errors.append(f"{path.name}: {exc}")
            continue
        chunks = chunk_text(text, size=size, overlap=overlap)
        if not chunks:
            continue
        rel = str(path.relative_to(root))
        store.add(embedder.embed(chunks), [{"source": rel, "text": c} for c in chunks])
        total += len(chunks)
        used.append(rel)
    return {"files": used, "chunks": total, "errors": errors}
