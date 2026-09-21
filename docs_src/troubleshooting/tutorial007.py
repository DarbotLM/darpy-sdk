from typing import Annotated

from pydantic import BaseModel

from darpy_sdk.server import MCPServer
from darpy_sdk.server.mcpserver import Elicit, Resolve

mcp = MCPServer("Bistro")


class Confirmation(BaseModel):
    confirm: bool


async def ask_to_confirm(date: str) -> Elicit[Confirmation]:
    """Resolver: ask the user to confirm the booking."""
    return Elicit(f"Book a table for {date}?", Confirmation)


@mcp.tool()
async def book_table(date: str, answer: Annotated[Confirmation, Resolve(ask_to_confirm)]) -> str:
    """Book a table at the bistro."""
    if answer.confirm:
        return f"Booked for {date}."
    return "No booking made."
