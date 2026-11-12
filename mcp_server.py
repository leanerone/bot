"""FabBot MCP Server —— 把 BOT 的三大引擎（RAG/Text2SQL/告警值守）暴露为 MCP 工具。

传输: stdio（同机 Agent 子进程）默认; `--transport streamable-http --port 8111` 可选跨机。
用途: AIWEB Agent 工具循环 / 任何 MCP 客户端远程消费 BOT 引擎（连接器模式, 零进程内耦合）。

运行: python mcp_server.py                 (stdio)
     python mcp_server.py --transport streamable-http --port 8111
"""
from __future__ import annotations

import argparse
import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("fabbot")


@mcp.tool()
def rag_search(query: str, top_k: int = 6) -> str:
    """在工厂知识库（SOP/设备手册/处置经验/Notes 导出）中做混合检索，返回带来源的片段。

    Args:
        query: 自然语言问题或关键词（支持机台号/告警码精确匹配）
        top_k: 返回片段数 (1~10)
    """
    from app.rag import pipeline

    result = pipeline.ask(query, top_k=min(max(top_k, 1), 10))
    return json.dumps({
        "answer": result["answer"],
        "sources": result["sources"],
    }, ensure_ascii=False)


@mcp.tool()
def text2sql_query(question: str) -> str:
    """对授权生产数据库做只读查询（WIP/良率/机台状态/告警）。SQL 白名单校验 + 只读连接 + 行数上限。

    Args:
        question: 自然语言查询, 如 "最近未处理的告警有哪些"
    """
    from app.sqlbot import text2sql

    result = text2sql.query(question)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def alarms_open(hours: int = 168) -> str:
    """查询当前未处理告警（分级汇总 + 按机台分布 + 明细）。

    Args:
        hours: 回看窗口小时数 (默认 168 = 7 天)
    """
    from app.adapters.mock_mes import MockMESAdapter

    alarms = MockMESAdapter().get_alarms(hours=min(max(hours, 1), 24 * 30), only_open=True)
    summary = {
        "total": len(alarms),
        "critical": sum(1 for a in alarms if a["level"] == "CRITICAL"),
        "alarm": sum(1 for a in alarms if a["level"] == "ALARM"),
        "warn": sum(1 for a in alarms if a["level"] == "WARN"),
    }
    return json.dumps({"summary": summary, "alarms": alarms[:50]}, ensure_ascii=False)


@mcp.tool()
def watcher_summary() -> str:
    """值守概览: 未处理告警汇总 + 当前在制品批次总数。"""
    from app.adapters.mock_mes import MockMESAdapter

    adapter = MockMESAdapter()
    alarms = adapter.get_alarms(hours=24 * 7, only_open=True)
    return json.dumps({
        "alarms": {"total": len(alarms),
                   "critical": sum(1 for a in alarms if a["level"] == "CRITICAL")},
        "wip": adapter.get_wip_count(),
    }, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    parser.add_argument("--port", type=int, default=8111)
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
