"""MCPServer Echo Server with direct CallToolResult return"""

from typing import Annotated

from pydantic import BaseModel

from darpy_sdk.server.mcpserver import MCPServer
from darpy_sdk.types import CallToolResult, TextContent

mcp = MCPServer("Echo Server")


class EchoResponse(BaseModel):
    text: str


@mcp.tool()
def echo(text: str) -> Annotated[CallToolResult, EchoResponse]:
    """Echo the input text with structure and metadata"""
    return CallToolResult(
        content=[TextContent(type="text", text=text)], structured_content={"text": text}, _meta={"some": "metadata"}
    )
