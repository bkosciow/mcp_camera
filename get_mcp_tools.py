import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

MCP_SERVER_CMD = "/home/kosci/services/camera_mcp/.venv/bin/camera-mcp-mcp"


async def load_mcp_tools():
    """Connect to MCP server and get list of available tools"""
    server_params = StdioServerParameters(command=MCP_SERVER_CMD, args=[])

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.list_tools()
            return result.tools


if __name__ == "__main__":
    tools_list = asyncio.run(load_mcp_tools())
    for tool in tools_list:
        print(f"\n{'='*60}")
        print(f"🔧 {tool.name}")
        print(f"   {tool.description}")
        if tool.inputSchema and "properties" in tool.inputSchema:
            for param, details in tool.inputSchema["properties"].items():
                req = ""
                if "required" in tool.inputSchema and param in tool.inputSchema["required"]:
                    req = " (required)"
                default = ""
                if "default" in details:
                    default = f" = {details['default']}"
                print(f"   • {param}{req}: {details.get('type', 'any')}{default}")
        print(f"{'='*60}")
