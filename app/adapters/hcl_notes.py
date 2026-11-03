"""HCL Notes (Lotus Notes) 内容接入适配器。

Notes 内容存在 Domino 服务器的 .nsf 库中 (富文本为 Notes 私有格式), 无法像普通
文件一样直接读取, 必须经接口抽取后再进知识库。本模块支持两种抽取方式:

- mode=export : 读取导出产出的 JSON 目录 (契约见下), 由 Domino 导出代理或
                tools/export_notes_com.py (Notes 客户端 COM) 生成 —— 推荐,
                与「中间库只读副本」安全原则一致, Bot 不直连 Domino
- mode=domino : 经 Domino HTTP 只读拉取 (经典 URL 命令 ReadViewEntries /
                ?OpenDocument, 各版本 Domino 均支持), 需管理员开通只读账号

导出 JSON 契约 (单个文件可含多库多文档, 支持 sharding):
{
  "db_title": "工艺经验库", "db_path": "KB/process.nsf",
  "docs": [{
    "unid": "C1257A1B...",            // 文档唯一 ID
    "subject": "...", "author": "...", "modified": "...",
    "body_text": "...",               // 与 body_html 至少给一个
    "body_html": "<p>...</p>",
    "attachments": [{"name": "附件名", "file": "attachments/xx.docx"}],  // 相对导出目录
    "links": []                       // 可不填, 会从正文自动提取 notes:// 链接
  }]
}

说明:
- notes:// 文档链接是 Notes 私有协议, Bot 无法直接打开; 本模块解析出链接中的
  UNID 用于关联标注, 目标文档需要纳入导出/拉取范围才能进入知识库
- 重复导入会重复入库; 更新知识库时可删除 data/vector_store 后全量重建
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import quote

import httpx

from app.config import cfg
from app.rag.ingest import chunk_text, get_store, read_document
from app.rag.embedder import get_embedder
from app.rag.store import LocalVectorStore

# ── notes:// 文档链接解析 ──

_DOC_LINK_RE = re.compile(
    r"notes://[A-Za-z0-9._\-]+(?:/[^\s\"'<>（）()，,;；]+)*", re.I
)


def extract_doclinks(text: str) -> List[str]:
    """提取正文中的 notes:// 文档链接。"""
    return _DOC_LINK_RE.findall(text or "")


def parse_doclink(url: str) -> Dict[str, str]:
    """notes://Host/Db[/View]/Unid -> {host, db, view, unid} (尽力解析)。"""
    parts = [p for p in url[len("notes://"):].split("/") if p]
    return {
        "host": parts[0] if parts else "",
        "db": parts[1] if len(parts) > 1 else "",
        "view": parts[2] if len(parts) > 2 else "",
        "unid": parts[-1] if parts else "",
    }


# ── 富文本 HTML -> 纯文本 ──

_BLOCK_TAGS = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "table", "ul", "ol", "br"}
_VOID_TAGS = {"br", "img", "hr"}


class _HTML2Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self.parts.append("\n" if tag != "li" else "\n- ")

    def handle_endtag(self, tag):
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """Domino 渲染的文档 HTML -> 纯文本 (保留基本换行与列表符号)。"""
    parser = _HTML2Text()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", "", html or "")
    lines = [ln.strip() for ln in "".join(parser.parts).split("\n")]
    return "\n".join(ln for ln in lines if ln)


# ── 文档模型 ──

@dataclass
class NoteDoc:
    unid: str
    subject: str = ""
    db_path: str = ""
    db_title: str = ""
    author: str = ""
    modified: str = ""
    body_text: str = ""
    body_html: str = ""
    attachments: List[Dict[str, str]] = field(default_factory=list)

    def plain_text(self) -> str:
        return self.body_text or html_to_text(self.body_html)

    def source_label(self) -> str:
        db = self.db_path or self.db_title or "notesdb"
        return f"notes://{db}/{self.unid[:8]} · {self.subject[:40]}"


# ── mode=export: 读取导出目录 ──

def load_export_dir(export_dir: str | Path) -> Dict[str, Any]:
    """读取导出目录下所有 *.json, 返回 {docs, dbs, errors}。"""
    root = Path(export_dir)
    docs: List[NoteDoc] = []
    errors: List[str] = []
    dbs: set = set()
    if not root.exists():
        return {"docs": docs, "dbs": dbs, "errors": [f"导出目录不存在: {root}"]}
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        db_path = payload.get("db_path", "")
        db_title = payload.get("db_title", "")
        dbs.add(db_path or db_title or path.stem)
        for raw in payload.get("docs", []):
            docs.append(NoteDoc(
                unid=str(raw.get("unid", "")),
                subject=str(raw.get("subject", "") or "无标题"),
                db_path=db_path, db_title=db_title,
                author=str(raw.get("author", "")),
                modified=str(raw.get("modified", "")),
                body_text=str(raw.get("body_text", "")),
                body_html=str(raw.get("body_html", "")),
                attachments=list(raw.get("attachments", [])),
            ))
    return {"docs": docs, "dbs": dbs, "errors": errors}


# ── 入库: 导出目录 -> 向量库 ──

def ingest_notes_export(export_dir: str, store: Optional[LocalVectorStore] = None,
                        embedder=None, include_attachments: bool = True) -> Dict[str, Any]:
    loaded = load_export_dir(export_dir)
    docs: List[NoteDoc] = loaded["docs"]
    errors: List[str] = list(loaded["errors"])
    if store is None:  # 注意不能用 `store or ...`: 空库 __len__==0 会被判假
        store = get_store()
    embedder = embedder or get_embedder()
    root = Path(export_dir)

    items: List[tuple] = []  # (source_label, text)
    link_count = 0
    att_count = 0
    for doc in docs:
        text = doc.plain_text().strip()
        if not text and not doc.attachments:
            continue
        label = doc.source_label()
        links = extract_doclinks(doc.body_text + " " + doc.body_html)
        link_count += len(links)
        if links:
            text = f"{text}\n\n[文档链接] " + " ; ".join(links[:10])
        if text:
            items.append((label, f"{doc.subject}\n\n{text}"))
        # 附件: 复用既有文档解析 (docx/pdf/md/txt)
        if include_attachments:
            for att in doc.attachments:
                att_file = root / str(att.get("file", ""))
                if not att_file.exists():
                    errors.append(f"附件缺失: {doc.unid[:8]} {att.get('name')}")
                    continue
                try:
                    att_text = read_document(att_file)
                except Exception as exc:
                    errors.append(f"附件解析失败 {att.get('name')}: {exc}")
                    continue
                att_count += 1
                items.append((f"{label}/附件/{att.get('name', att_file.name)}",
                              f"{doc.subject} - 附件 {att.get('name')}\n\n{att_text}"))

    chunks_total = 0
    size = int(cfg("rag.chunk_size", 500))
    overlap = int(cfg("rag.chunk_overlap", 80))
    if items:
        vectors, metas = [], []
        for label, text in items:
            for chunk in chunk_text(text, size=size, overlap=overlap):
                vectors.extend(embedder.embed([chunk]))
                metas.append({"source": label, "text": chunk})
                chunks_total += 1
        store.add(vectors, metas)
    return {"docs": len(docs), "chunks": chunks_total,
            "attachments": att_count, "links": link_count, "errors": errors}


# ── mode=domino: 经 Domino HTTP 只读拉取 ──

class DominoNotesClient:
    """经 Domino HTTP 的只读拉取 (经典 URL 命令, 各版本 Domino 均支持)。

    前提 (需 Domino 管理员配合):
    1. Domino HTTP 任务已开启, bot 所在办公网段允许访问;
    2. 提供只读服务账号, 目标库 ACL 只读;
    3. 访问行为纳入 Domino 侧审计。
    拉取到的是 Domino 渲染的 HTML (富文本已转为 HTML), 附件与深度关联文档
    建议走导出模式覆盖。
    """

    def __init__(self, base_url: str, db_path: str, username: str = "",
                 password: str = "", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.db_path = db_path.strip("/")
        auth = (username, password) if username else None
        self.client = httpx.Client(base_url=self.base_url, auth=auth, timeout=timeout)

    def list_unids(self, view: str = "($All)", count: int = 500) -> List[str]:
        url = f"/{self.db_path}/{quote(view)}?ReadViewEntries&Count={count}&outputformat=JSON"
        resp = self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("viewentry") or []
        if isinstance(entries, dict):
            entries = [entries]
        return [e["@unid"] for e in entries if e.get("@unid")]

    @staticmethod
    def _extract_title(html: str) -> str:
        m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        return html_to_text(m.group(1))[:60] if m else "无标题"

    def fetch_doc_html(self, unid: str) -> str:
        resp = self.client.get(f"/{self.db_path}/{unid}?OpenDocument")
        resp.raise_for_status()
        return resp.text

    def iter_docs(self, view: str = "($All)") -> Iterator[NoteDoc]:
        for unid in self.list_unids(view):
            html = self.fetch_doc_html(unid)
            yield NoteDoc(unid=unid, subject=self._extract_title(html),
                          db_path=self.db_path, body_html=html)


def ingest_notes_domino(client: DominoNotesClient, store: Optional[LocalVectorStore] = None,
                        embedder=None, view: str = "($All)") -> Dict[str, Any]:
    if store is None:
        store = get_store()
    embedder = embedder or get_embedder()
    vectors, metas = [], []
    chunks_total = 0
    errors: List[str] = []
    size = int(cfg("rag.chunk_size", 500))
    overlap = int(cfg("rag.chunk_overlap", 80))
    doc_count = 0
    for doc in client.iter_docs(view=view):
        text = doc.plain_text().strip()
        if not text:
            continue
        doc_count += 1
        label = doc.source_label()
        for chunk in chunk_text(f"{doc.subject}\n\n{text}", size=size, overlap=overlap):
            vectors.extend(embedder.embed([chunk]))
            metas.append({"source": label, "text": chunk})
            chunks_total += 1
    if vectors:
        store.add(vectors, metas)
    return {"docs": doc_count, "chunks": chunks_total,
            "attachments": 0, "links": 0, "errors": errors}
