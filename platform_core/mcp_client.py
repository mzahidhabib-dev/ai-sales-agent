import asyncio
from typing import Any, Dict
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from platform_core.logging_config import get_logger

logger = get_logger(__name__)

async def _call_mcp_tool_async(server_cmd: str, server_args: list[str], tool_name: str, tool_args: dict) -> Dict[str, Any]:
    server_params = StdioServerParameters(
        command=server_cmd,
        args=server_args
    )
    
    logger.info("Connecting to MCP server", extra={"command": server_cmd, "tool": tool_name})
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # Call the tool
            logger.info("Calling MCP tool", extra={"tool": tool_name})
            result = await session.call_tool(tool_name, arguments=tool_args)
            
            # Convert CallToolResult to dict
            output = ""
            for content in result.content:
                if content.type == "text":
                    output += content.text
            
            return {"output": output, "is_error": result.isError}

def call_mcp_tool(server_cmd: str, server_args: list[str], tool_name: str, tool_args: dict) -> Any:
    """
    Synchronous wrapper around the async MCP client.
    """
    try:
        result = asyncio.run(_call_mcp_tool_async(server_cmd, server_args, tool_name, tool_args))
        if result.get("is_error"):
            raise RuntimeError(f"MCP Tool '{tool_name}' returned error: {result['output']}")
        return result["output"]
    except Exception as e:
        logger.error("MCP Tool call failed", extra={
            "tool": tool_name,
            "exc_type": type(e).__name__,
            "error": str(e)
        })
        raise
