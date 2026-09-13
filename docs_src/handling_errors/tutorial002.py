from darpy_sdk import MCPError
from darpy_sdk.server import MCPServer
from darpy_sdk.types import INVALID_PARAMS

mcp = MCPServer("Bookshop")

CATALOG = {"Dune": "Frank Herbert", "Neuromancer": "William Gibson"}


@mcp.tool()
def get_author(title: str) -> str:
    """Look up the author of a book in the catalog."""
    if title not in CATALOG:
        raise MCPError(code=INVALID_PARAMS, message=f"No book titled {title!r} in the catalog.")
    return CATALOG[title]
