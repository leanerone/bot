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


def reset_store() -> None:
    """丢弃内存单例 (重建知识库前调用, 目录由调用方清理)。"""
    global _store
    _store = None


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


def chunk_markdown(text: str, size: int = 500, overlap: int = 80) -> List[str]:
    """Markdown 感知分块: 以 #/## 标题为硬边界; 每块携带 H1/H2 面包屑前缀。

    动机: SOP 文档的"标题 -> 处置步骤"常被普通分块切开, 导致标题词
    (如"研磨速率漂移")与正文词 (如"研磨垫/Slurry")落在不同块, 检索互相稀释。
    面包屑让每块都携带标题词, 混合检索的向量路与 BM25 路同时受益。
    """
    h1 = ""
    cur_bc = ""
    cur_paras: List[str] = []
    out_paras: List[tuple] = []  # (breadcrumb, 段落文本)

    def flush_section() -> None:
        nonlocal cur_paras
        body = "\n".join(cur_paras).strip()
        if body:
            out_paras.append((cur_bc, body))
        cur_paras = []

    for ln in text.split("\n"):
        if ln.startswith("## "):
            flush_section()
            cur_bc = (h1 + " / " if h1 else "") + ln.lstrip("# ").strip()
            cur_paras = [ln]
        elif ln.startswith("# "):
            flush_section()
            h1 = ln.lstrip("# ").strip()
            cur_bc = h1
            cur_paras = [ln]
        else:
            cur_paras.append(ln)
    flush_section()

    chunks: List[str] = []
    buf = ""
    for bc, body in out_paras:
        piece = (bc + "\n" + body) if bc else body
        if buf and len(buf) + len(piece) + 1 <= size:
            buf = f"{buf}\n{piece}"
        else:
            if buf:
                chunks.append(buf)
            if len(piece) <= size:
                buf = piece
            else:
                step = max(1, size - overlap)
                chunks.extend(piece[i : i + size] for i in range(0, len(piece), step))
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


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
    added = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = read_document(path)
        except Exception as exc:  # 单个文件失败不阻塞整批
            errors.append(f"{path.name}: {exc}")
            continue
        chunks = (chunk_markdown(text, size=size, overlap=overlap)
                  if path.suffix.lower() == ".md"
                  else chunk_text(text, size=size, overlap=overlap))
        if not chunks:
            continue
        rel = str(path.relative_to(root))
        added += store.add(embedder.embed(chunks), [{"source": rel, "text": c} for c in chunks])
        total += len(chunks)
        used.append(rel)
    return {"files": used, "chunks": total, "added": added, "errors": errors}
