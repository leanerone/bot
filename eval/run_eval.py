"""离线评测脚本: 知识检索命中率 + Text2SQL 可执行率。

用法:
  python eval/run_eval.py                 # 离线模式 (检索/SQL 执行, 不调 LLM 生成)
  python eval/run_eval.py --topk 8        # 调整检索档位
  python eval/run_eval.py --llm           # 额外跑 LLM 生成, 统计引用率 (需已接真实模型)

输出: eval/report.md + eval/report.json
说明: 评测集见 eval/evalset.json; 上线前请用真实问题扩充至 50~100 条。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag import pipeline  # noqa: E402
from app.sqlbot import text2sql  # noqa: E402
from app.sqlbot.validator import SQLRejected  # noqa: E402


def _kb_eval(item: dict, topk: int) -> dict:
    t0 = time.time()
    context, sources = pipeline._retrieve(item["question"], topk)
    ms = int((time.time() - t0) * 1000)
    expects = item.get("expect", [])
    joined = json.dumps(sources, ensure_ascii=False)
    hit_terms = [e for e in expects if e.lower() in joined.lower()]
    return {
        "id": item["id"],
        "type": "kb",
        "hit": bool(context) and (not expects or len(hit_terms) > 0),
        "hit_terms": hit_terms,
        "miss_terms": [e for e in expects if e not in hit_terms],
        "n_sources": len(sources),
        "top1_source": sources[0]["source"] if sources else "",
        "ms": ms,
    }


def _sql_eval(item: dict) -> dict:
    t0 = time.time()
    try:
        result = text2sql.query(item["question"])
    except (SQLRejected, FileNotFoundError, Exception) as exc:  # noqa: BLE001
        return {"id": item["id"], "type": "sql", "pass": False,
                "error": str(exc)[:120], "ms": int((time.time() - t0) * 1000)}
    ms = int((time.time() - t0) * 1000)
    cols = result.get("columns", [])
    missing = [c for c in item.get("expect_columns", []) if c not in cols]
    return {
        "id": item["id"], "type": "sql",
        "pass": not missing and result.get("row_count", 0) >= 0,
        "sql": result.get("sql"), "rows": result.get("row_count"),
        "missing_columns": missing, "ms": ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--llm", action="store_true", help="额外统计 LLM 生成回答的引用率")
    args = parser.parse_args()

    evalset = json.loads((ROOT / "eval" / "evalset.json").read_text(encoding="utf-8"))
    items = evalset["items"]
    kb_rows, sql_rows = [], []
    for item in items:
        if item["type"] == "kb":
            kb_rows.append(_kb_eval(item, args.topk))
        else:
            sql_rows.append(_sql_eval(item))

    kb_hit = sum(1 for r in kb_rows if r["hit"])
    sql_pass = sum(1 for r in sql_rows if r["pass"])
    report = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "mode": "offline" + ("+llm" if args.llm else ""),
        "topk": args.topk,
        "kb": {"total": len(kb_rows), "hit": kb_hit,
               "hit_rate": round(kb_hit / len(kb_rows), 4) if kb_rows else None,
               "avg_ms": round(sum(r["ms"] for r in kb_rows) / len(kb_rows)) if kb_rows else None},
        "sql": {"total": len(sql_rows), "pass": sql_pass,
                "pass_rate": round(sql_pass / len(sql_rows), 4) if sql_rows else None,
                "avg_ms": round(sum(r["ms"] for r in sql_rows) / len(sql_rows)) if sql_rows else None},
        "detail": kb_rows + sql_rows,
    }

    # 可选: LLM 生成引用率 (仅当配置了真实模型)
    if args.llm:
        cited, gen_total = 0, 0
        for item in items:
            if item["type"] != "kb":
                continue
            r = pipeline.ask(item["question"])
            if r["sources"]:
                gen_total += 1
                import re
                if re.search(r"\[\d", r["answer"]):
                    cited += 1
        report["llm_citation"] = {"total": gen_total,
                                  "cited": cited,
                                  "rate": round(cited / gen_total, 4) if gen_total else None}

    (ROOT / "eval").mkdir(exist_ok=True)
    (ROOT / "eval" / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [
        "# Fab Bot 离线评测报告",
        "",
        f"- 时间: {report['time']}  模式: {report['mode']}  top_k={args.topk}",
        "",
        "| 指标 | 结果 |",
        "|---|---|",
        f"| 知识检索命中率 | {kb_hit}/{len(kb_rows)} ({report['kb']['hit_rate']}) |",
        f"| Text2SQL 通过率 | {sql_pass}/{len(sql_rows)} ({report['sql']['pass_rate']}) |",
        f"| 检索平均耗时 | {report['kb']['avg_ms']} ms |",
        f"| SQL 平均耗时 | {report['sql']['avg_ms']} ms |",
    ]
    if args.llm and "llm_citation" in report:
        lines.append(f"| LLM 回答引用率 | {report['llm_citation']['cited']}/{report['llm_citation']['total']} "
                     f"({report['llm_citation']['rate']}) |")
    lines += ["", "## 未命中项", ""]
    lines += [f"- {r['id']}: 缺少 {r['miss_terms']}" for r in kb_rows if not r["hit"]] or ["- (无)"]
    lines += ["", "## SQL 失败项", ""]
    failed = [r for r in sql_rows if not r["pass"]]
    lines += [f"- {r['id']}: {r.get('error') or ('缺列 ' + str(r.get('missing_columns')))}" for r in failed] or ["- (无)"]
    (ROOT / "eval" / "report.md").write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines[:12]))
    print(f"\n报告: eval/report.md / eval/report.json")
    sys.exit(0 if kb_hit == len(kb_rows) and sql_pass == len(sql_rows) else 1)


if __name__ == "__main__":
    main()
