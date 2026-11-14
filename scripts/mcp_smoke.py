"""MCP Server 冒烟测试 (D2): stdio 子进程握手 + list_tools + 全部 7 工具调用验证。

用法: python scripts/mcp_smoke.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

EXPECTED_TOOLS = {
    "rag_search", "text2sql_query", "alarms_open", "watcher_summary",
    "kb_search", "shift_report", "kb_sources_check",
}


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve().parents[1] / "mcp_server.py")],
        env={"FABBOT_ROOT": str(Path(__file__).resolve().parents[1]),
             "PYTHONIOENCODING": "utf-8"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("tools:", names)
            missing = EXPECTED_TOOLS - set(names)
            assert not missing, f"缺少工具: {missing}"

            async def call(name: str, args: dict, expect_ok: bool = True) -> dict:
                result = await asyncio.wait_for(session.call_tool(name, args), timeout=90)
                data = json.loads(result.content[0].text)
                if expect_ok:
                    assert data.get("ok") is True, f"{name} 应成功: {data}"
                else:
                    assert data.get("ok") is False, f"{name} 应失败: {data}"
                return data

            r = await call("text2sql_query", {"question": "最近未处理的告警有哪些"})
            assert "sql" in r["data"]
            print("text2sql_query OK:", str(r["data"])[:100].replace("\n", " "))

            r = await call("alarms_open", {"hours": 168})
            assert r["data"]["summary"]["total"] > 0
            print("alarms_open OK: total =", r["data"]["summary"]["total"])

            r = await call("rag_search", {"query": "射频功率漂移", "top_k": 3})
            assert r["data"]["sources"]
            print("rag_search OK: sources =", len(r["data"]["sources"]))

            r = await call("kb_search", {"query": "腔压越限", "top_k": 3})
            assert r["data"]["sources"]
            print("kb_search OK: sources =", len(r["data"]["sources"]))

            r = await call("shift_report", {"hours": 8})
            assert "alarms" in r["data"]
            print("shift_report OK: hours =", r["data"]["hours"])

            r = await call("kb_sources_check", {})
            assert r["data"]["chunks"] > 0
            print("kb_sources_check OK: chunks =", r["data"]["chunks"])

            r = await call("watcher_summary", {})
            assert "wip" in r["data"]
            print("watcher_summary OK")
    print("MCP SMOKE PASSED (7/7 tools)")


if __name__ == "__main__":
    asyncio.run(main())
