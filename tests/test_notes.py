"""HCL Notes 适配器测试 (html 转换 / doclink 解析 / 导出目录入库)。"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.hcl_notes import (
    extract_doclinks,
    html_to_text,
    ingest_notes_export,
    load_export_dir,
    parse_doclink,
)
from app.rag.store import LocalVectorStore

_SAMPLE = Path(__file__).resolve().parents[1] / "data" / "demo" / "notes_export_sample"


def test_html_to_text():
    text = html_to_text("<p>第一步检查阀门</p><div>泄压<br>再抽真空</div><ul><li>记录</li></ul>")
    assert "第一步检查阀门" in text
    assert "泄压\n再抽真空" in text
    assert "- 记录" in text


def test_extract_and_parse_doclinks():
    body = '详见 <a href="notes://FABAPP/C1257A1B000000FF/0/C1257A1B00000099">SOP</a> 以及 notes://METROAPP/KB2.nsf/0/C1257A1B000000AA'
    links = extract_doclinks(body)
    assert len(links) == 2
    parsed = parse_doclink(links[0])
    assert parsed["host"] == "FABAPP"
    assert parsed["unid"] == "C1257A1B00000099"


def test_load_export_dir():
    loaded = load_export_dir(str(_SAMPLE))
    assert len(loaded["docs"]) == 3
    assert loaded["dbs"] == {"KB/process.nsf"}
    assert loaded["errors"] == []


def test_ingest_notes_export_with_attachment():
    tmp = Path(tempfile.mkdtemp())
    store = LocalVectorStore(tmp / "vs")
    summary = ingest_notes_export(str(_SAMPLE), store=store)
    assert summary["docs"] == 3
    assert summary["chunks"] > 0
    assert summary["attachments"] == 1          # checklist.md
    assert summary["links"] == 2                # 两条 notes:// 链接
    sources = " ".join(m["source"] for m in store.metas)
    assert sources.startswith("notes://KB/process.nsf/")
    assert "附件/处置检查单" in sources


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
