"""MCP Server 冒烟测试: stdio 子进程握手 + list_tools + 调用 text2sql_query。

用法: python scripts/mcp_smoke.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402


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
            assert {"rag_search", "text2sql_query", "alarms_open", "watcher_summary"} <= set(names)
            result = await session.call_tool("text2sql_query",
                                             {"question": "最近未处理的告警有哪些"})
            text = result.content[0].text
            assert "sql" in text
            print("text2sql_query OK:", text[:120].replace("\n", " "))
            result = await session.call_tool("alarms_open", {"hours": 168})
            print("alarms_open OK:", result.content[0].text[:80].replace("\n", " "))
    print("MCP SMOKE PASSED")


if __name__ == "__main__":
    asyncio.run(main())
