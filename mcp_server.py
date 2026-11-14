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

from app.config import cfg

mcp = FastMCP("fabbot")


@mcp.tool()
def rag_search(query: str, top_k: int = 6) -> str:
    """在工厂知识库（SOP/设备手册/处置经验/Notes 导出）中做混合检索，返回带来源的片段。

    Args:
        query: 自然语言问题或关键词（支持机台号/告警码精确匹配）
        top_k: 返回片段数 (1~10)
    """
    return _env(_rag_search_impl, query, top_k)


def _rag_search_impl(query: str, top_k: int) -> str:
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
    return _env(_text2sql_impl, question)


def _text2sql_impl(question: str) -> str:
    from app.sqlbot import text2sql

    result = text2sql.query(question)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def alarms_open(hours: int = 168) -> str:
    """查询当前未处理告警（分级汇总 + 按机台分布 + 明细）。

    Args:
        hours: 回看窗口小时数 (默认 168 = 7 天)
    """
    return _env(_alarms_impl, hours)


def _alarms_impl(hours: int) -> str:
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
    return _env(_watcher_impl)


def _watcher_impl() -> str:
    from app.adapters.mock_mes import MockMESAdapter

    adapter = MockMESAdapter()
    alarms = adapter.get_alarms(hours=24 * 7, only_open=True)
    return json.dumps({
        "alarms": {"total": len(alarms),
                   "critical": sum(1 for a in alarms if a["level"] == "CRITICAL")},
        "wip": adapter.get_wip_count(),
    }, ensure_ascii=False)


# ── v4.4 (D1): 工具扩充 —— 统一 envelope {ok, data, error}, 错误不裸抛, 供 Agent 判定 ──

def _env(fn, *args, **kwargs) -> str:
    """工具统一出口: 异常转 ok=false, Agent 可据此重试/降级。"""
    try:
        return json.dumps({"ok": True, "data": json.loads(fn(*args, **kwargs))},
                          ensure_ascii=False)
    except Exception as exc:  # noqa: BLE001 —— 工具边界兜底
        return json.dumps({"ok": False, "data": None,
                           "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False)


@mcp.tool()
def kb_search(query: str, top_k: int = 6) -> str:
    """纯知识库检索 (不生成回答): 返回最相关的 SOP/手册/Notes 片段, 供调用方自行组织答案。

    Args:
        query: 自然语言问题或关键词 (支持机台号/告警码精确匹配)
        top_k: 返回片段数 (1~10)
    """
    return _env(_kb_search_impl, query, top_k)


def _kb_search_impl(query: str, top_k: int) -> str:
    from app.rag.pipeline import _retrieve

    context, sources = _retrieve(query, top_k=min(max(top_k, 1), 10))
    return json.dumps({"sources": sources}, ensure_ascii=False)


@mcp.tool()
def shift_report(hours: int = 8) -> str:
    """生成交班报告摘要 (告警汇总/机台分布/待办), 供班组交接使用。

    Args:
        hours: 报告覆盖的小时数 (1~72)
    """
    return _env(_shift_report_impl, hours)


def _shift_report_impl(hours: int) -> str:
    from app.services.shift_report import build_shift_report

    return json.dumps(build_shift_report(hours=min(max(hours, 1), 72)), ensure_ascii=False)


@mcp.tool()
def kb_sources_check() -> str:
    """只读: 知识库来源清单与片段统计, 用于导入前核对。"""
    return _env(_kb_sources_impl)


def _kb_sources_impl() -> str:
    from app.rag.ingest import get_store

    store = get_store()
    counts: dict = {}
    for m in store.metas:
        counts[m["source"]] = counts.get(m["source"], 0) + 1
    return json.dumps({"chunks": len(store), "sources": counts}, ensure_ascii=False)


def _warmup() -> None:
    """主线程预热导入 (rag/向量库/numpy): 避免工具调用在 worker 线程内冷导入挂起。"""
    try:
        from app.rag import pipeline  # noqa: F401
        from app.rag.ingest import get_store  # noqa: F401

        get_store()
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", default="stdio", choices=["stdio", "streamable-http"])
    parser.add_argument("--port", type=int, default=8111)
    args = parser.parse_args()
    _warmup()

    if args.transport == "streamable-http":
        # C5: streamable-http 模式支持共享密钥头 X-FabBot-Key (stdio 模式同机无需)
        _run_streamable_http(args.port)
    else:
        mcp.run(transport="stdio")


def _run_streamable_http(port: int) -> None:
    """streamable-http + 可选密钥校验中间件 (config mcp.require_key / mcp.key)。"""
    import uvicorn
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse as _JSONResp

    required = bool(cfg("mcp.require_key", False))
    secret = cfg("mcp.key", "")

    class KeyGuard(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if required and request.headers.get("x-fabbot-key", "") != secret:
                return _JSONResp({"error": "unauthorized: missing/invalid X-FabBot-Key"},
                                 status_code=401)
            return await call_next(request)

    app = mcp.streamable_http_app(middleware=[Middleware(KeyGuard)])
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
