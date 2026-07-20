import sys
from typing import Any
import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent

# Suppress general logs so we don't corrupt the MCP stdio protocol which runs over stdout
import logging
logging.basicConfig(level=logging.ERROR)

app = Server("dummy-linkedin-n8n")

@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="research_company",
            description="Searches LinkedIn for company info",
            inputSchema={
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string"},
                    "domain": {"type": "string"}
                },
                "required": ["tenant_id", "domain"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    if name == "research_company":
        domain = arguments.get("domain", "unknown")
        # Pretend we scraped LinkedIn
        result = f"[MCP LinkedIn Scraper Server] Found 500 employees at {domain}. High growth trajectory."
        return [TextContent(type="text", text=result)]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
