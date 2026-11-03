"""HCL Notes -> JSON 导出脚本 (Windows + 已安装并登录的 Notes 客户端)。

用途: 把指定 Notes 库的文档按「导出 JSON 契约」导出到 data/notes_export/,
供 POST /api/kb/ingest_notes (mode=export) 导入知识库。

用法:
  pip install pywin32
  python tools/export_notes_com.py --server "" --db "KB/process.nsf" \
      --view "($All)" --out data/notes_export [--body-field Body] [--limit 100]

说明:
- NotesSession 走本机 Notes 客户端与 ID 文件; 若客户端未保存密码, 用
  --password 传入 (或先在 Notes 客户端登录一次)
- 服务器名传空字符串表示本机/当前工作区
- 大库建议先用 --limit 100 试跑, 全量导出放非生产时段
- 需要对目标库有只读以上权限; 导出内容会落在本地磁盘, 注意密级与存放位置
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.hcl_notes import extract_doclinks  # noqa: E402


def iter_view_documents(view):
    doc = view.GetFirstDocument()
    while doc is not None:
        yield doc
        doc = view.GetNextDocument(doc)


def _item_text(doc, names):
    """取第一个存在且有值的文本字段。"""
    for name in names:
        try:
            values = doc.GetItemValue(name)
        except Exception:
            continue
        if values:
            value = values[0]
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def doc_to_dict(doc, att_dir: Path, body_field: str) -> dict:
    record = {
        "unid": doc.UniversalID,
        "subject": _item_text(doc, ["Subject", "Title", "Topic"]) or "无标题",
        "author": _item_text(doc, ["From", "Author"]) ,
        "modified": str(doc.LastModified) if doc.LastModified else "",
        "body_text": "",
        "body_html": "",
        "attachments": [],
        "links": [],
    }
    body = doc.GetFirstItem(body_field)
    if body is not None:
        try:
            # GetFormattedText(去掉Tab, 每行宽度) -> 富文本纯文本
            record["body_text"] = body.GetFormattedText(False, 0)
        except Exception:
            pass
    for att in doc.Attachments or []:
        try:
            name = att.Name
            target = att_dir / f"{doc.UniversalID[:8]}_{name}"
            att.ExtractFile(str(target))
            record["attachments"].append({"name": name, "file": str(target.relative_to(att_dir.parent))})
        except Exception as exc:
            print(f"  [warn] 附件提取失败 {doc.UniversalID[:8]}: {exc}")
    record["links"] = extract_doclinks(record["body_text"])
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="", help="Domino 服务器名, 空串=本机")
    parser.add_argument("--db", required=True, help="库路径, 如 KB/process.nsf")
    parser.add_argument("--view", default="($All)", help="视图名, 默认 ($All)")
    parser.add_argument("--body-field", default="Body", help="富文本字段名, 默认 Body")
    parser.add_argument("--out", default="data/notes_export", help="输出目录")
    parser.add_argument("--limit", type=int, default=0, help="最多导出 N 篇, 0=全部")
    parser.add_argument("--password", default="", help="Notes ID 密码 (客户端未保存密码时)")
    args = parser.parse_args()

    import win32com.client  # pywin32

    out_dir = Path(args.out)
    att_dir = out_dir / "attachments"
    att_dir.mkdir(parents=True, exist_ok=True)

    session = win32com.client.Dispatch("Lotus.NotesSession")
    if args.password:
        session.Initialize(args.password)
    else:
        session.Initialize()  # 使用客户端已保存的凭据

    database = session.GetDatabase(args.server, args.db)
    view = database.GetView(args.view)
    if view is None:
        raise SystemExit(f"视图不存在: {args.view} (库: {args.db})")

    docs = []
    for i, doc in enumerate(iter_view_documents(view)):
        if args.limit and i >= args.limit:
            break
        record = doc_to_dict(doc, att_dir, args.body_field)
        if record["body_text"] or record["attachments"]:
            docs.append(record)
        if (i + 1) % 50 == 0:
            print(f"  已处理 {i + 1} 篇...")

    payload = {
        "db_title": database.Title,
        "db_path": args.db,
        "docs": docs,
    }
    out_file = out_dir / f"{Path(args.db).stem}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"导出完成: {len(docs)} 篇 -> {out_file} (附件目录: {att_dir})")


if __name__ == "__main__":
    main()
