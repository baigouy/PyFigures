"""CI: the built app serves the saved-file MCP server itself (what Tools > MCP server…
registers in the standalone apps): `<app> --mcp-server --tools categories` over stdio must
answer and list its three entry tools.

    python .github/scripts/check_mcp_server.py "dist/PyFigures/PyFigures MCP.exe"
"""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED = {"list_pyfigures_categories", "find_pyfigures_tools", "use_pyfigures_tool"}


async def main(app):
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    params = StdioServerParameters(command=app, args=["--mcp-server", "--tools", "categories"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 300)
            names = {t.name for t in (await session.list_tools()).tools}
    print("tools:", sorted(names))
    if names != EXPECTED:
        sys.exit(f"expected {sorted(EXPECTED)}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
