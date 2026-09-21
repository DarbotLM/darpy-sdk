import logging

from darpy_sdk.server import MCPServer

logger = logging.getLogger(__name__)

mcp = MCPServer("Bookshop")


@mcp.tool()
def search_books(query: str) -> str:
    """Search the catalog by title or author."""
    logger.info("Searching for %r", query)
    return f"Found 3 books matching {query!r}."
