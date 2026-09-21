from pydantic import BaseModel

from darpy_sdk.server import MCPServer
from darpy_sdk.server.mcpserver import Context

mcp = MCPServer("Bistro")


class Confirmation(BaseModel):
    confirm: bool


@mcp.tool()
async def book_table(date: str, ctx: Context) -> str:
    """Book a table at the bistro."""
    result = await ctx.elicit(f"Book a table for {date}?", schema=Confirmation)
    if result.action == "accept" and result.data.confirm:
        return f"Booked for {date}."
    return "No booking made."
