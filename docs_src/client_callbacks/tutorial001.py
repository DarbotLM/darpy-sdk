from pydantic import BaseModel

from darpy_sdk.server import MCPServer
from darpy_sdk.server.mcpserver import Context

mcp = MCPServer("Library")


class CardHolder(BaseModel):
    name: str


@mcp.tool()
async def issue_card(ctx: Context) -> str:
    """Issue a new library card."""
    answer = await ctx.elicit("What name should go on the card?", schema=CardHolder)
    if answer.action == "accept":
        return f"Card issued to {answer.data.name}."
    return "No card issued."
