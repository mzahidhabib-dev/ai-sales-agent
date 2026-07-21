import sys
import logging
import requests
from bs4 import BeautifulSoup
from typing import Any
import mcp.server.stdio
from mcp.server import Server
from mcp.types import Tool, TextContent

# Suppress general logs so we don't corrupt the MCP stdio protocol which runs over stdout
logging.basicConfig(level=logging.ERROR)

app = Server("web-research-mcp")

@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="research_company",
            description="Scrapes the public website of a company to gather research and buying signals.",
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
        domain = arguments.get("domain")
        if not domain:
            raise ValueError("Domain is required")
            
        # Add http if missing
        if not domain.startswith("http"):
            url = f"https://{domain}"
        else:
            url = domain
            
        try:
            # We must use a real-looking user agent otherwise many sites block python-requests
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script, style, and nav elements to get clean text
            for script in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                script.extract()
                
            text = soup.get_text(separator=' ', strip=True)
            
            # Truncate to first 3000 chars to avoid token limit explosions
            if len(text) > 3000:
                text = text[:3000] + "... [truncated]"
                
            result = f"[Real Web Scraper] Successfully extracted data from {domain}:\n\n{text}"
            return [TextContent(type="text", text=result)]
            
        except requests.exceptions.RequestException as e:
            return [TextContent(type="text", text=f"[Real Web Scraper] Failed to fetch {domain}. Error: {str(e)}")]
            
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
